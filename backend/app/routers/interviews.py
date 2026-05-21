import random
import json
import logging
from pathlib import Path
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.requests import Request

from ..database import SessionLocal
from .. import models
from .auth import get_current_user, get_db
from .ollama_service import generate_questions, fallback_questions, research_company, chat_response
from ..cv_read import read_cv_plaintext
from ..analysis import stt, scoring
from .messages import _, get_lang_from_header

logger = logging.getLogger(__name__)

router = APIRouter()
ALLOWED_INTERVIEW_STATUSES = {
    "created",
    "preparing",
    "ready",
    "preparation_failed",
    "in_progress",
    "analyzing",
    "analyzed",
    "analysis_failed",
}


@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    categories = db.query(models.Category).all()
    return [{"id": c.id, "name": c.name, "description": c.description} for c in categories]


class InterviewCreate(BaseModel):
    title: str
    domain: str
    language: str
    company_name: str | None = None
    department_name: str | None = None
    position: str | None = None
    sector: str | None = None


@router.post("/interviews")
def create_interview(
    payload: InterviewCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    request: Request = None,
):
    lang = get_lang_from_header(request.headers.get("accept-language") if request else None)
    profile = db.query(models.Profile).filter(models.Profile.user_id == current_user.id).first()
    if not profile or not getattr(profile, "cv_path", None):
        raise HTTPException(status_code=400, detail=_("cv_required", lang))

    cn = (payload.company_name or "").strip()
    dn = (payload.department_name or "").strip()
    pos = (payload.position or "").strip()
    sec = (payload.sector or "").strip()
    if not cn or not dn or not pos or not sec:
        raise HTTPException(status_code=400, detail=_("fields_required", lang))

    new_interview = models.Interview(
        user_id=current_user.id,
        title=payload.title,
        domain=payload.domain,
        language=payload.language,
        company_name=cn,
        department_name=dn,
        position=pos,
        sector=sec,
        status="preparing",
    )
    db.add(new_interview)
    db.commit()
    db.refresh(new_interview)

    cv_path = profile.cv_path
    background_tasks.add_task(
        _prepare_interview_background,
        interview_id=new_interview.id,
        position=pos,
        company_name=cn,
        department_name=dn,
        domain=payload.domain,
        language=payload.language,
        sector=sec,
        profile_university=profile.university,
        profile_department=profile.department,
        profile_class_year=profile.class_year,
        cv_path=cv_path,
    )

    return {
        "id": new_interview.id,
        "title": new_interview.title,
        "domain": new_interview.domain,
        "language": new_interview.language,
        "status": "preparing",
        "created_at": new_interview.created_at,
    }


@router.post("/interviews/{interview_id}/retry-prep")
def retry_preparation(
    interview_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    request: Request = None,
):
    lang = get_lang_from_header(request.headers.get("accept-language") if request else None)
    interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail=_("interview_not_found", lang))
    if interview.user_id != current_user.id:
        raise HTTPException(status_code=403, detail=_("not_authorized", lang))
    if interview.status != "preparation_failed":
        raise HTTPException(status_code=400, detail=_("not_preparation_failed", lang))

    db.query(models.InterviewQuestion).filter(
        models.InterviewQuestion.interview_id == interview_id
    ).delete()
    interview.status = "preparing"
    interview.preparation_error = None
    db.commit()
    db.refresh(interview)

    profile = db.query(models.Profile).filter(models.Profile.user_id == current_user.id).first()
    cv_path = profile.cv_path if profile else None

    background_tasks.add_task(
        _prepare_interview_background,
        interview_id=interview.id,
        position=interview.position or "",
        company_name=interview.company_name or "",
        department_name=interview.department_name or "",
        domain=interview.domain,
        language=interview.language,
        sector=interview.sector or "",
        profile_university=profile.university if profile else None,
        profile_department=profile.department if profile else None,
        profile_class_year=profile.class_year if profile else None,
        cv_path=cv_path,
    )

    return {"id": interview.id, "status": "preparing"}


