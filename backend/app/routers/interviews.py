import random
import json
import logging
from pathlib import Path
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import SessionLocal
from .. import models
from .auth import get_current_user, require_admin, get_db
from .ollama_service import generate_questions, fallback_questions, chat_response
from ..analysis import stt, scoring

logger = logging.getLogger(__name__)

router = APIRouter()
ALLOWED_INTERVIEW_STATUSES = {
    "created",
    "in_progress",
    "completed",
    "analyzing",
    "analyzed",
    "analysis_failed",
}


@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    categories = db.query(models.Category).all()
    return [{"id": c.id, "name": c.name, "description": c.description} for c in categories]


class QuestionCreate(BaseModel):
    text: str
    category_id: int
    language: str
    difficulty: int | None = None
    is_active: int = 1


class QuestionUpdate(BaseModel):
    text: str | None = None
    category_id: int | None = None
    language: str | None = None
    difficulty: int | None = None
    is_active: int | None = None


@router.get("/questions")
def get_questions(
    category_id: int | None = None,
    language: str | None = None,
    is_active: int | None = None,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(require_admin),
):
    query = db.query(models.Question)
    if category_id is not None:
        query = query.filter(models.Question.category_id == category_id)
    if language is not None:
        query = query.filter(models.Question.language == language)
    if is_active is not None:
        query = query.filter(models.Question.is_active == is_active)

    questions = query.all()
    creator_ids = {q.created_by for q in questions if q.created_by}
    creators = db.query(models.User).filter(models.User.id.in_(creator_ids)).all() if creator_ids else []
    creator_emails = {u.id: u.email for u in creators}
    return [
        {
            "id": q.id,
            "text": q.text,
            "category_id": q.category_id,
            "language": q.language,
            "difficulty": q.difficulty,
            "is_active": q.is_active,
            "created_by": q.created_by,
            "created_at": q.created_at.isoformat() if q.created_at else None,
            "created_by_email": creator_emails.get(q.created_by) if q.created_by else None,
        }
        for q in questions
    ]


@router.post("/questions")
def create_question(
    payload: QuestionCreate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(require_admin),
):
    new_q = models.Question(
        text=payload.text,
        category_id=payload.category_id,
        language=payload.language,
        difficulty=payload.difficulty,
        is_active=payload.is_active,
        created_by=current_admin.id,
    )
    db.add(new_q)
    db.commit()
    db.refresh(new_q)
    return {
        "id": new_q.id,
        "text": new_q.text,
        "category_id": new_q.category_id,
        "language": new_q.language,
        "difficulty": new_q.difficulty,
        "is_active": new_q.is_active,
        "created_by": new_q.created_by,
        "created_at": new_q.created_at.isoformat() if new_q.created_at else None,
        "created_by_email": current_admin.email,
    }


