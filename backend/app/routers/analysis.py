"""
Interview Analysis API Endpoints
Handles metrics calculation, content analysis, and feedback generation
"""

import asyncio
import json
import logging
from typing import Any, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..analysis.scoring import pause_control_from_answer_text
from ..analysis.speech_metrics import words_per_minute, wpm_clarity_score
from ..analysis.video_features import analyze_interview_video, resolve_interview_video_path
from .. import models
from .auth import get_current_user, get_db
from .content_analyzer import get_analyzer as get_content_analyzer
from .feedback_generator import get_generator as get_feedback_generator
from ..analysis.ollama_feedback import generate_ollama_feedback

logger = logging.getLogger(__name__)

router = APIRouter()


def run_full_analysis(interview_id: int) -> None:
    """
    Run the complete analysis pipeline (content + speech + video + Ollama feedback).
    Creates its own DB session — safe to call as a FastAPI BackgroundTask.
    Sets interview.status to 'analyzed' on success or 'analysis_failed' on error.
    """
    from ..database import SessionLocal

    db = SessionLocal()
    try:
        interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
        if not interview:
            return

        all_metrics, n_answers = apply_content_metrics_to_interview_answers(db, interview)
        db.commit()

        if n_answers == 0:
            interview.status = "analysis_failed"
            db.commit()
            return

        answer_rows = (
            db.query(models.InterviewAnswer)
            .filter(models.InterviewAnswer.interview_id == interview_id)
            .order_by(models.InterviewAnswer.question_order)
            .all()
        )

        def _mean_int(getter):
            vals = [getter(r) for r in answer_rows if getter(r) is not None]
            return int(sum(vals) / len(vals)) if vals else None

        content_scores  = [m.get("content_score",  50) for m in all_metrics if "content_score"  in m]
        relevance_scores = [m.get("relevance_score", 50) for m in all_metrics if "relevance_score" in m]
        overall_content  = int(sum(content_scores)  / len(content_scores))  if content_scores  else 50
        overall_relevance = int(sum(relevance_scores) / len(relevance_scores)) if relevance_scores else 50

        wpm_avg   = _mean_int(lambda r: r.speech_rate_wpm)
        pause_avg = _mean_int(lambda r: r.pause_frequency_score)
        wpm_clarity_vals = [
            wpm_clarity_score(int(r.speech_rate_wpm))
            for r in answer_rows if r.speech_rate_wpm is not None
        ]
        if wpm_clarity_vals and pause_avg is not None:
            speech_quality = int((sum(wpm_clarity_vals) / len(wpm_clarity_vals) + pause_avg) / 2)
        elif wpm_clarity_vals:
            speech_quality = int(sum(wpm_clarity_vals) / len(wpm_clarity_vals))
        elif pause_avg is not None:
            speech_quality = pause_avg
        else:
            speech_quality = 65

        eye_avg     = _mean_int(lambda r: r.eye_contact_score)
        posture_avg = _mean_int(lambda r: r.posture_score)
        head_avg    = _mean_int(lambda r: r.head_stability_score)
        nv_parts    = [x for x in [eye_avg, posture_avg, head_avg] if x is not None]
        nonverbal_aggregate = int(sum(nv_parts) / len(nv_parts)) if nv_parts else None

        avg_words = _mean_int(lambda r: r.answer_length_words) or 0

        # Domain-aware averages — None when not applicable
        tech_avg = _mean_int(lambda r: r.technical_accuracy_score)   # None for general domain
        star_avg = _mean_int(lambda r: r.star_structure_score)        # None for technical domain

        aggregated_metrics = {
            "domain": interview.domain,
            "content_score": overall_content,
            "relevance_score": overall_relevance,
            "answer_count": n_answers,
            "answer_length_words": avg_words,
            "star_structure_score": star_avg,          # None for technical domain
            "technical_accuracy_score": tech_avg,      # None for general domain
            "speech_quality_score": speech_quality,
            "speech_rate_wpm": wpm_avg if wpm_avg is not None else 120,
            "pause_frequency_score": pause_avg if pause_avg is not None else 70,
            "eye_contact_score": eye_avg,
            "posture_score": posture_avg,
            "head_stability_score": head_avg,
            "nonverbal_aggregate": nonverbal_aggregate,
        }

        feedback_gen    = get_feedback_generator()
        feedback_report = feedback_gen.generate_full_report(
            interview_data={"domain": interview.domain},
            metrics=aggregated_metrics,
        )

        qa_pairs    = [{"question": r.question_text or "", "answer": r.answer_text or ""} for r in answer_rows]
        ollama_text = generate_ollama_feedback(
            questions_answers=qa_pairs,
            metrics=aggregated_metrics,
            domain=interview.domain or "general",
        )

        feedback = (
            db.query(models.Feedback)
            .filter(models.Feedback.interview_id == interview_id)
            .order_by(models.Feedback.created_at.desc(), models.Feedback.id.desc())
            .first()
        )
        if not feedback:
            feedback = models.Feedback(interview_id=interview_id)
            db.add(feedback)

        def _communication_label(score: Optional[int]) -> str:
            """Speech-based communication skill label."""
            if score is None: return "Average"
            if score >= 80:   return "Strong"
            if score >= 65:   return "Good"
            if score >= 50:   return "Average"
            return "Weak"

        def _motivation_label(score: Optional[int]) -> str:
            """Content-based motivation / engagement label."""
            if score is None: return "Average"
            if score >= 80:   return "High"
            if score >= 65:   return "Moderate"
            if score >= 50:   return "Average"
            return "Low"

        feedback.overall_score               = feedback_report["overall_score"]
        feedback.content_quality_score       = feedback_report["content_score"]
        feedback.speech_quality_score        = feedback_report["speech_score"]
        feedback.nonverbal_score             = feedback_report["nonverbal_score"]
        feedback.metrics_json                = json.dumps(aggregated_metrics)
        feedback.summary                     = "Interview analysis complete"
        feedback.strengths                   = "\n".join(feedback_report["strengths"])
        feedback.improvements                = "\n".join(feedback_report["improvements"])
        feedback.actionable_recommendations  = ollama_text or feedback_report["content_feedback"]
        feedback.technical_fit               = "Sufficient" if overall_content >= 75 else "Partial" if overall_content >= 60 else "Insufficient"
        feedback.communication_fit           = _communication_label(speech_quality)
        feedback.motivation_level            = _motivation_label(overall_content)
        feedback.overall_recommendation      = feedback_report["recommendation"]
        interview.status                     = "analyzed"
        db.commit()
        logger.info("Background analysis complete for interview_id=%s", interview_id)

    except Exception as exc:
        logger.error("Background analysis failed for interview_id=%s: %s", interview_id, exc, exc_info=True)
        try:
            db.rollback()
            interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
            if interview:
                interview.status = "analysis_failed"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _backfill_speech_from_transcript(db: Session, interview: models.Interview, answers: List[Any]) -> None:
    """Fill missing speech_rate_wpm and pause_frequency_score from interview transcript.

    WPM note: the transcript only provides total word count + total duration,
    so per-answer timing is unavailable. We estimate each missing answer's WPM
    from its own word count and its proportional share of the total duration —
    which is mathematically equivalent to the overall rate but derives from
    per-answer data and stays None when the answer has no text.
    """
    if not answers:
        return

    # Pause score: keep real PCM-based value from WebSocket if present;
    # fall back to text-based English filler-word proxy only when missing.
    for ar in answers:
        if ar.pause_frequency_score is None:
            ar.pause_frequency_score = pause_control_from_answer_text(ar.answer_text or "")  # English fallback

    # speech_rate_wpm backfill requires a transcript with valid duration
    tr = (
        db.query(models.Transcript)
        .filter(models.Transcript.interview_id == interview.id)
        .order_by(models.Transcript.id.desc())
        .first()
    )
    if not tr or not tr.duration_seconds or tr.duration_seconds <= 0:
        return

    total_duration = float(tr.duration_seconds)
    full_text = (tr.text or "").strip()
    total_words = len(full_text.split())
    if total_words <= 0:
        return

    # Assign per-answer WPM only to answers that lack real PCM-based timing.
    # Use the answer's own word count to estimate its proportional duration.
    for ar in answers:
        if ar.speech_rate_wpm is not None:
            continue  # already set from PCM — don't overwrite
        answer_words = len((ar.answer_text or "").split())
        if answer_words <= 0:
            continue  # empty answer — leave as None
        # Proportional duration estimate: answer_words / total_words * total_duration
        est_duration = (answer_words / total_words) * total_duration
        ar.speech_rate_wpm = words_per_minute(answer_words, est_duration)