def _prepare_interview_background(
    *,
    interview_id: int,
    position: str,
    company_name: str,
    department_name: str,
    domain: str,
    language: str,
    sector: str | None,
    profile_university: str | None,
    profile_department: str | None,
    profile_class_year: str | None,
    cv_path: str | None,
):
    """Background task: company research → question generation → ready."""
    logger.info(f"Background preparation started for interview {interview_id}")
    db = SessionLocal()
    try:
        interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
        if not interview:
            logger.error(f"Interview {interview_id} not found in background task")
            return

        # Step 1: Research company
        context = research_company(
            company_name=company_name,
            sector=sector,
            department_name=department_name,
            position=position,
        )
        if context:
            interview.company_context = context
            db.commit()
            logger.info(f"Company context saved for interview {interview_id}: {len(context)} chars")

        # Step 2: Read CV
        cv_text = None
        if cv_path:
            cv_text = read_cv_plaintext(cv_path)

        # Step 3: Generate questions
        target_n = random.randint(5, 7)
        ai_list = generate_questions(
            position=position,
            company_name=company_name,
            department_name=department_name,
            domain=domain,
            sector=sector,
            cv_text=cv_text,
            profile_university=profile_university,
            profile_department=profile_department,
            profile_class_year=profile_class_year,
            company_context=context,
            n_questions=target_n,
        )

        if not ai_list:
            logger.warning("Ollama question generation returned empty; using fallback.")
            ai_list = fallback_questions(domain, target_n)

        if ai_list:
            order = 1
            for item in ai_list[:target_n]:
                text = (item.get("text") or "").strip()[:1024]
                if not text:
                    continue
                db.add(
                    models.InterviewQuestion(
                        interview_id=interview_id,
                        question_id=None,
                        question_text=text,
                        order=order,
                    )
                )
                order += 1

        # Step 4: Mark as ready
        interview.status = "ready"
        db.commit()
        logger.info(f"Interview {interview_id} background preparation completed. Questions: {order - 1}")

    except Exception as e:
        logger.error(f"Background preparation failed for interview {interview_id}: {e}", exc_info=True)
        try:
            interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
            if interview:
                interview.status = "preparation_failed"
                interview.preparation_error = str(e)[:2000]
                db.commit()
        except Exception as inner:
            logger.error(f"Failed to mark interview {interview_id} as failed: {inner}")
    finally:
        db.close()



@router.get("/interviews")
def list_interviews(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    interviews = db.query(models.Interview).filter(models.Interview.user_id == current_user.id).order_by(models.Interview.created_at.desc()).all()
    return [
        {
            "id": i.id,
            "title": i.title,
            "domain": i.domain,
            "language": i.language,
            "status": i.status,
            "created_at": i.created_at,
        }
        for i in interviews
    ]


@router.delete("/interviews/{interview_id}")
def delete_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    request: Request = None,
):
    lang = get_lang_from_header(request.headers.get("accept-language") if request else None)
    interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail=_("interview_not_found", lang))
    if interview.user_id != current_user.id:
        raise HTTPException(status_code=403, detail=_("access_denied", lang))
    db.query(models.InterviewQuestion).filter(models.InterviewQuestion.interview_id == interview_id).delete(synchronize_session=False)
    db.query(models.InterviewAnswer).filter(models.InterviewAnswer.interview_id == interview_id).delete(synchronize_session=False)
    db.query(models.Transcript).filter(models.Transcript.interview_id == interview_id).delete(synchronize_session=False)
    db.query(models.Feedback).filter(models.Feedback.interview_id == interview_id).delete(synchronize_session=False)
    if interview.video_path:
        video_file = Path(interview.video_path)
        if video_file.exists():
            video_file.unlink()
    db.delete(interview)
    db.commit()
    return {"detail": "Interview deleted."}


class InterviewStatusUpdate(BaseModel):
    status: str


@router.post("/interviews/{interview_id}/status")
def update_interview_status(
    interview_id: int,
    payload: InterviewStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    request: Request = None,
):
    lang = get_lang_from_header(request.headers.get("accept-language") if request else None)
    interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail=_("interview_not_found", lang))
    if interview.user_id != current_user.id:
        raise HTTPException(status_code=403, detail=_("access_denied", lang))
    if payload.status not in ALLOWED_INTERVIEW_STATUSES:
        raise HTTPException(status_code=400, detail=_("invalid_status", lang))
    interview.status = payload.status
    db.commit()
    db.refresh(interview)
    return {"id": interview.id, "status": interview.status}


UPLOAD_INTERVIEWS_DIR = Path("uploads") / "interviews"


