import asyncio
import os
import json
import base64
import logging
import tempfile
import time
import wave
from typing import List, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..analysis.speech_metrics import (
    pause_frequency_score_from_pcm,
    pcm_duration_seconds,
    words_per_minute,
)
from ..database import SessionLocal
from .. import models
from .messages import _
from .ollama_service import _ollama_chat

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

# Category → generation instruction (used in dynamic question generation)
_CATEGORY_PROMPTS = {
    # Technical
    "intro":       "Ask the candidate to introduce themselves: their educational background, any internships, university projects, or part-time work, and what led them to apply. The candidate may be a new graduate or intern — adjust accordingly.",
    "motivation":  "Ask specifically WHY they applied to THIS company and THIS role — what drew them here over other options. Focus on company and role fit, not career plans.",
    "industry":    "If the candidate mentioned a specific technical concept or challenge, ask a focused follow-up on that. If they were vague or said nothing technical, ask a standard industry question: how would they approach a common engineering challenge in this sector (e.g. scalability, data consistency, real-time processing).",
    "skills":      "If the candidate mentioned specific tools or technologies, go deeper — how they used it, what problem it solved, what trade-offs they encountered. If they were vague or said nothing specific, ask: what tools or technologies are they most comfortable with for this type of role? Do NOT assume or mention any technology they have not brought up themselves.",
    "project":     "If the candidate described a specific project, probe it: what was the hardest technical decision, how did they debug a problem, or what would they do differently. If they gave no project details, ask them to describe a technical challenge they faced — however small — and how they approached it.",
    "learning":    "If the candidate gave a specific learning example, probe it deeper — what they built, what they struggled with, what they discovered. If they were vague, ask: how do they approach learning a new technology from scratch, and what is the most recent thing they taught themselves.",
    "team":        "If the candidate mentioned a team experience, ask about a specific technical disagreement — architecture choice, tech stack, code review — and how they resolved it. If no team experience was mentioned, ask how they would handle a situation where they disagree with a senior engineer's technical decision.",
    # General
    "career":      "Ask about their near-term career plan — what they want to learn or achieve in the next 1-2 years, and how this specific role helps them get there. Do NOT ask about motivation or why they applied — that was already covered.",
    "strengths":   "Ask either about their greatest strength OR a real weakness they are working on — whichever feels more natural based on what the candidate has shared so far. Ask only ONE, not both.",
    "company":     "Ask a direct question about the sector and the company's position in it. For example: who are the main competitors, what differentiates this company, or what recent development in the sector caught their attention. Do NOT ask 'what do you find interesting' — probe actual knowledge.",
    "team_hr":     "Ask about a specific team experience from an internship, university group project, or part-time job. What was their role, what did they contribute, and how did they handle a disagreement or challenge within the team.",
}

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
        return {
            "text": text,
            "speech_rate_wpm": wpm,
            "pause_frequency_score": pause,
        }
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass



