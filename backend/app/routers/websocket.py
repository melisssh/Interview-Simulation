import os
import json
import base64
import logging
import tempfile
import wave
from typing import List, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ..analysis.speech_metrics import (
    pause_frequency_score_from_segments,
    pcm_duration_seconds,
    pcm_tone_variation_score,
    pcm_volume_stability_score,
    words_per_minute,
)
from ..database import SessionLocal
from .. import models

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

try:
    import ollama
except ImportError:
    ollama = None

logger = logging.getLogger(__name__)

router = APIRouter()

_WS_WHISPER_MODEL = None


def _get_ws_whisper_model():
    global _WS_WHISPER_MODEL
    if WhisperModel is None:
        raise RuntimeError("faster-whisper yüklü değil")
    if _WS_WHISPER_MODEL is None:
        _WS_WHISPER_MODEL = WhisperModel("base", device="cpu", compute_type="int8")
    return _WS_WHISPER_MODEL


def _transcribe_pcm_b64_with_metrics(audio_b64: str, language: str = "tr") -> dict:
    """Transcribe PCM int16 mono @48kHz; attach speech metrics from audio + segment timings."""
    empty: dict = {
        "text": "",
        "speech_rate_wpm": None,
        "pause_frequency_score": None,
        "volume_stability_score": None,
        "tone_variation_score": None,
    }
    audio_bytes = base64.b64decode(audio_b64)
    if not audio_bytes or len(audio_bytes) < 3200:
        return empty

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        with wave.open(tmp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            wf.writeframes(audio_bytes)
        model = _get_ws_whisper_model()
        segments, _ = model.transcribe(tmp_path, language=language)
        segs = list(segments)
        text = "".join(seg.text for seg in segs).strip()
        dur = pcm_duration_seconds(len(audio_bytes))
        wc = len(text.split())
        wpm = words_per_minute(wc, dur)
        ranges = [(float(s.start), float(s.end)) for s in segs]
        pause = pause_frequency_score_from_segments(ranges)
        vol = pcm_volume_stability_score(audio_bytes)
        tone = pcm_tone_variation_score(audio_bytes)
        return {
            "text": text,
            "speech_rate_wpm": wpm,
            "pause_frequency_score": pause,
            "volume_stability_score": vol,
            "tone_variation_score": tone,
        }
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _ollama_chat(messages: list[dict], model: str | None = None):
    if not ollama:
        raise RuntimeError("Ollama python paketi yüklü değil")

    target_model = model or os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    host = (os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_HOST") or "").strip()
    options = {
        "temperature": float(os.getenv("OLLAMA_TEMPERATURE", "0.2")),
        "top_p": float(os.getenv("OLLAMA_TOP_P", "0.9")),
        "num_predict": int(os.getenv("OLLAMA_NUM_PREDICT", "300")),
    }

    if host and hasattr(ollama, "Client"):
        client = ollama.Client(host=host)
        return client.chat(model=target_model, messages=messages, options=options)
    return ollama.chat(model=target_model, messages=messages, options=options)


def _looks_wrong_language(text: str, language: str) -> bool:
    low = (text or "").lower()
    if language == "tr":
        return any(tok in low for tok in ["tell me", "what ", "describe ", "could you", "example"])
    return any(tok in low for tok in ["nasıl", "neden", "örnek", "mısın", "misin", "teşekkür"])


class InterviewSession:
    """State machine for real-time interview flow."""

    PHASE_GREETING = "greeting"
    PHASE_QUESTIONS = "questions"
    PHASE_CLOSING = "closing"
    PHASE_ENDED = "ended"

    def __init__(self, interview, profile=None):
        self.interview = interview
        self.profile = profile or {}
        self.domain = interview.domain or "general"
        self.language = interview.language or "tr"
        self.max_questions = 6
        self.question_count = 0
        self.answer_count = 0
        self.history: List[Dict] = []
        self.phase = self.PHASE_GREETING
        self.cv_context = ""
        if profile:
            cv_text = profile.get("cv_text", "") or ""
            uni = profile.get("university", "") or ""
            dept = profile.get("department", "") or ""
            self.cv_context = f"Aday Profili:\n- Üniversite: {uni}\n- Bölüm: {dept}\n- CV Özeti: {cv_text[:800]}"

    def _build_system_prompt(self) -> str:
        dil = self.language
        company_name = self.interview.company_name or "Şirket"
        department_name = self.interview.department_name or "Departman"
        position = self.interview.position or "Pozisyon"
        interview_type = "Teknik Mülakat" if self.domain == "technical" else "Davranışsal/HR Mülakat"

        context_block = ""
        if self.cv_context:
            context_block = f"\n\nADAY HAKKINDA BİLGİLER (BU BİLGİLERİ SORULARINA YEDİR):\n{self.cv_context}"

        if dil == "tr":
            return f"""Sen {company_name} şirketinin profesyonel ve deneyimli mülakatçısısın.
Mülakat dili SADECE TÜRKÇEDİR. İngilizce KESİNlikle kullanma.

POZİSYON:
- Unvan: {position}
- Departman: {department_name}
- Tip: {interview_type}
{context_block}

MÜLAKAT FAZLARI:
1. GİRİŞ: Kısa bir karşılama yap ve adaydan kendini tanıtmasını, eğitim ve deneyim geçmişini anlatmasını iste.
2. DERİNLEŞME: Adayın verdiği cevaplara ve CV'sine bakarak teknik veya davranışsal sorular sor.
   - Eğer "technical" ise: Kullandığı teknolojileri, proje deneyimlerini ve teknik yaklaşımlarını sorgula.
   - Eğer "general" ise: Takım çalışması, zorluklarla başa çıkma ve iletişim becerilerini sorgula.
3. KAPANIŞ: Yeterli soru sorulduğunda (genellikle 5-7 arası) kısa bir teşekkürle mülakatı bitir.

KESİN KURALLAR:
1. DİL: Sadece Türkçe yanıt ver. İngilizce kelime, selamlama veya terim YASAK.
2. TEK SORU: Her turda SADECE 1 soru sor. Asla birden fazla soru sorma.
3. DOĞAL AKIŞ: Adayın son cevabına bağlı kal. Konuyu dağıtma.
4. GERİ BİLDİRİM: Soruya geçmeden önce adayın cevabını çok kısa (1 cümle) onayla. (Örn: "Harika bir örnek, teşekkürler. Peki...")
5. KISA VE NET: Soruların maksimum 2-3 cümle olsun.

ÖNEMLİ: Adayın CV'sindeki detayları yakala ve ona göre soru üret!"""
        else:
            return f"""You are a professional and experienced interviewer at {company_name}.
The interview language is STRICTLY ENGLISH. Do NOT use Turkish.

POSITION:
- Title: {position}
- Department: {department_name}
- Type: {interview_type}
{context_block}

INTERVIEW PHASES:
1. INTRODUCTION: Brief welcome, ask the candidate to introduce themselves and their background.
2. DEEP-DIVE: Ask technical or behavioral questions based on answers and CV.
3. CLOSING: When enough questions are asked (usually 5-7), give a short thank you and end the interview.

STRICT RULES:
1. LANGUAGE: Reply ONLY IN ENGLISH. No Turkish words allowed.
2. ONE QUESTION: Ask EXACTLY ONE question per turn.
3. NATURAL FLOW: Stay connected to the candidate's last answer.
4. FEEDBACK: Acknowledge the answer briefly (1 sentence) before asking the next question.
5. SHORT & CLEAR: Keep questions max 2-3 sentences.

IMPORTANT: Catch details from the candidate's CV and ask specific questions about them!"""

    def _get_fallback(self) -> str:
        lang = self.language
        if self.phase == self.PHASE_GREETING:
            if lang == "en":
                return "Welcome! To start, could you briefly introduce yourself and your relevant background?"
            return "Hoş geldiniz! Başlangıç için kendinizi ve ilgili geçmişinizi kısaca tanıtır mısınız?"

        if self.phase == self.PHASE_CLOSING:
            if lang == "en":
                return "Thank you for your time. The interview is now complete. We will get back to you soon."
            return "Vaktiniz için teşekkür ederiz. Mülakatımız sona erdi. En kısa sürede size dönüş yapacağız."

        fallbacks_en = [
            "Can you give a concrete example and explain your exact actions?",
            "What was the most difficult part, and how did you handle it?",
            "What would you do differently if you faced the same situation again?",
            "How does this experience prepare you for this role?",
            "Thank you. Is there anything else you would like to add?",
        ]
        fallbacks_tr = [
            "Somut bir örnek verip tam olarak hangi adımları attığınızı anlatır mısınız?",
            "En zorlandığınız nokta neydi ve bunu nasıl yönettiniz?",
            "Aynı durum tekrar olsa neyi farklı yapardınız?",
            "Bu deneyim sizi bu rol için nasıl hazırladı?",
            "Teşekkürler. Eklemek istediğiniz son bir şey var mı?",
        ]
        pool = fallbacks_en if lang == "en" else fallbacks_tr
        idx = min(max(0, self.question_count - 1), len(pool) - 1)
        return pool[idx]

    def _ask_ollama(self, prompt: str) -> str | None:
        # OPTIMIZASYON: Ollama çok ağır olduğu için, fallback sorularını kullan
        # Eğer Ollama istersen, bu fonksiyonun başına True ekle:
        # if True:  # Ollama'yı devre dışı bırak
        #     return None

        try:
            messages = [{"role": "system", "content": self._build_system_prompt()}]
            for h in self.history[-8:]:
                messages.append(h)
            messages.append({"role": "user", "content": prompt})

            response = _ollama_chat(
                model=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
                messages=messages,
            )
            out = (response.get("message", {}).get("content", "") or "").strip()
            return " ".join(out.split())
        except Exception as e:
            logger.error(f"Ollama LLM error: {e}")
            return None

    def get_greeting(self) -> str:
        """Phase 1: Greeting + first question."""
        self.phase = self.PHASE_QUESTIONS
        lang = self.language
        if lang == "en":
            starter = "Start the interview with a brief welcome and the first question only."
        else:
            starter = "Mülakatı kısa bir karşılama ve yalnızca ilk soruyla başlat."

        q = self._ask_ollama(starter)
        if not q or _looks_wrong_language(q, lang):
            q = self._get_fallback()
        self.question_count = 1
        self.history.append({"role": "assistant", "content": q})
        return q

    def handle_answer(self, transcript: str) -> tuple[str, bool]:
        """Phase 2: Process answer, generate next question. Returns (response, is_ended)."""
        self.answer_count += 1
        self.history.append({"role": "user", "content": transcript})

        if self.answer_count >= self.max_questions:
            self.phase = self.PHASE_CLOSING

        if self.phase == self.PHASE_CLOSING:
            closing = self._get_fallback()
            self.history.append({"role": "assistant", "content": closing})
            self.phase = self.PHASE_ENDED
            return closing, True

        lang = self.language
        next_q_num = self.question_count + 1
        
        # Dinamik Prompt: Faz ve Profil bilgisi içerir
        phase_instruction = ""
        if self.question_count < 2:
            phase_instruction = "Adayın kendini tanıtmasına dayanarak, geçmişini ve motivasyonunu derinleştiren bir soru sor."
        elif self.domain == "technical":
            phase_instruction = "Adayın teknik bilgilerini ve CV'sindeki projeleri sorgulayan spesifik bir teknik soru sor."
        else:
            phase_instruction = "Adayın davranışsal yetkinliklerini (takım, çatışma, liderlik) ölçen bir durum sorusu sor."

        if lang == "en":
            prompt = (
                f"Candidate's answer: {transcript}\n"
                f"Context: {self.cv_context}\n"
                f"Instruction: {phase_instruction}\n"
                f"Phase: Question {next_q_num} of roughly {self.max_questions}.\n"
                "Ask exactly one next question in English. Acknowledge their answer briefly first."
            )
        else:
            prompt = (
                f"Adayın cevabı: {transcript}\n"
                f"Bağlam (Profil): {self.cv_context}\n"
                f"Talimat: {phase_instruction}\n"
                f"Faz: Yaklaşık {self.max_questions} sorudan {next_q_num}. soru.\n"
                "Adayın cevabını çok kısa (1 cümle) onayla ve ardından Türkçe bir sonraki soruyu sor."
            )

        q = self._ask_ollama(prompt)
        if not q or _looks_wrong_language(q, lang):
            q = self._get_fallback()

        self.question_count = next_q_num
        self.history.append({"role": "assistant", "content": q})
        return q, False


@router.websocket("/ws/interview/{interview_id}")
async def websocket_interview(websocket: WebSocket, interview_id: int):
    print(f"\n🔵🔵🔵 WS HANDLER START: interview_id={interview_id} 🔵🔵🔵\n")
    await websocket.accept()
    print(f"🔵 WebSocket accept edildi\n")
    logger.info(f"🔵 WebSocket açıldı: interview_id={interview_id}")

    print(f"🔵 SessionLocal oluşturuluyor...\n")
    db = SessionLocal()
    print(f"🔵 SessionLocal oluşturuldu\n")

    try:
        print(f"🔵 Try bloğu başladı\n")
        interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
        print(f"🔵 Interview sorgusu yapıldı: {interview is not None}\n")
        logger.info(f"Interview sorgusu yapıldı: {interview is not None}")

        # Fetch interview questions from database
        interview_questions = {}
        if interview:
            print(f"🔵 Interview soruları yükleniyor...\n")
            iqs = db.query(models.InterviewQuestion).filter(
                models.InterviewQuestion.interview_id == interview_id
            ).order_by(models.InterviewQuestion.order).all()
            print(f"🔵 Interview soruları yüklendi: {len(iqs)}\n")
            logger.info(f"Interview soruları yüklendi: {len(iqs)}")
            for iq in iqs:
                question_text = iq.question_text or ""
                if not question_text and iq.question_id:
                    q = db.query(models.Question).filter(
                        models.Question.id == iq.question_id
                    ).first()
                    if q:
                        question_text = q.text
                interview_questions[iq.order] = {
                    "text": question_text,
                    "id": iq.id
                }

        # Profil ve CV bilgilerini çek
        profile_data = {}
        if interview:
            profile = db.query(models.Profile).filter(models.Profile.user_id == interview.user_id).first()
            if profile:
                profile_data = {
                    "university": profile.university or "",
                    "department": profile.department or "",
                    "cv_text": ""
                }
                # CV metni varsa oku
                if profile.cv_path:
                    try:
                        from pypdf import PdfReader
                        reader = PdfReader(profile.cv_path)
                        text_parts = []
                        for page in reader.pages:
                            text_parts.append(page.extract_text())
                        profile_data["cv_text"] = "\n".join(text_parts)
                        logger.info(f"CV yüklendi: {len(profile_data['cv_text'])} karakter")
                    except Exception as e:
                        logger.warning(f"CV okuma hatası: {e}")

        print(f"🔵 Profil ve CV yüklendi\n")
        if not interview:
            await websocket.send_json({"type": "error", "message": "Mülakat bulunamadı"})
            return

        print(f"🔵 InterviewSession oluşturuluyor...\n")
        session = InterviewSession(interview, profile=profile_data)
        print(f"🔵 InterviewSession oluşturuldu: domain={session.domain}, language={session.language}\n")
        logger.info(f"✅ Session oluşturuldu: domain={session.domain}, language={session.language}")
    except Exception as e:
        print(f"\n❌❌❌ EXCEPTION: {e}\n")
        import traceback
        print(f"\n{traceback.format_exc()}\n")
        logger.error(f"❌ WebSocket setup hatası: {e}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": f"Setup hatası: {str(e)}"})
        except:
            pass
        return
    finally:
        print(f"🔵 Finally bloğu: db.close() çağrılıyor\n")
        db.close()

    async def safe_send(payload: dict) -> bool:
        try:
            await websocket.send_json(payload)
            return True
        except (WebSocketDisconnect, RuntimeError):
            logger.info("WS send skipped (closed): interview_id=%s", interview_id)
            return False

    def update_interview_status(new_status: str, context: str) -> None:
        status_db = SessionLocal()
        try:
            interview_record = status_db.query(models.Interview).filter(
                models.Interview.id == interview_id
            ).first()
            if interview_record:
                interview_record.status = new_status
                status_db.commit()
                logger.info(
                    "Interview %s status set to %s (%s)",
                    interview_id,
                    new_status,
                    context,
                )
        except Exception as exc:
            logger.error("Error updating interview status to %s: %s", new_status, exc)
        finally:
            status_db.close()

    try:
        print(f"\n🟢🟢🟢 MAIN LOOP BAŞLADI: interview_id={interview_id} 🟢🟢🟢\n")
        logger.info(f"Interview session started: interview_id={interview_id}")

        while True:
            try:
                print(f"🟢 Message bekleniyor...\n")
                raw = await websocket.receive_text()
                print(f"🟢 Message alındı: {raw[:100]}\n")
                data = json.loads(raw)
            except json.JSONDecodeError as e:
                print(f"🔴 JSON decode error: {e}\n")
                continue
            except WebSocketDisconnect:
                print(f"🔴 Client disconnected\n")
                logger.info(f"Client disconnected: {interview_id}")
                break
            except Exception as e:
                print(f"🔴 receive_text error: {e}\n")
                logger.error(f"receive_text error: {e}", exc_info=True)
                break

            msg_type = data.get("type")
            print(f"🟢 Message type: {msg_type}\n")

            if msg_type == "init":
                print(f"🟢 Init mesajı işleniyor\n")
                session.domain = data.get("domain", session.domain)
                session.language = data.get("language", session.language)
                session.max_questions = data.get("max_questions", 5)
                session.answer_count = 0
                update_interview_status("in_progress", "ws_init")

                greeting = session.get_greeting()
                if not await safe_send({
                    "type": "question",
                    "question": greeting,
                    "q_num": 1,
                    "total": session.max_questions,
                    "phase": session.phase,
                }):
                    break

            elif msg_type == "audio":
                print(f"🟢 Audio mesajı işleniyor\n")
                audio_b64 = data.get("audio")
                if not audio_b64:
                    print(f"🔴 Audio verisi yok\n")
                    continue

                try:
                    print(f"🟢 Transcript oluşturuluyor...\n")
                    tm = _transcribe_pcm_b64_with_metrics(audio_b64, language=session.language)
                    transcript = (tm.get("text") or "").strip()
                    print(f"🟢 Transcript: {transcript[:50]}\n")

                    if not transcript:
                        print(f"🔴 Transcript boş\n")
                        await safe_send({
                            "type": "error",
                            "message": "Cevap net algılanamadı. Daha net konuşup tekrar deneyin.",
                        })
                        continue

                    logger.info(f"Transcription: {transcript[:100]}...")

                    # Save answer to database BEFORE handle_answer increments counter
                    print(f"🟢 Database session açılıyor\n")
                    db = SessionLocal()
                    try:
                        print(f"🟢 Cevap kaydediliyor\n")
                        # answer_count will be incremented in handle_answer, so use current value
                        current_q_num = session.answer_count + 1  # Next question number (since we increment in handle_answer)
                        question_text = interview_questions.get(current_q_num, {}).get("text", f"Question {current_q_num}")

                        answer_record = models.InterviewAnswer(
                            interview_id=interview_id,
                            question_order=current_q_num,
                            question_text=question_text,
                            answer_text=transcript,
                            speech_rate_wpm=tm.get("speech_rate_wpm"),
                            pause_frequency_score=tm.get("pause_frequency_score"),
                            volume_stability_score=tm.get("volume_stability_score"),
                            tone_variation_score=tm.get("tone_variation_score"),
                        )
                        db.add(answer_record)
                        db.commit()
                        print(f"🟢 Cevap kaydedildi: {current_q_num}\n")
                        logger.info(f"Saved answer {current_q_num} to database")
                    except Exception as save_error:
                        print(f"🔴 Save error: {save_error}\n")
                        logger.error(f"Error saving answer: {save_error}")
                    finally:
                        db.close()

                    print(f"🟢 handle_answer çağrılıyor\n")
                    response_text, is_ended = session.handle_answer(transcript)
                    print(f"🟢 handle_answer tamamlandı: is_ended={is_ended}\n")

                    if is_ended:
                        print(f"🟢 Mülakat bitmiş!\n")
                        update_interview_status("completed", "ws_auto_end")

                        print(f"🟢 Ended mesajı gönderiliyor\n")
                        if not await safe_send({
                            "type": "ended",
                            "message": "Mülakat tamamlandı. Teşekkür ederiz.",
                            "question": response_text,
                            "q_num": session.question_count,
                            "total": session.max_questions,
                            "transcript": transcript,
                        }):
                            break
                        break

                    print(f"🟢 Sonraki soru gönderiliyor: q_num={session.question_count}\n")
                    if not await safe_send({
                        "type": "question",
                        "question": response_text,
                        "transcript": transcript,
                        "q_num": session.question_count,
                        "total": session.max_questions,
                        "phase": session.phase,
                    }):
                        print(f"🔴 safe_send başarısız\n")
                        break
                    print(f"🟢 Soru gönderildi!\n")

                except Exception as e:
                    print(f"🔴 Audio processing exception: {e}\n")
                    import traceback
                    print(f"{traceback.format_exc()}\n")
                    logger.error(f"Audio processing error: {e}")
                    if not await safe_send({"type": "error", "message": str(e)}):
                        break

            elif msg_type == "test_answer":
                print(f"🟢 Test answer mesajı işleniyor\n")
                transcript = (data.get("text") or "").strip()
                if not transcript:
                    transcript = f"Dummy answer {session.answer_count + 1}: Silent test response."

                try:
                    logger.info(f"Test transcript: {transcript[:100]}...")

                    db = SessionLocal()
                    try:
                        current_q_num = session.answer_count + 1
                        question_text = interview_questions.get(current_q_num, {}).get("text", f"Question {current_q_num}")
                        answer_record = models.InterviewAnswer(
                            interview_id=interview_id,
                            question_order=current_q_num,
                            question_text=question_text,
                            answer_text=transcript,
                        )
                        db.add(answer_record)
                        db.commit()
                        logger.info(f"Saved test answer {current_q_num} to database")
                    except Exception as save_error:
                        logger.error(f"Error saving test answer: {save_error}")
                    finally:
                        db.close()

                    response_text, is_ended = session.handle_answer(transcript)

                    if is_ended:
                        update_interview_status("completed", "ws_test_auto_end")
                        if not await safe_send({
                            "type": "ended",
                            "message": "Mülakat tamamlandı. Teşekkür ederiz.",
                            "question": response_text,
                            "q_num": session.question_count,
                            "total": session.max_questions,
                            "transcript": transcript,
                        }):
                            break
                        break

                    if not await safe_send({
                        "type": "question",
                        "question": response_text,
                        "transcript": transcript,
                        "q_num": session.question_count,
                        "total": session.max_questions,
                        "phase": session.phase,
                    }):
                        break

                except Exception as e:
                    logger.error(f"Test answer processing error: {e}", exc_info=True)
                    if not await safe_send({"type": "error", "message": str(e)}):
                        break

            elif msg_type == "end":
                if session.phase != InterviewSession.PHASE_ENDED:
                    closing, _ = session.handle_answer("")
                    await safe_send({
                        "type": "ended",
                        "message": "Mülakat bitti.",
                        "question": closing,
                        "q_num": session.question_count,
                        "total": session.max_questions,
                    })

                update_interview_status("completed", "ws_user_end")

                break

    except WebSocketDisconnect:
        logger.info(f"WS disconnect: {interview_id}")
    except Exception as e:
        logger.error(f"WS unexpected error: {e}", exc_info=True)