@router.post("/interviews/{interview_id}/video")
async def upload_interview_video(
    interview_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    request: Request = None,
):
    lang = get_lang_from_header(request.headers.get("accept-language") if request else None)
    interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail=_("interview_not_found", lang))
    if interview.user_id != current_user.id:
        raise HTTPException(status_code=403, detail=_("access_denied", lang))

    allowed_types = {"video/webm", "video/mp4", "video/x-matroska"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only video/webm, video/mp4 or video/mkv files are allowed.")

    UPLOAD_INTERVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    interview_dir = UPLOAD_INTERVIEWS_DIR / str(interview_id)
    interview_dir.mkdir(parents=True, exist_ok=True)

    safe_name = (file.filename or "interview.webm").replace("/", "_")
    target_path = interview_dir / safe_name

    data = await file.read()
    target_path.write_bytes(data)
    interview.status = "analyzing"
    db.commit()

    try:
        transcript_text, duration, _ignored1, _ignored2 = stt.get_transcript(interview_id, str(target_path))
        if transcript_text:
            analysis = scoring.score_transcript(transcript_text, duration, language=interview.language or "tr")

            db.add(models.Transcript(
                interview_id=interview_id,
                text=transcript_text[:5000],
                duration_seconds=duration,
            ))

            import json
            feedback_row = db.query(models.Feedback).filter(
                models.Feedback.interview_id == interview_id
            ).order_by(models.Feedback.created_at.desc(), models.Feedback.id.desc()).first()
            if not feedback_row:
                feedback_row = models.Feedback(interview_id=interview_id)
                db.add(feedback_row)
            feedback_row.metrics_json = json.dumps(dict(analysis["scores"]))
            feedback_row.summary = analysis.get("summary", "")[:1000]
            feedback_row.strengths = analysis.get("strengths", "")[:2000]
            feedback_row.improvements = analysis.get("improvements", "")[:2000]
            scores = analysis.get("scores", {}) if isinstance(analysis, dict) else {}
            overall = scores.get("overall")
            length = scores.get("length")
            speaking_rate = scores.get("speaking_rate")
            pause_control = scores.get("pause_control")

            # Populate score columns for consistent API/UI rendering.
            feedback_row.overall_score = int(overall) if overall is not None else None
            feedback_row.content_quality_score = int(length) if length is not None else None
            if speaking_rate is not None or pause_control is not None:
                parts = [p for p in [speaking_rate, pause_control] if p is not None]
                feedback_row.speech_quality_score = int(sum(parts) / len(parts))
            else:
                feedback_row.speech_quality_score = None
            # We do not have true nonverbal analysis in this flow; use overall as neutral fallback.
            feedback_row.nonverbal_score = int(overall) if overall is not None else None

            # Fill per-answer scores on interview_answers (WS path); video STT only updated Feedback before.
            from .analysis import apply_content_metrics_to_interview_answers

            apply_content_metrics_to_interview_answers(db, interview)

        interview.status = "analyzed"
        db.commit()
    except Exception as e:
        print(f"STT/Analysis error: {e}")
        interview.status = "analysis_failed"
        db.commit()

    return {
        "detail": "Video kaydedildi.",
        "filename": safe_name,
        "path": str(target_path),
    }


@router.get("/interviews/{interview_id}")
def get_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    request: Request = None,
):
    lang = get_lang_from_header(request.headers.get("accept-language") if request else None)
    interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail=_("interview_not_found", lang))
    if interview.user_id != current_user.id:
        raise HTTPException(status_code=403, detail=_("access_denied", lang))

    iqs = db.query(models.InterviewQuestion).filter(models.InterviewQuestion.interview_id == interview_id).order_by(models.InterviewQuestion.order).all()
    questions = []
    for iq in iqs:
        text = None
        if iq.question_id is not None:
            q = db.query(models.Question).filter(models.Question.id == iq.question_id).first()
            if q:
                text = q.text
        elif iq.question_text:
            text = iq.question_text
        if text:
            questions.append({"order": iq.order, "text": text})

    transcript_row = db.query(models.Transcript).filter(
        models.Transcript.interview_id == interview_id
    ).order_by(models.Transcript.id.desc()).first()
    transcript = transcript_row.text if transcript_row else None
    duration = transcript_row.duration_seconds if transcript_row else None

    feedback_row = db.query(models.Feedback).filter(
        models.Feedback.interview_id == interview_id
    ).order_by(models.Feedback.created_at.desc(), models.Feedback.id.desc()).first()
    feedback = None
    if feedback_row:
        feedback = {
            "metrics_json": feedback_row.metrics_json,
            "summary": feedback_row.summary,
            "strengths": feedback_row.strengths,
            "improvements": feedback_row.improvements,
        }

    answers = db.query(models.InterviewAnswer).filter(
        models.InterviewAnswer.interview_id == interview_id
    ).order_by(models.InterviewAnswer.question_order).all()
    answers_data = [
        {
            "question_order": a.question_order,
            "question_text": a.question_text,
            "answer_text": a.answer_text,
        }
        for a in answers
    ]

    return {
        "id": interview.id,
        "user_id": interview.user_id,
        "title": interview.title,
        "domain": interview.domain,
        "language": interview.language,
        "status": interview.status,
        "created_at": interview.created_at,
        "company_context": interview.company_context,
        "preparation_error": interview.preparation_error,
        "questions": questions,
        "transcript": transcript,
        "duration_seconds": duration,
        "feedback": feedback,
        "answers": answers_data,
    }


class ChatMessage(BaseModel):
    message: str


@router.post("/interviews/{interview_id}/chat")
def chat(
    interview_id: int,
    payload: ChatMessage,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    request: Request = None,
):
    lang = get_lang_from_header(request.headers.get("accept-language") if request else None)
    interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail=_("interview_not_found", lang))
    if interview.user_id != current_user.id:
        raise HTTPException(status_code=403, detail=_("access_denied", lang))

    transcript_row = db.query(models.Transcript).filter(models.Transcript.interview_id == interview_id).first()
    feedback_row = db.query(models.Feedback).filter(models.Feedback.interview_id == interview_id).first()
    transcript = (transcript_row.text or "") if transcript_row else ""
    summary = (feedback_row.summary or "") if feedback_row else ""
    strengths = (feedback_row.strengths or "") if feedback_row else ""
    improvements = (feedback_row.improvements or "") if feedback_row else ""

    user_msg = (payload.message or "").strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail=_("empty_message", lang))

    reply = chat_response(transcript, summary, strengths, improvements, user_msg)
    return {"reply": reply}
