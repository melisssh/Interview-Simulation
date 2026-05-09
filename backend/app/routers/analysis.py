"""
Interview Analysis API Endpoints
Handles metrics calculation, content analysis, and feedback generation
"""

import json
import logging
from typing import Any, List, Tuple

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..analysis.scoring import pause_control_from_answer_text, score_transcript
from ..analysis.speech_metrics import (
    nonverbal_proxies_from_speech,
    words_per_minute,
    wpm_clarity_score,
)
from ..cv_read import read_cv_plaintext
from .. import models
from .auth import get_current_user, get_db
from .content_analyzer import get_analyzer as get_content_analyzer
from .feedback_generator import get_generator as get_feedback_generator

logger = logging.getLogger(__name__)

router = APIRouter()


def _backfill_speech_from_transcript(db: Session, interview: models.Interview, answers: List[Any]) -> None:
    """Fill missing speech columns using interview video transcript + duration when available."""
    if not answers:
        return
    tr = (
        db.query(models.Transcript)
        .filter(models.Transcript.interview_id == interview.id)
        .order_by(models.Transcript.id.desc())
        .first()
    )
    if not tr or not tr.duration_seconds or tr.duration_seconds <= 0:
        return
    full_text = (tr.text or "").strip()
    total_words = len(full_text.split())
    if total_words <= 0:
        return
    lang = interview.language or "tr"
    overall_wpm = words_per_minute(total_words, float(tr.duration_seconds))
    try:
        full_pkg = score_transcript(full_text, duration_seconds=int(tr.duration_seconds), language=lang)
        sc = full_pkg.get("scores") or {}
        speaking = sc.get("speaking_rate")
        pause_ctrl = sc.get("pause_control")
    except Exception:
        speaking = pause_ctrl = None

    for ar in answers:
        if ar.speech_rate_wpm is None and overall_wpm is not None:
            ar.speech_rate_wpm = overall_wpm
        if ar.pause_frequency_score is None:
            ar.pause_frequency_score = pause_control_from_answer_text(ar.answer_text or "", lang)
        if ar.volume_stability_score is None and speaking is not None:
            ar.volume_stability_score = int(max(35, min(100, int(speaking) + 8)))
        if ar.tone_variation_score is None:
            if pause_ctrl is not None and speaking is not None:
                ar.tone_variation_score = int(max(40, min(96, (int(speaking) + int(pause_ctrl)) // 2)))
            elif pause_ctrl is not None:
                ar.tone_variation_score = int(max(45, min(92, int(pause_ctrl))))
            else:
                ar.tone_variation_score = 58


def _finalize_engagement_nonverbal(answer_row: models.InterviewAnswer, language: str) -> None:
    """Speech-inferred nonverbal proxies + engagement composite (no separate vision pipeline)."""
    lang = language or "tr"
    p = answer_row.pause_frequency_score
    if p is None:
        p = pause_control_from_answer_text(answer_row.answer_text or "", lang)
    v = answer_row.volume_stability_score if answer_row.volume_stability_score is not None else 58
    t = answer_row.tone_variation_score if answer_row.tone_variation_score is not None else 58
    nv = nonverbal_proxies_from_speech(
        pause_score=int(p),
        volume_stability=int(v),
        tone_variation=int(t),
        sentiment=int(answer_row.sentiment_score or 0),
    )
    for key, val in nv.items():
        setattr(answer_row, key, val)

    parts = [int(answer_row.content_score or 0)]
    if answer_row.speech_rate_wpm is not None:
        parts.append(wpm_clarity_score(int(answer_row.speech_rate_wpm)))
    parts.append(int(p))
    answer_row.engagement_score = int(round(sum(parts) / len(parts)))


def apply_content_metrics_to_interview_answers(db: Session, interview: models.Interview) -> Tuple[List[Any], int]:
    """
    Run content analyzer on each InterviewAnswer row and persist fields on those ORM objects.
    Caller must commit. Returns (all_metrics, answer_count). answer_count 0 means no rows.
    """
    answers = (
        db.query(models.InterviewAnswer)
        .filter(models.InterviewAnswer.interview_id == interview.id)
        .order_by(models.InterviewAnswer.question_order)
        .all()
    )
    if not answers:
        return [], 0

    profile = db.query(models.Profile).filter(models.Profile.user_id == interview.user_id).first()
    cv_text = read_cv_plaintext(getattr(profile, "cv_path", None)) if profile else ""

    analyzer = get_content_analyzer()
    all_metrics: List[Any] = []
    row_blobs: List[dict] = []
    is_behavioral = interview.domain == "general"
    lang = interview.language or "tr"

    for answer_row in answers:
        try:
            content_metrics = analyzer.analyze_answer(
                question=answer_row.question_text or "",
                answer=answer_row.answer_text or "",
                domain=interview.domain,
                is_behavioral=is_behavioral,
                cv_text=cv_text or None,
                language=lang,
            )
            answer_row.relevance_score = content_metrics.get("relevance_score", 0)
            answer_row.keyword_match_score = content_metrics.get("keyword_match_score", 0)
            answer_row.completeness_score = content_metrics.get("completeness_score", 0)
            answer_row.star_structure_score = content_metrics.get("star_structure_score")
            answer_row.technical_accuracy_score = content_metrics.get("technical_accuracy_score")
            answer_row.sentiment_score = content_metrics.get("sentiment_score", 0)
            answer_row.answer_length_words = content_metrics.get("answer_length_words", 0)
            answer_row.content_score = content_metrics.get("content_score", 0)
            answer_row.qualification_match_score = content_metrics.get("qualification_match_score", 0)
            answer_row.red_flags = json.dumps([])
            all_metrics.append(content_metrics)
            row_blobs.append(dict(content_metrics))
        except Exception as e:
            logger.error("Error analyzing answer %s: %s", answer_row.question_order, e)
            answer_row.relevance_score = 50
            answer_row.keyword_match_score = 50
            answer_row.completeness_score = 50
            answer_row.content_score = 50
            answer_row.qualification_match_score = 0
            row_blobs.append({"analysis_error": str(e)[:500]})

    _backfill_speech_from_transcript(db, interview, answers)

    for answer_row, blob in zip(answers, row_blobs):
        _finalize_engagement_nonverbal(answer_row, lang)
        for key in (
            "speech_rate_wpm",
            "pause_frequency_score",
            "volume_stability_score",
            "tone_variation_score",
            "eye_contact_score",
            "head_stability_score",
            "posture_score",
            "facial_expression_positive",
            "facial_expression_neutral",
            "facial_expression_negative",
            "confidence_tone_score",
            "engagement_score",
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
    print(f"\n📊 GET /analysis endpoint: interview_id={interview_id}\n")
    interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
    if not interview:
        print(f"❌ Interview not found\n")
        raise HTTPException(status_code=404, detail="Mülakat bulunamadı")
    if interview.user_id != current_user.id:
        print(f"❌ User permission denied\n")
        raise HTTPException(status_code=403, detail="Bu mülakata erişim yetkiniz yok")

    # Get feedback from database
    print(f"📊 Feedback searching...\n")
    feedback = db.query(models.Feedback).filter(
        models.Feedback.interview_id == interview_id
    ).order_by(models.Feedback.created_at.desc(), models.Feedback.id.desc()).first()
    if not feedback:
        print(f"❌ Feedback not found\n")
        raise HTTPException(status_code=404, detail="Analiz sonuçları henüz hazır değil")
    print(f"✅ Feedback found: score={feedback.overall_score}\n")

    # Parse metrics JSON
    try:
        metrics = json.loads(feedback.metrics_json) if feedback.metrics_json else {}
    except:
        metrics = {}

    response = {
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
    print(f"✅ Response gönderiliyor: score={response['overall_score']}\n")
    return response


@router.post("/interviews/{interview_id}/analyze")
async def analyze_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Analyze interview: calculate metrics, match qualifications, generate feedback
    Called after video upload is complete
    """
    print(f"\n📊📊📊 ANALYZE ENDPOINT BAŞLADI: interview_id={interview_id} 📊📊📊\n")
    logger.info(f"Starting analysis for interview {interview_id}")

    try:
        interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
        print(f"📊 Interview sorgulanıyor: {interview is not None}\n")
        if not interview:
            print(f"❌ Interview bulunamadı\n")
            logger.error(f"Interview {interview_id} not found")
            raise HTTPException(status_code=404, detail="Mülakat bulunamadı")
        if interview.user_id != current_user.id:
            print(f"❌ Yetki yok\n")
            logger.error(f"User {current_user.id} does not own interview {interview_id}")
            raise HTTPException(status_code=403, detail="Bu mülakata erişim yetkiniz yok")
        interview.status = "analyzing"
        db.commit()

        print(f"📊 Answers sorgulanıyor...\n")
        all_metrics, n_answers = apply_content_metrics_to_interview_answers(db, interview)
        print(f"📊 {n_answers} cevap bulundu\n")

        if n_answers == 0:
            print(f"❌ Cevap bulunamadı\n")
            logger.warning(f"No answers found for interview {interview_id}")
            raise HTTPException(status_code=400, detail="Cevap verisi bulunamadı")

        logger.info(f"Analyzed {n_answers} answers for interview {interview_id}")

        # Calculate aggregate scores
        if all_metrics:
            content_scores = [m.get("content_score", 50) for m in all_metrics if "content_score" in m]
            relevance_scores = [m.get("relevance_score", 50) for m in all_metrics if "relevance_score" in m]
            keyword_scores = [m.get("keyword_match_score", 50) for m in all_metrics if "keyword_match_score" in m]

            overall_content_score = int(sum(content_scores) / len(content_scores)) if content_scores else 50
            overall_relevance = int(sum(relevance_scores) / len(relevance_scores)) if relevance_scores else 50
            overall_keywords = int(sum(keyword_scores) / len(keyword_scores)) if keyword_scores else 50
        else:
            overall_content_score = 50
            overall_relevance = 50
            overall_keywords = 50

        logger.info(f"Aggregate scores: content={overall_content_score}, relevance={overall_relevance}, keywords={overall_keywords}")

        answer_rows = (
            db.query(models.InterviewAnswer)
            .filter(models.InterviewAnswer.interview_id == interview_id)
            .order_by(models.InterviewAnswer.question_order)
            .all()
        )

        def _mean_int(getter):
            vals = [getter(r) for r in answer_rows]
            vals = [v for v in vals if v is not None]
            return int(sum(vals) / len(vals)) if vals else None

        wpm_avg = _mean_int(lambda r: r.speech_rate_wpm)
        pause_avg = _mean_int(lambda r: r.pause_frequency_score)
        vol_avg = _mean_int(lambda r: r.volume_stability_score)
        tone_avg = _mean_int(lambda r: r.tone_variation_score)
        eye_avg = _mean_int(lambda r: r.eye_contact_score)
        posture_avg = _mean_int(lambda r: r.posture_score)
        head_avg = _mean_int(lambda r: r.head_stability_score)
        engagement_avg = _mean_int(lambda r: r.engagement_score)
        qual_avg = _mean_int(lambda r: r.qualification_match_score)

        wpm_clarity_vals = [
            wpm_clarity_score(int(r.speech_rate_wpm))
            for r in answer_rows
            if r.speech_rate_wpm is not None
        ]
        if wpm_clarity_vals and pause_avg is not None:
            speech_quality_score = int((sum(wpm_clarity_vals) / len(wpm_clarity_vals) + pause_avg) / 2)
        elif wpm_clarity_vals:
            speech_quality_score = int(sum(wpm_clarity_vals) / len(wpm_clarity_vals))
        elif pause_avg is not None:
            speech_quality_score = pause_avg
        else:
            speech_quality_score = 65

        nv_parts = [x for x in [eye_avg, posture_avg, head_avg, tone_avg] if x is not None]
        nonverbal_aggregate = int(sum(nv_parts) / len(nv_parts)) if nv_parts else 65

        # Generate feedback
        feedback_gen = get_feedback_generator()
        tech_avg = _mean_int(lambda r: r.technical_accuracy_score)
        aggregated_metrics = {
            "content_score": overall_content_score,
            "relevance_score": overall_relevance,
            "keyword_match_score": overall_keywords,
            "answer_count": n_answers,
            "speech_quality_score": speech_quality_score,
            "speech_rate_wpm": wpm_avg if wpm_avg is not None else 120,
            "pause_frequency_score": pause_avg if pause_avg is not None else 70,
            "volume_stability_score": vol_avg if vol_avg is not None else 70,
            "tone_variation_score": tone_avg if tone_avg is not None else 70,
            "eye_contact_score": eye_avg if eye_avg is not None else 65,
            "posture_score": posture_avg if posture_avg is not None else 65,
            "head_stability_score": head_avg if head_avg is not None else 65,
            "engagement_score": engagement_avg if engagement_avg is not None else overall_content_score,
            "qualification_match_score": qual_avg if qual_avg is not None else 0,
            "technical_accuracy_score": tech_avg if tech_avg is not None else overall_content_score,
            "nonverbal_aggregate": nonverbal_aggregate,
        }

        feedback_report = feedback_gen.generate_full_report(
            interview_data={"domain": interview.domain, "language": interview.language},
            metrics=aggregated_metrics
        )

        # Save feedback to database
        feedback = db.query(models.Feedback).filter(
            models.Feedback.interview_id == interview_id
        ).order_by(models.Feedback.created_at.desc(), models.Feedback.id.desc()).first()
        if not feedback:
            feedback = models.Feedback(interview_id=interview_id)
            db.add(feedback)

        feedback.overall_score = feedback_report["overall_score"]
        feedback.content_quality_score = feedback_report["content_score"]
        feedback.speech_quality_score = feedback_report["speech_score"]
        feedback.nonverbal_score = feedback_report["nonverbal_score"]
        feedback.metrics_json = json.dumps(aggregated_metrics)
        feedback.summary = "Mülakat analiz tamamlandı"
        feedback.strengths = "\n".join(feedback_report["strengths"])
        feedback.improvements = "\n".join(feedback_report["improvements"])
        feedback.actionable_recommendations = feedback_report["content_feedback"]
        feedback.technical_fit = "Sufficient" if overall_content_score >= 75 else "Partial" if overall_content_score >= 60 else "Insufficient"
        feedback.communication_fit = "Good"  # Would need speech analysis
        feedback.motivation_level = "High"  # Would need video analysis
        feedback.overall_recommendation = feedback_report["recommendation"]
        interview.status = "analyzed"

        db.commit()
        db.refresh(feedback)

        print(f"\n✅✅✅ ANALIZ TAMAMLANDI ✅✅✅\n")
        print(f"📊 Score: {feedback.overall_score}\n")
        print(f"📊 Recommendation: {feedback.overall_recommendation}\n")
        logger.info(f"Analysis complete. Score: {feedback.overall_score}, Recommendation: {feedback.overall_recommendation}")

        return {
            "status": "success",
            "interview_id": interview_id,
            "overall_score": feedback.overall_score,
            "recommendation": feedback.overall_recommendation,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"\n❌❌❌ ANALIZ HATASI ❌❌❌\n")
        print(f"❌ {e}\n")
        import traceback
        print(f"{traceback.format_exc()}\n")
        logger.error(f"Analysis error for interview {interview_id}: {e}", exc_info=True)
        try:
            interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
            if interview:
                interview.status = "analysis_failed"
                db.commit()
        except Exception:
            db.rollback()
        raise HTTPException(status_code=500, detail=f"Analiz hatası: {str(e)}")