class InterviewSession:
    """State machine for real-time interview flow."""

    PHASE_GREETING = "greeting"
    PHASE_QUESTIONS = "questions"
    PHASE_ENDED = "ended"

    def __init__(self, interview, prepared_questions=None):
        self.interview = interview
        self.domain = interview.domain 
        self.language = interview.language or "en"
        self.question_count = 0
        self.answer_count = 0
        self.used_followups_per_q = 0
        self.history: List[Dict] = []
        self.phase = self.PHASE_GREETING
        self.last_question_text = ""  # for follow-up reference

        # CV is intentionally not used in question generation.
        # Questions are generated based on the conversation history only.

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
        sector = self.interview.sector or "Not specified"
        interview_type = "Technical Interview" if self.domain == "technical" else "General Interview"

        extra_context = ""
        if self.company_context:
            extra_context = f"\n\nCOMPANY CONTEXT (reference info for generating questions):\n{self.company_context}"

        position_block = f"""POSITION:
- Title: {position}
- Department: {department_name}
- Sector: {sector}
- Type: {interview_type}
{extra_context}"""

        common_rules = """RULES:
1. Ask EXACTLY ONE question per turn.
2. NATURAL FLOW: Reference what the candidate actually said in this conversation. Do NOT invent facts.
3. NO OVERPRAISING: Don't use "amazing", "wonderful", "excellent" etc. Be professional and natural.
4. NO UNNECESSARY ACKNOWLEDGMENT: Don't praise every answer. Move directly to the next question.
5. STICK TO CONVERSATION: Only refer to things the candidate has actually said in this interview. Never invent experiences they didn't mention.
6. OFF-TOPIC REDIRECT: If the candidate's answer is completely unrelated to the question, briefly acknowledge and redirect: ask them to answer the original question or move to the next relevant one.
7. The candidate is APPLYING to the company, NOT working there. Never say "at your company" as if they work there."""

        if self.domain == "technical":
            intro = f"""You are a real technical interviewer at {company_name}.
You are a technical expert who knows the position and sector well. Focus on assessing the candidate's technical knowledge and experience.
The interview language is STRICTLY ENGLISH. Do NOT use Turkish."""
            extra_rules = "\n8. NEVER ASSUME SKILLS: Do NOT assume the candidate knows any specific technology, language, or tool unless they explicitly mentioned it. If unsure, ask first."
            return f"{intro}\n\n{position_block}\n\n{common_rules}{extra_rules}"

        else:
            intro = f"""You are a real HR interviewer at {company_name}.
Focus on assessing the candidate's motivation, genuine interest in the role, cultural fit, and overall potential.
This is NOT a technical exam -- your goal is to understand who they are, what drives them, and how well they'd fit.
The interview language is STRICTLY ENGLISH. Do NOT use Turkish."""
            extra_rules = "\n8. FOCUS: Ask about motivation, interest, why they applied, and cultural fit. NOT technical tools or skills."
            return f"{intro}\n\n{position_block}\n\n{common_rules}{extra_rules}"

    def _ask_ollama(self, prompt: str) -> str | None:
        try:
            messages = [{"role": "system", "content": self._build_system_prompt()}]
            for h in self.history[-8:]:
                messages.append(h)
            messages.append({"role": "user", "content": prompt})

            response = _ollama_chat(
                messages=messages,
                temperature=0.55,
                num_predict=300,
            )
            out = (response.get("message", {}).get("content", "") or "").strip()
            return " ".join(out.split())
        except Exception as e:
            logger.error(f"Ollama LLM error: {e}")
            return None

    def _generate_question_for_category(self, category: str) -> str:
        """Generate a personalized question for the given category using conversation history."""
        instruction = _CATEGORY_PROMPTS.get(category, f"Ask a relevant question about the candidate's {category}.")

        # Inject company/sector context for company category
        if category == "company":
            company_name = self.interview.company_name or "the company"
            sector = self.interview.sector or "this sector"
            instruction = (
                f"Ask the candidate directly about their knowledge of {company_name}'s position in the {sector} sector. "
                f"Probe for specific knowledge: Who are the main competitors? What differentiates {company_name}? "
                f"What recent development in the sector have they noticed? Pick ONE of these angles and ask it directly."
            )

        # Extract key points from the last 2 candidate answers to drive adaptation
        recent_context = ""
        user_turns = [h["content"] for h in self.history if h["role"] == "user"]
        if user_turns:
            last_answers = user_turns[-2:]
            snippets = " | ".join(a[:120] for a in last_answers)
            recent_context = f"\nCandidate recently said: \"{snippets}\"\nBuild your question on these specifics — reference what they actually mentioned.\n"

        # Inject last 3 asked questions in full to prevent repetition
        asked_qs = [h["content"] for h in self.history if h["role"] == "assistant"][-3:]
        if asked_qs:
            topics_str = "\n- ".join(asked_qs)
            recent_context += f"\nYou already asked these questions — do NOT ask about the same topic again:\n- {topics_str}\n"

        prompt = (
            f"Category instruction: {instruction}\n"
            f"{recent_context}\n"
            "Generate ONE focused interview question for this category. "
            "Do not repeat a topic already discussed. "
            "Ask ONLY ONE question. No preamble, no praise. RESPOND IN ENGLISH ONLY."
        )

        q = self._ask_ollama(prompt)
        if not q:
            # fallback to category description itself as a plain question
            fallbacks = {
                "intro":     "Could you walk us through your background and what led you to apply for this position?",
                "motivation":"What motivated you to apply for this role, and where do you see yourself in 5 years?",
                "industry":  "What do you know about the current trends in this industry and how this company fits into that landscape?",
                "skills":    "Which tools and technologies relevant to this position are you most comfortable with?",
                "project":   "Can you describe a project you worked on, how tasks were distributed, and how you handled deadlines?",
                "learning":  "How do you keep up with new technologies, and can you give an example of learning something new for a project?",
                "team":      "How do you typically collaborate with teammates, and how do you handle disagreements within a team?",
                "career":    "Where do you see yourself in the next few years, and how does this role fit into your career path?",
                "strengths": "What would you say is your greatest strength, and is there an area you are actively working to improve?",
                "company":   "How familiar are you with our company, and what do you find most interesting about this sector?",
                "team_hr":   "Can you describe a team experience where you contributed to a shared goal and handled a challenge or disagreement?",
            }
            q = fallbacks.get(category, "Could you tell me more about your experience in this area?")
        return q

    def get_greeting(self) -> str:
        """Phase 1: Greeting + hardcoded intro question."""
        self.phase = self.PHASE_QUESTIONS
        company_name = self.interview.company_name or "our company"
        position = self.interview.position or "this position"
        q = (
            f"Welcome to {company_name} for the {position} position. "
            f"Could you start by introducing yourself — your educational background, "
            f"any relevant experience such as internships or projects, and what brought you to apply for this role?"
        )
        self.last_question_text = q
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
            "is_short": wc < 35,
            "is_struggling": is_struggling,
        }

    def handle_answer(self, transcript: str) -> tuple[str, bool]:
        """Phase 2: Process answer, generate next question. Returns (response, is_ended)."""
        self.answer_count += 1
        self.history.append({"role": "user", "content": transcript})

        q_quality = self._answer_quality(transcript)
        is_shallow = q_quality["is_short"]
        logger.info(f"🔹 handle_answer: q#{self.question_count} answer#{self.answer_count} words={q_quality['word_count']} short={q_quality['is_short']} struggling={q_quality['is_struggling']} shallow={is_shallow} followups={self.used_followups_per_q}")

        # Which prepared question are we on?
        current_q_index = min(self.question_count - 1, len(self.prepared_questions) - 1) if self.prepared_questions else -1
        total_prepared = len(self.prepared_questions)

        # Categories where follow-up is allowed (0-based index)
        # Technical:  4=Project Experience, 5=Learning & Adaptability, 6=Team & Organization
        # General:    0=Introduction, 3=Strengths & Growth Areas, 5=Communication & Team Fit
        if self.domain == "technical":
            followup_allowed_indices = {4, 5, 6}
        else:
            followup_allowed_indices = {0, 3, 5}

        # Follow-up: short answer on allowed category
        if is_shallow and self.used_followups_per_q < 1 and current_q_index in followup_allowed_indices and current_q_index < total_prepared:
            self.used_followups_per_q += 1
            current_category = self.prepared_questions[current_q_index]["text"] if self.prepared_questions else ""

            prompt = (
                f"The candidate was asked: {self.last_question_text}\n"
                f"They answered briefly: {transcript}\n"
                "Their answer was too short. Ask ONE natural follow-up question that goes deeper on exactly what they mentioned. "
                "Do NOT introduce a new topic. Do NOT drift. Do NOT praise. RESPOND IN ENGLISH ONLY."
            )
            logger.info(f"🔹 Follow-up triggered: q_index={current_q_index} category={current_category}")
            q = self._ask_ollama(prompt)
            if not q:
                q = "Could you elaborate on that a bit more?"
            self.history.append({"role": "assistant", "content": q})
            return q, False

        # Move to next category
        self.used_followups_per_q = 0
        next_q_index = current_q_index + 1
        logger.info(f"🔹 Moving to category index {next_q_index} / {total_prepared}")

        if next_q_index >= total_prepared:
            self.phase = self.PHASE_ENDED
            q = "Thank you for your time and for sharing your experiences with us."
            self.history.append({"role": "assistant", "content": q})
            return q, True

        next_category = self.prepared_questions[next_q_index]["text"]
        self.question_count = next_q_index + 1

        q = self._generate_question_for_category(next_category)
        self.last_question_text = q
        self.history.append({"role": "assistant", "content": q})
        return q, False


