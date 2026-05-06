import os
import json
import base64
import logging
import tempfile
import wave
from typing import List, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

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


def _transcribe_pcm_b64(audio_b64: str, language: str = "tr") -> str:
    audio_bytes = base64.b64decode(audio_b64)
    if not audio_bytes or len(audio_bytes) < 3200:
        return ""

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
        return "".join(seg.text for seg in segments).strip()
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
    await websocket.accept()

    db = SessionLocal()
    interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
    
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
                except Exception as e:
                    logger.warning(f"CV okuma hatası: {e}")

    db.close()

    if not interview:
        await websocket.send_json({"type": "error", "message": "Mülakat bulunamadı"})
        return

    session = InterviewSession(interview, profile=profile_data)

    async def safe_send(payload: dict) -> bool:
        try:
            await websocket.send_json(payload)
            return True
        except (WebSocketDisconnect, RuntimeError):
            logger.info("WS send skipped (closed): interview_id=%s", interview_id)
            return False

    try:
        logger.info(f"Interview session started: interview_id={interview_id}")

        while True:
            try:
                raw = await websocket.receive_text()
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            except WebSocketDisconnect:
                logger.info(f"Client disconnected: {interview_id}")
                break
            except Exception as e:
                logger.error(f"receive_text error: {e}", exc_info=True)
                break

            msg_type = data.get("type")

            if msg_type == "init":
                session.domain = data.get("domain", session.domain)
                session.language = data.get("language", session.language)
                session.max_questions = data.get("max_questions", 5)
                session.answer_count = 0

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
                audio_b64 = data.get("audio")
                if not audio_b64:
                    continue

                try:
                    transcript = _transcribe_pcm_b64(audio_b64, language=session.language)

                    if not transcript:
                        await safe_send({
                            "type": "error",
                            "message": "Cevap net algılanamadı. Daha net konuşup tekrar deneyin.",
                        })
                        continue

                    logger.info(f"Transcription: {transcript[:100]}...")
                    response_text, is_ended = session.handle_answer(transcript)

                    if is_ended:
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
                    logger.error(f"Audio processing error: {e}")
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
                break

    except WebSocketDisconnect:
        logger.info(f"WS disconnect: {interview_id}")
    except Exception as e:
        logger.error(f"WS unexpected error: {e}", exc_info=True)