_VIDEO_NONVERBAL_KEYS = (
    "eye_contact_score",
    "head_stability_score",
    "posture_score",
)


def _apply_video_nonverbal_to_answers(
    interview: models.Interview,
    answers: List[Any],
) -> Optional[dict]:
    """Run MediaPipe/OpenCV video analysis and set nonverbal fields on each answer row.

    If answers have video_start_second / video_end_second timestamps (set by WebSocket),
    each answer is analyzed against its own video segment. Otherwise falls back to
    whole-video analysis (legacy behaviour / no timestamps recorded).
    """
    if not answers:
        return None

    video_path = resolve_interview_video_path(
        interview.id,
        getattr(interview, "video_path", None),
    )
    if not video_path:
        logger.info("No interview video found for interview_id=%s", interview.id)
        return None

    # Check if per-answer timestamps are available
    has_timestamps = any(
        getattr(a, "video_start_second", None) is not None
        and getattr(a, "video_end_second", None) is not None
        for a in answers
    )

    if has_timestamps:
        logger.info("Per-answer video analysis: interview_id=%s", interview.id)
        aggregated: dict = {}
        for answer_row in answers:
            start = getattr(answer_row, "video_start_second", None)
            end   = getattr(answer_row, "video_end_second",   None)
            if start is None or end is None or end <= start:
                continue
            try:
                nv = analyze_interview_video(video_path, start_sec=start, end_sec=end, max_frames=120)
            except Exception as e:
                logger.error("Segment video analysis failed for answer order=%s: %s", answer_row.question_order, e)
                continue
            if not nv:
                continue
            for key in _VIDEO_NONVERBAL_KEYS:
                val = nv.get(key)
                if val is not None:
                    setattr(answer_row, key, int(val))
                    aggregated.setdefault(key, []).append(val)
            logger.info(
                "Segment video applied (order=%s, %.1f-%.1fs, method=%s)",
                answer_row.question_order, start, end, nv.get("video_analysis_method"),
            )

        if not aggregated:
            return None
        final_nv = {k: int(sum(v) / len(v)) for k, v in aggregated.items()}
        final_nv["video_analysis_method"] = "mediapipe_per_answer"
        return final_nv

    # ── Fallback: whole-video analysis (no timestamps) ──
    logger.info("Whole-video analysis (no timestamps): interview_id=%s", interview.id)
    try:
        nv = analyze_interview_video(video_path)
    except Exception as e:
        logger.error("Video analysis failed for interview %s: %s", interview.id, e)
        return None

    if not nv:
        return None

    for answer_row in answers:
        for key in _VIDEO_NONVERBAL_KEYS:
            val = nv.get(key)
            if val is not None:
                setattr(answer_row, key, int(val))

    logger.info(
        "Video nonverbal applied (method=%s, detection=%.2f) interview_id=%s",
        nv.get("video_analysis_method"),
        float(nv.get("video_face_detection_rate") or 0),
        interview.id,
    )
    return nv