@router.websocket("/ws/interview/{interview_id}")
async def websocket_interview(websocket: WebSocket, interview_id: int):
    logger.info("WebSocket handler start: interview_id=%s", interview_id)

    await websocket.accept()
    logger.info("WebSocket accepted: interview_id=%s", interview_id)

    # First frame must be init + token (avoid putting JWT in query string).
    try:
        raw_init = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        init_data = json.loads(raw_init)
    except asyncio.TimeoutError:
        await websocket.close(code=4001, reason="Init timeout")
        return
    except Exception:
        await websocket.close(code=4001, reason="Init payload required")
        return

    if init_data.get("type") != "init":
        await websocket.close(code=4001, reason="Init payload required")
        return

    token = (init_data.get("token") or "").strip()
    if not token:
        await websocket.close(code=4001, reason="Token required")
        return

    try:
        import jwt
        payload = jwt.decode(token, os.getenv("JWT_SECRET_KEY"), algorithms=["HS256"])
        ws_user_id = payload.get("user_id")
        if not ws_user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    db = SessionLocal()

    try:
        interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()

        if not interview:
            await websocket.send_json({"type": "error", "message": _("interview_not_found")})
            await websocket.close(code=4004)
            return

        # Check if the user in the token is the interview owner
        if interview.user_id != ws_user_id:
            await websocket.close(code=4003, reason="You do not have access to this interview")
            return

        # Fetch interview questions from database
        interview_questions = {}
        if interview:
            iqs = db.query(models.InterviewQuestion).filter(
                models.InterviewQuestion.interview_id == interview_id
            ).order_by(models.InterviewQuestion.order).all()
            logger.info("Interview questions loaded: %d", len(iqs))
            for iq in iqs:
                question_text = iq.question_text or ""
                interview_questions[iq.order] = {
                    "text": question_text,
                    "id": iq.id
                }

        if not interview:
            await websocket.send_json({"type": "error", "message": _("interview_not_found")})
            return

        if interview.status == "preparing":
            await websocket.send_json({"type": "error", "message": _("ws_not_ready")})
            return
        if interview.status == "preparation_failed":
            await websocket.send_json({"type": "error", "message": _("ws_prep_failed")})
            return

        session = InterviewSession(interview, prepared_questions=interview_questions)
        session.answer_count = 0
    except Exception as e:
        logger.error("WebSocket setup error: %s", e, exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": f"{_('interview_not_found')}: {str(e)}"})
        except Exception:
            pass
        return
    finally:
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
        logger.info("Interview session started: interview_id=%s", interview_id)

        session_start_time: float | None = None
        last_q_video_offset = 0.0

        # Clear any previous answers for this interview (in case of reconnection/restart)
        try:
            answer_db = SessionLocal()
            answer_db.query(models.InterviewAnswer).filter(
                models.InterviewAnswer.interview_id == interview_id
            ).delete()
            answer_db.commit()
            answer_db.close()
            logger.info("Cleared previous answers for interview %s", interview_id)
        except Exception as e:
            logger.warning("Could not clear previous answers: %s", e)

        update_interview_status("in_progress", "ws_init")
        session_start_time = time.time()
        last_q_video_offset = 0.0
        greeting = session.get_greeting()
        if not await safe_send({
            "type": "question",
            "question": greeting,
        }):
            return

        while True:
            try:
                raw = await websocket.receive_text()
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            except WebSocketDisconnect:
                logger.info("Client disconnected: interview_id=%s", interview_id)
                break
            except Exception as e:
                logger.error("receive_text error: %s", e, exc_info=True)
                break

            msg_type = data.get("type")

            if msg_type == "init":
                # Session already initialized on first frame.
                continue

            elif msg_type == "audio":
                audio_b64 = data.get("audio")
                if not audio_b64:
                    continue

                try:
                    tm = _transcribe_pcm_b64_with_metrics(audio_b64, language=session.language)
                    transcript = (tm.get("text") or "").strip()

                    if not transcript:
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
                        }):
                            break
                        continue

                    logger.info(f"Transcription: {transcript[:100]}...")

                    video_end_sec = (
                        time.time() - session_start_time
                        if session_start_time is not None
                        else None
                    )

                    db = SessionLocal()
                    try:
                        current_q_num = session.question_count
                        question_text = session.last_question_text or interview_questions.get(current_q_num, {}).get("text", f"Question {current_q_num}")

                        answer_record = models.InterviewAnswer(
                            interview_id=interview_id,
                            question_order=current_q_num,
                            question_text=question_text,
                            answer_text=transcript,
                            speech_rate_wpm=tm.get("speech_rate_wpm"),
                            pause_frequency_score=tm.get("pause_frequency_score"),
                            video_start_second=last_q_video_offset,
                            video_end_second=video_end_sec,
                        )
                        db.add(answer_record)
                        db.commit()
                        logger.info("Saved answer %d for interview %s", current_q_num, interview_id)
                    except Exception as save_error:
                        logger.error("Error saving answer: %s", save_error)
                    finally:
                        db.close()

                    response_text, is_ended = session.handle_answer(transcript)

                    if is_ended:
                        update_interview_status("analyzing", "ws_auto_end")
                        if not await safe_send({
                            "type": "ended",
                            "message": _("ws_completed"),
                            "question": response_text,
                        }):
                            break
                        break

                    if not await safe_send({
                        "type": "question",
                        "question": response_text,
                    }):
                        break

                    if session_start_time is not None:
                        last_q_video_offset = time.time() - session_start_time

                except Exception as e:
                    logger.error("Audio processing error: %s", e, exc_info=True)
                    if not await safe_send({"type": "error", "message": str(e)}):
                        break

    except WebSocketDisconnect:
        logger.info(f"WS disconnect: {interview_id}")
    except Exception as e:
        logger.error(f"WS unexpected error: {e}", exc_info=True)
