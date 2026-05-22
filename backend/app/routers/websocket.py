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
    pause_frequency_score_from_pcm,
    pause_frequency_score_from_segments,
    pcm_duration_seconds,
    pcm_tone_variation_score,
    pcm_volume_stability_score,
    words_per_minute,
)
from ..database import SessionLocal
from .. import models
from .messages import _, get_lang_from_header

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
        raise RuntimeError("faster-whisper is not installed")
    if _WS_WHISPER_MODEL is None:
        _WS_WHISPER_MODEL = WhisperModel("base", device="cpu", compute_type="int8")
    return _WS_WHISPER_MODEL


def _transcribe_pcm_b64_with_metrics(audio_b64: str, language: str = "en") -> dict:
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
        # PCM-based pause detection: measures actual silence periods in raw audio,
        # giving per-answer variation instead of the flat 82 from segment gaps.
        pause = pause_frequency_score_from_pcm(audio_bytes)
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
        raise RuntimeError("Ollama python package is not installed")

    target_model = model or os.getenv("OLLAMA_MODEL", "llama3.1:8b")
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
    return False


class InterviewSession:
    """State machine for real-time interview flow."""

    PHASE_GREETING = "greeting"
    PHASE_QUESTIONS = "questions"
    PHASE_CLOSING = "closing"
    PHASE_ENDED = "ended"

    def __init__(self, interview, profile=None, prepared_questions=None):
        self.interview = interview
        self.profile = profile or {}
        self.domain = interview.domain or "general"
        self.language = interview.language or "en"
        self.base_questions = 7
        self.min_questions = 5
        self.max_questions = 12
        self.question_count = 0
        self.answer_count = 0
        self.short_answers = 0
        self.detailed_answers = 0
        self.used_followups_per_q = 0
        self.history: List[Dict] = []
        self.phase = self.PHASE_GREETING
        self.cv_context = ""
        if profile:
            cv_text = profile.get("cv_text", "") or ""
            dept = profile.get("department", "") or ""
            self.cv_context = f"Candidate Profile:\n- Department: {dept}\n- CV Summary: {cv_text[:800]}"
        self.company_context = (interview.company_context or "").strip()
        self.prepared_questions = []
        if prepared_questions:
            sorted_qs = sorted(prepared_questions.items(), key=lambda x: x[0])
            for order, q in sorted_qs:
                text = q.get("text", "").strip()
                if text:
                    self.prepared_questions.append({"order": order, "text": text})

    def _build_system_prompt(self) -> str:
        company_name = self.interview.company_name or "the company"
        department_name = self.interview.department_name or "Department"
        position = self.interview.position or "Position"
        interview_type = "Technical Interview" if self.domain == "technical" else "General Interview"

        context_block = ""
        if self.cv_context:
            context_block = f"\n\nCANDIDATE BACKGROUND (reference info for generating questions -- do not validate/compare answers against it):\n{self.cv_context}"

        extra_context = ""
        if self.company_context:
            extra_context = f"\n\nCOMPANY CONTEXT (reference info for generating questions):\n{self.company_context}"

        if self.domain == "technical":
            kategori_bolumu = """  1) Introduction & Self-Presentation (education, past experiences, who you are)
  2) Motivation & Career (why this role/department, career goals, 5-year plan)
  3) Position & Industry Knowledge (industry trends, company's position in the market)
  4) Technical Skills & Tool Knowledge (tools/technologies specific to the role and sector)
  5) Project Experience (managed projects, task distribution, deadlines)
  6) Problem Solving (challenges faced, approach, outcome)
  7) Team & Organization (teamwork, reporting structure)"""

            return f"""You are a real technical interviewer at {company_name}.
You are a technical expert who knows the position and sector well. Focus on assessing the candidate's technical knowledge and experience.
The interview language is STRICTLY ENGLISH. Do NOT use Turkish.

POSITION:
- Title: {position}
- Department: {department_name}
- Sector: {self.interview.sector or 'Not specified'}
- Type: {interview_type}
{context_block}{extra_context}

INTERVIEW FLOW:
- INTRODUCTION: Brief welcome, do NOT introduce yourself by name. Move directly to the first question.
- QUESTIONS: Ask the next prepared question from the list. Follow this ORDER:
{kategori_bolumu}
- CLOSING: When all prepared questions are done, short thank you and end.

RULES:
1. Speak ONLY in English.
2. Ask EXACTLY ONE question per turn.
3. NATURAL FLOW: Don't repeat the candidate's answer. You CAN reference their previous answer naturally.
4. NO OVERPRAISING: Don't use "amazing", "wonderful", "excellent" etc. Be professional and natural.
5. NO UNNECESSARY ACKNOWLEDGMENT: A simple "thanks" is enough, don't praise every answer.
6. SHORT & CLEAR: Max 2 sentences per question. No fluff.
7. CV REFERENCE RULE — CRITICAL: If you reference something from the candidate's CV that they have NOT mentioned during the interview, say "I see from your CV that..." or "According to your CV...". NEVER say "as you mentioned" or "you said" for CV information. Only use "as you mentioned" or "you said" if the candidate actually said it in this conversation.
8. The candidate is APPLYING to the company, NOT working there. Never say "at your company" as if they work there."""

        else:
            kategori_bolumu = """  1) Introduction & Self-Presentation (education, past experiences, how they describe themselves)
  2) Motivation & Interest (why this position/company, what drives them, curiosity to learn)
  3) Career Goals (short and long-term goals, where they see themselves in this role)
  4) Strengths & Growth Areas (self-awareness, what they do to improve)
  5) Company & Industry Knowledge (how well they know the company, their perspective on the sector, depth of research)
  6) Communication & Team Fit (how they work with others, handling disagreements, receiving feedback)
  7) Closing (any questions from the candidate, final impression)"""

            return f"""You are a real HR interviewer at {company_name}.
Focus on assessing the candidate's motivation, genuine interest in the role, cultural fit, and overall potential.
This is NOT a technical exam -- your goal is to understand who they are, what drives them, and how well they'd fit.
The interview language is STRICTLY ENGLISH. Do NOT use Turkish.

POSITION:
- Title: {position}
- Department: {department_name}
- Sector: {self.interview.sector or 'Not specified'}
- Type: {interview_type}
{context_block}{extra_context}

INTERVIEW FLOW:
- INTRODUCTION: Brief welcome, do NOT introduce yourself by name. Move directly to the first question.
- QUESTIONS: Ask the next prepared question from the list. Follow this ORDER:
{kategori_bolumu}
- CLOSING: When all prepared questions are done, short thank you and end.

RULES:
1. Speak ONLY in English.
2. Ask EXACTLY ONE question per turn.
3. NATURAL FLOW: Don't repeat the candidate's answer. You CAN reference their previous answer naturally.
4. NO OVERPRAISING: Don't use "amazing", "wonderful", "excellent" etc. Be professional and natural.
5. NO UNNECESSARY ACKNOWLEDGMENT: A simple "thanks" is enough, don't praise every answer.
6. SHORT & CLEAR: Max 2 sentences per question. No fluff.
7. CV REFERENCE RULE — CRITICAL: If you reference something from the candidate's CV that they have NOT mentioned during the interview, say "I see from your CV that..." or "According to your CV...". NEVER say "as you mentioned" or "you said" for CV information. Only use "as you mentioned" or "you said" if the candidate actually said it in this conversation.
8. FOCUS: Ask about motivation, interest, why they applied, and cultural fit. NOT technical tools or skills.
9. The candidate is APPLYING to the company, NOT working there. Never say "at your company" as if they work there."""

    def _get_fallback(self) -> str:
        if self.phase == self.PHASE_GREETING:
            return "Welcome! Could you briefly introduce yourself -- your education and who you are?"

        if self.phase == self.PHASE_CLOSING:
            return "Thank you for your time. The interview is now complete. We will get back to you soon."

        fallbacks = [
            "Can you give a concrete example and explain your exact actions?",
            "What was the most difficult part, and how did you handle it?",
            "What would you do differently if you faced the same situation again?",
            "How does this experience prepare you for this role?",
            "Thank you. Is there anything else you would like to add?",
        ]
        idx = min(max(0, self.question_count - 1), len(fallbacks) - 1)
        return fallbacks[idx]

    def _ask_ollama(self, prompt: str) -> str | None:
        # OPTIMIZATION: Ollama is heavy; use fallback questions if needed.
        # To disable Ollama, add True at the start of this function:
        # if True:  # Disable Ollama
        #     return None

        try:
            messages = [{"role": "system", "content": self._build_system_prompt()}]
            for h in self.history[-8:]:
                messages.append(h)
            messages.append({"role": "user", "content": prompt})

            response = _ollama_chat(
                model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
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
        first_q = ""
        if self.prepared_questions:
            first_q = self.prepared_questions[0]["text"]
        if not first_q:
            first_q = "Could you briefly introduce yourself and your relevant background?"

        starter = (
            "Start the interview with a brief welcome (do NOT introduce yourself by name). "
            "Then ask this EXACT first question -- do NOT change it, do NOT skip it, do NOT replace it with a different question:\n\n"
            f'"{first_q}"\n\n'
            "CRITICAL: You MUST ask this exact question as the first question. "
            "Do NOT ask about motivation, goals, or anything else first. "
            "The very first question MUST be about the candidate introducing themselves."
        )

        q = self._ask_ollama(starter)
        if not q or _looks_wrong_language(q, self.language):
            q = self._get_fallback()
        self.question_count = 1
        self.history.append({"role": "assistant", "content": q})
        return q

    def _answer_quality(self, transcript: str) -> dict:
        words = transcript.split()
        wc = len(words)
        low = transcript.lower()
        struggling_words = [
            "i don't know", "i'm not sure", "i don't remember", "pass", "next question",
        ]
        is_struggling = any(w in low for w in struggling_words)
        return {
            "word_count": wc,
            "is_short": wc < 25,
            "is_detailed": wc > 120,
            "is_struggling": is_struggling,
        }

    def handle_answer(self, transcript: str) -> tuple[str, bool]:
        """Phase 2: Process answer, generate next question. Returns (response, is_ended)."""
        self.answer_count += 1
        self.history.append({"role": "user", "content": transcript})

        q_quality = self._answer_quality(transcript)
        is_shallow = q_quality["is_short"] or q_quality["is_struggling"]
        logger.info(f"🔹 handle_answer: q#{self.question_count} answer#{self.answer_count} words={q_quality['word_count']} short={q_quality['is_short']} struggling={q_quality['is_struggling']} shallow={is_shallow} followups={self.used_followups_per_q}")

        # Which prepared question are we on?
        current_q_index = min(self.question_count - 1, len(self.prepared_questions) - 1) if self.prepared_questions else -1
        total_prepared = len(self.prepared_questions)

        # Check if we should ask a follow-up (shallow answer, haven't used follow-up yet for this question)
        if is_shallow and self.used_followups_per_q < 1 and current_q_index >= 0 and current_q_index < total_prepared:
            self.used_followups_per_q += 1
            q_text = self.prepared_questions[current_q_index]["text"]
            prompt = (
                f"Candidate's answer: {transcript}\n"
                f"The question was: {q_text}\n"
                "The candidate's answer was brief. Ask ONE short follow-up to get more detail, then we'll move to the next topic. Be natural."
            )
            logger.info(f"🔹 Follow-up triggered: q_index={current_q_index} followup={self.used_followups_per_q}")

            q = self._ask_ollama(prompt)
            if not q or _looks_wrong_language(q, self.language):
                q = "Could you tell me more about that?"
            self.history.append({"role": "assistant", "content": q})
            logger.info(f"🔹 Follow-up response: {q[:80]}")
            return q, False

        # Move to next prepared question
        logger.info(f"🔹 Moving to next question: current_q_index={current_q_index} -> next={current_q_index + 1} total={total_prepared}")
        self.used_followups_per_q = 0
        next_q_index = current_q_index + 1

        if next_q_index >= total_prepared:
            self.phase = self.PHASE_ENDED
            q = "Thank you for participating in this interview!"
            self.history.append({"role": "assistant", "content": q})
            return q, True

        next_q = self.prepared_questions[next_q_index]
        next_q_text = next_q["text"]
        self.question_count = next_q_index + 1

        prompt = (
            f"The candidate answered the previous question. "
            f"Now ask the following next question naturally, you may briefly acknowledge their answer first but keep it very short (1-2 words max):\n\n"
            f'"{next_q_text}"\n\n'
            "Ask this question. Do NOT change or replace it."
        )

        q = self._ask_ollama(prompt)
        if not q or _looks_wrong_language(q, self.language):
            q = next_q_text
        self.history.append({"role": "assistant", "content": q})
        return q, False


@router.websocket("/ws/interview/{interview_id}")
async def websocket_interview(websocket: WebSocket, interview_id: int):
    print(f"\n🔵🔵🔵 WS HANDLER START: interview_id={interview_id} 🔵🔵🔵\n")

    # Token check (from query param)
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Token required")
        return
    try:
        import jwt
        payload = jwt.decode(token, os.getenv("JWT_SECRET_KEY", "sizin-gizli-anahtar-buraya-degisitirin"), algorithms=["HS256"])
        ws_user_id = payload.get("user_id")
        if not ws_user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await websocket.accept()
    print(f"🔵 WebSocket accepted\n")
    logger.info(f"🔵 WebSocket opened: interview_id={interview_id}")
    ws_lang = get_lang_from_header(websocket.headers.get("accept-language"))

    print(f"🔵 Creating SessionLocal...\n")
    db = SessionLocal()
    print(f"🔵 SessionLocal created\n")

    try:
        print(f"🔵 Try block started\n")
        interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
        print(f"🔵 Interview query done: {interview is not None}\n")
        logger.info(f"Interview query done: {interview is not None}")

        if not interview:
            await websocket.send_json({"type": "error", "message": _("interview_not_found", ws_lang)})
            await websocket.close(code=4004)
            return

        # Check if the user in the token is the interview owner
        if interview.user_id != ws_user_id:
            await websocket.close(code=4003, reason="You do not have access to this interview")
            return

        # Fetch interview questions from database
        interview_questions = {}
        if interview:
            print(f"🔵 Loading interview questions...\n")
            iqs = db.query(models.InterviewQuestion).filter(
                models.InterviewQuestion.interview_id == interview_id
            ).order_by(models.InterviewQuestion.order).all()
            print(f"🔵 Interview questions loaded: {len(iqs)}\n")
            logger.info(f"Interview questions loaded: {len(iqs)}")
            for iq in iqs:
                question_text = iq.question_text or ""
                # Fix #2: question_text may be stored as JSON string {"text": "..."}
                if question_text and question_text.strip().startswith("{"):
                    try:
                        parsed = json.loads(question_text)
                        question_text = parsed.get("text", question_text)
                    except (json.JSONDecodeError, ValueError):
                        pass
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

        # Fetch profile and CV data
        profile_data = {}
        if interview:
            profile = db.query(models.Profile).filter(models.Profile.user_id == interview.user_id).first()
            if profile:
                profile_data = {
                    "university": profile.university or "",
                    "department": profile.department or "",
                    "cv_text": ""
                }
                # Read CV text if available
                if profile.cv_path:
                    from ..cv_read import read_cv_plaintext
                    cv_text = read_cv_plaintext(profile.cv_path)
                    if cv_text:
                        profile_data["cv_text"] = cv_text
                        logger.info(f"CV loaded: {len(cv_text)} characters")
                    else:
                        logger.warning(f"Could not read CV: {profile.cv_path}")

        print(f"🔵 Profile and CV loaded\n")
        if not interview:
            await websocket.send_json({"type": "error", "message": _("interview_not_found", ws_lang)})
            return

        iv_lang = interview.language or "en"
        if interview.status == "preparing":
            await websocket.send_json({"type": "error", "message": _("ws_not_ready", iv_lang)})
            return
        if interview.status == "preparation_failed":
            await websocket.send_json({"type": "error", "message": _("ws_prep_failed", iv_lang)})
            return

        print(f"🔵 Creating InterviewSession...\n")
        session = InterviewSession(interview, profile=profile_data, prepared_questions=interview_questions)
        print(f"🔵 InterviewSession created: domain={session.domain}, language={session.language}\n")
        logger.info(f"✅ Session created: domain={session.domain}, language={session.language}")
    except Exception as e:
        print(f"\n❌❌❌ EXCEPTION: {e}\n")
        import traceback
        print(f"\n{traceback.format_exc()}\n")
        logger.error(f"❌ WebSocket setup error: {e}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": f"{_('interview_not_found', ws_lang)}: {str(e)}"})
        except:
            pass
        return
    finally:
        print(f"🔵 Finally block: calling db.close()\n")
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
        print(f"\n🟢🟢🟢 MAIN LOOP STARTED: interview_id={interview_id} 🟢🟢🟢\n")
        logger.info(f"Interview session started: interview_id={interview_id}")

        while True:
            try:
                print(f"🟢 Waiting for message...\n")
                raw = await websocket.receive_text()
                print(f"🟢 Message received: {raw[:100]}\n")
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
                print(f"🟢 Processing init message\n")
                session.domain = data.get("domain", session.domain)
                session.language = data.get("language", session.language)
                session.base_questions = data.get("max_questions", 7)
                session.max_questions = max(session.min_questions, min(session.base_questions, session.max_questions))
                session.answer_count = 0
                # Clear any previous answers for this interview (in case of reconnection/restart)
                try:
                    answer_db = SessionLocal()
                    answer_db.query(models.InterviewAnswer).filter(
                        models.InterviewAnswer.interview_id == interview_id
                    ).delete()
                    answer_db.commit()
                    answer_db.close()
                    logger.info(f"Cleared previous answers for interview {interview_id}")
                except Exception as e:
                    logger.warning(f"Could not clear previous answers: {e}")
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
                print(f"🟢 Processing audio message\n")
                audio_b64 = data.get("audio")
                if not audio_b64:
                    print(f"🔴 No audio data\n")
                    continue

                try:
                    print(f"🟢 Generating transcript...\n")
                    tm = _transcribe_pcm_b64_with_metrics(audio_b64, language=session.language)
                    transcript = (tm.get("text") or "").strip()
                    print(f"🟢 Transcript: {transcript[:50]}\n")

                    if not transcript:
                        print(f"🔴 Transcript empty, AI asking again\n")
                        re_prompt = (
                            "The candidate's answer was not audible. "
                            "Politely ask them to repeat in a short, natural way."
                        )
                        re_ask = session._ask_ollama(re_prompt)
                        if not re_ask:
                            re_ask = "I couldn't hear you clearly, could you please repeat that?"
                        if not await safe_send({
                            "type": "question",
                            "question": re_ask,
                            "q_num": session.answer_count + 1,
                            "total": session.max_questions,
                            "phase": session.phase,
                        }):
                            break
                        continue

                    logger.info(f"Transcription: {transcript[:100]}...")

                    # Save answer to database BEFORE handle_answer increments counter
                    print(f"🟢 Opening database session\n")
                    db = SessionLocal()
                    try:
                        print(f"🟢 Saving answer\n")
                        # Fix #1 & #3: use question_count (which prepared question is being answered)
                        # rather than answer_count+1 (which overcounts due to follow-ups)
                        current_q_num = session.question_count
                        question_text = interview_questions.get(current_q_num, {}).get("text", f"Question {current_q_num}")

                        answer_record = models.InterviewAnswer(
                            interview_id=interview_id,
                            question_order=current_q_num,
                            question_text=question_text,
                            answer_text=transcript,
                            speech_rate_wpm=tm.get("speech_rate_wpm"),
                            pause_frequency_score=tm.get("pause_frequency_score"),
                        )
                        db.add(answer_record)
                        db.commit()
                        print(f"🟢 Answer saved: {current_q_num}\n")
                        logger.info(f"Saved answer {current_q_num} to database")
                    except Exception as save_error:
                        print(f"🔴 Save error: {save_error}\n")
                        logger.error(f"Error saving answer: {save_error}")
                    finally:
                        db.close()

                    print(f"🟢 Calling handle_answer\n")
                    response_text, is_ended = session.handle_answer(transcript)
                    print(f"🟢 handle_answer completed: is_ended={is_ended}\n")

                    if is_ended:
                        print(f"🟢 Interview ended!\n")
                        update_interview_status("analyzing", "ws_auto_end")

                        print(f"🟢 Sending ended message\n")
                        if not await safe_send({
                            "type": "ended",
                            "message": _("ws_completed", session.language),
                            "question": response_text,
                            "q_num": session.question_count,
                            "total": session.max_questions,
                            "transcript": transcript,
                        }):
                            break
                        break

                    print(f"🟢 Sending next question: q_num={session.question_count}\n")
                    if not await safe_send({
                        "type": "question",
                        "question": response_text,
                        "transcript": transcript,
                        "q_num": session.question_count,
                        "total": session.max_questions,
                        "phase": session.phase,
                    }):
                        print(f"🔴 safe_send failed\n")
                        break
                    print(f"🟢 Question sent!\n")

                except Exception as e:
                    print(f"🔴 Audio processing exception: {e}\n")
                    import traceback
                    print(f"{traceback.format_exc()}\n")
                    logger.error(f"Audio processing error: {e}")
                    if not await safe_send({"type": "error", "message": str(e)}):
                        break

            elif msg_type == "test_answer":
                print(f"🟢 Processing test answer message\n")
                transcript = (data.get("text") or "").strip()
                if not transcript:
                    transcript = f"Dummy answer {session.answer_count + 1}: Silent test response."

                try:
                    logger.info(f"Test transcript: {transcript[:100]}...")

                    db = SessionLocal()
                    try:
                        # Fix #1 & #3: use question_count (consistent with audio handler)
                        current_q_num = session.question_count
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
                        update_interview_status("analyzing", "ws_test_auto_end")
                        if not await safe_send({
                            "type": "ended",
                            "message": _("ws_completed", session.language),
                            "question": response_text,
                            "q_num": session.question_count,
                            "total": session.max_questions,
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
                    closing, _ended = session.handle_answer("")
                    await safe_send({
                        "type": "ended",
                        "message": _("ws_ended", session.language),
                        "question": closing,
                        "q_num": session.question_count,
                        "total": session.max_questions,
                    })

                update_interview_status("analyzing", "ws_user_end")

                break

    except WebSocketDisconnect:
        logger.info(f"WS disconnect: {interview_id}")
    except Exception as e:
        logger.error(f"WS unexpected error: {e}", exc_info=True)