def apply_content_metrics_to_interview_answers(db: Session, interview: models.Interview) -> Tuple[List[Any], int]:
    """
    Run content analyzer on each InterviewAnswer row and persist fields.
    Caller must commit. Returns (all_metrics, answer_count).
    """
    answers = (
        db.query(models.InterviewAnswer)
        .filter(models.InterviewAnswer.interview_id == interview.id)
        .order_by(models.InterviewAnswer.question_order)
        .all()
    )
    if not answers:
        return [], 0

    analyzer = get_content_analyzer()
    all_metrics: List[Any] = []
    row_blobs: List[dict] = []
    is_behavioral = interview.domain == "general"

    for answer_row in answers:
        try:
            content_metrics = analyzer.analyze_answer(
                question=answer_row.question_text or "",
                answer=answer_row.answer_text or "",
                domain=interview.domain,
                is_behavioral=is_behavioral,
            )
            answer_row.relevance_score = content_metrics.get("relevance_score", 0)
            answer_row.star_structure_score = content_metrics.get("star_structure_score")
            answer_row.technical_accuracy_score = content_metrics.get("technical_accuracy_score")
            answer_row.answer_length_words = content_metrics.get("answer_length_words", 0)
            answer_row.content_score = content_metrics.get("content_score", 0)
            answer_row.red_flags = json.dumps([])
            all_metrics.append(content_metrics)
            row_blobs.append(dict(content_metrics))
        except Exception as e:
            logger.error("Error analyzing answer %s: %s", answer_row.question_order, e)
            answer_row.relevance_score = 50
            answer_row.content_score = 50
            row_blobs.append({"analysis_error": str(e)[:500]})

    _backfill_speech_from_transcript(db, interview, answers)

    video_nv = _apply_video_nonverbal_to_answers(interview, answers)
    if video_nv:
        for blob in row_blobs:
            blob.update({k: video_nv[k] for k in _VIDEO_NONVERBAL_KEYS if k in video_nv})
            blob["video_analysis_method"] = video_nv.get("video_analysis_method")
            blob["video_face_detection_rate"] = video_nv.get("video_face_detection_rate")

    for answer_row, blob in zip(answers, row_blobs):
        for key in (
            "speech_rate_wpm",
            "pause_frequency_score",
            "eye_contact_score",
            "head_stability_score",
            "posture_score",
        ):
            val = getattr(answer_row, key, None)
            if val is not None:
                blob[key] = val
        answer_row.answer_feedback = json.dumps(blob, ensure_ascii=False)

    return all_metrics, len(answers)