@router.delete("/questions/{question_id}")
def delete_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(require_admin),
):
    q = db.query(models.Question).filter(models.Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Soru bulunamadı")
    db.query(models.InterviewQuestion).filter(models.InterviewQuestion.question_id == question_id).delete(synchronize_session=False)
    db.delete(q)
    db.commit()
    return {"detail": "Soru silindi."}


@router.put("/questions/{question_id}")
def update_question(
    question_id: int,
    payload: QuestionUpdate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(require_admin),
):
    q = db.query(models.Question).filter(models.Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Soru bulunamadı")
    if payload.text is not None:
        q.text = payload.text
    if payload.category_id is not None:
        q.category_id = payload.category_id
    if payload.language is not None:
        q.language = payload.language
    if payload.difficulty is not None:
        q.difficulty = payload.difficulty
    if payload.is_active is not None:
        q.is_active = payload.is_active
    db.commit()
    db.refresh(q)
    return {
        "id": q.id,
        "text": q.text,
        "category_id": q.category_id,
        "language": q.language,
        "difficulty": q.difficulty,
        "is_active": q.is_active,
    }


class InterviewCreate(BaseModel):
    title: str
    domain: str
    language: str
    company_name: str | None = None
    department_name: str | None = None
    position: str | None = None


@router.post("/interviews")
def create_interview(
    payload: InterviewCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    profile = db.query(models.Profile).filter(models.Profile.user_id == current_user.id).first()
    if not profile or not getattr(profile, "cv_path", None):
        raise HTTPException(status_code=400, detail="Mülakat oluşturmak için önce profilinize CV yüklemelisiniz.")

    cn = (payload.company_name or "").strip()
    dn = (payload.department_name or "").strip()
    pos = (payload.position or "").strip()
    if not cn or not dn or not pos:
        raise HTTPException(status_code=400, detail="Şirket, departman ve pozisyon alanları zorunludur.")

    new_interview = models.Interview(
        user_id=current_user.id,
        title=payload.title,
        domain=payload.domain,
        language=payload.language,
        company_name=cn,
        department_name=dn,
        position=pos,
    )
    db.add(new_interview)
    db.commit()
    db.refresh(new_interview)

    target_n = random.randint(5, 7)
    cv_text = getattr(profile, "cv_text", None)

    # HIZLI BAŞLANGIC: Fallback sorularını direkt kullan (Ollama yavaş olduğu için)
    # WebSocket'te (mülakatın başında) Ollama'dan dinamik sorular alınacak
    logger.info(f"Mülakat oluşturma: fallback sorularını hızlı kullanıyorum")
    ai_list = fallback_questions(payload.domain, payload.language, target_n)
    logger.info(f"✅ {len(ai_list)} fallback soru yüklendi")

    if ai_list:
        order = 1
        for item in ai_list[:target_n]:
            text = (item.get("text") or "").strip()[:1024]
            if not text:
                continue
            db.add(
                models.InterviewQuestion(
                    interview_id=new_interview.id,
                    question_id=None,
                    question_text=text,
                    order=order,
                )
            )
            order += 1
        if order > 1:
            db.commit()
            return {
                "id": new_interview.id,
                "title": new_interview.title,
                "domain": new_interview.domain,
                "language": new_interview.language,
                "status": new_interview.status,
                "created_at": new_interview.created_at,
                "question_source": "ollama_or_fallback",
            }

    raise HTTPException(status_code=500, detail="Mülakat soruları oluşturulamadı.")


class DebugGenerateQuestionsRequest(BaseModel):
    position: str
    company_name: str | None = None
    department_name: str | None = None
    domain: str
    language: str = "tr"
    n_questions: int = 6


@router.post("/debug/generate-questions")
def debug_generate_questions(
    payload: DebugGenerateQuestionsRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    profile = db.query(models.Profile).filter(models.Profile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=400, detail="Önce profil bilgilerinizi doldurun.")
    if not getattr(profile, "cv_path", None):
        raise HTTPException(status_code=400, detail="Önce profilinize CV yüklemelisiniz.")

    cv_text = getattr(profile, "cv_text", None)
    questions = generate_questions(
        position=payload.position,
        company_name=payload.company_name,
        department_name=payload.department_name,
        domain=payload.domain,
        language=payload.language,
        cv_text=cv_text,
        profile_university=getattr(profile, "university", None),
        profile_department=getattr(profile, "department", None),
        profile_class_year=getattr(profile, "class_year", None),
        n_questions=payload.n_questions,
    )
    return {"questions": questions}


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


class InterviewStatusUpdate(BaseModel):
    status: str


@router.post("/interviews/{interview_id}/status")
def update_interview_status(
    interview_id: int,
    payload: InterviewStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Mülakat bulunamadı")
    if interview.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Bu mülakata erişim yetkiniz yok")
    if payload.status not in ALLOWED_INTERVIEW_STATUSES:
        raise HTTPException(status_code=400, detail="Geçersiz mülakat durumu")
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
):
    interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Mülakat bulunamadı")
    if interview.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Bu mülakata erişim yetkiniz yok")

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
        transcript_text, duration, _, _ = stt.get_transcript(interview_id, str(target_path))
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
):
    interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Mülakat bulunamadı")
    if interview.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Bu mülakata erişim yetkiniz yok")

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

    return {
        "id": interview.id,
        "user_id": interview.user_id,
        "title": interview.title,
        "domain": interview.domain,
        "language": interview.language,
        "status": interview.status,
        "created_at": interview.created_at,
        "questions": questions,
        "transcript": transcript,
        "duration_seconds": duration,
        "feedback": feedback,
    }


class ChatMessage(BaseModel):
    message: str


@router.post("/interviews/{interview_id}/chat")
def chat(
    interview_id: int,
    payload: ChatMessage,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    if interview.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have access to this interview")

    transcript_row = db.query(models.Transcript).filter(models.Transcript.interview_id == interview_id).first()
    feedback_row = db.query(models.Feedback).filter(models.Feedback.interview_id == interview_id).first()
    transcript = (transcript_row.text or "") if transcript_row else ""
    summary = (feedback_row.summary or "") if feedback_row else ""
    strengths = (feedback_row.strengths or "") if feedback_row else ""
    improvements = (feedback_row.improvements or "") if feedback_row else ""

    user_msg = (payload.message or "").strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Mesaj boş olamaz")

    reply = chat_response(transcript, summary, strengths, improvements, user_msg, interview.language or "tr")
    return {"reply": reply}