@router.get("/interviews/{interview_id}/analysis")
def get_interview_analysis(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get complete analysis for an interview"""
    interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    if interview.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have access to this interview")

    feedback = db.query(models.Feedback).filter(
        models.Feedback.interview_id == interview_id
    ).order_by(models.Feedback.created_at.desc(), models.Feedback.id.desc()).first()
    if not feedback:
        raise HTTPException(status_code=404, detail="Analysis results are not ready yet")

    try:
        metrics = json.loads(feedback.metrics_json) if feedback.metrics_json else {}
    except Exception:
        metrics = {}

    return {
        "interview_id": interview_id,
        "overall_score": feedback.overall_score,
        "content_quality_score": feedback.content_quality_score,
        "speech_quality_score": feedback.speech_quality_score,
        "nonverbal_score": feedback.nonverbal_score,
        "summary": feedback.summary,
        "strengths": feedback.strengths,
        "improvements": feedback.improvements,
        "actionable_recommendations": feedback.actionable_recommendations,
        "technical_fit": feedback.technical_fit,
        "communication_fit": feedback.communication_fit,
        "motivation_level": feedback.motivation_level,
        "overall_recommendation": feedback.overall_recommendation,
        "metrics": metrics,
    }


@router.post("/interviews/{interview_id}/analyze")
async def analyze_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Analyze interview: calculate metrics and generate feedback (including Ollama)."""
    interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    if interview.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have access to this interview")

    # run_full_analysis is CPU/IO-heavy (Whisper + MediaPipe + SentenceTransformer + Ollama).
    # Run it in a thread-pool executor so the async event loop stays free for other requests.
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, run_full_analysis, interview_id)
    except Exception as e:
        logger.error("analyze endpoint error for interview %s: %s", interview_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Analysis failed. Please try again.")

    # Re-read to return fresh status/scores
    db.expire(interview)
    feedback = (
        db.query(models.Feedback)
        .filter(models.Feedback.interview_id == interview_id)
        .order_by(models.Feedback.created_at.desc(), models.Feedback.id.desc())
        .first()
    )
    return {
        "status": "success",
        "interview_id": interview_id,
        "overall_score": feedback.overall_score if feedback else None,
        "recommendation": feedback.overall_recommendation if feedback else None,
    }
