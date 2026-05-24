"""
Module for computing simple metrics and rule-based scores from a transcript.

Goals:
- Compute basic metrics such as length and filler-word ratio
- Produce a few 0–100 scores
- Generate simple summary / strengths / improvements texts

Note: App is Turkish-only. English filler-word support has been removed.
"""

from typing import Dict, Optional


# Turkish filler / hesitation words (correctly encoded)
FILLER_WORDS_TR = ["şey", "yani", "işte", "hani", "aslında", "eee", "hmm", "ya", "falan", "öyle"]


def _normalize_word(word: str) -> str:
    return word.strip(".,!?;:()[]\"'").lower()


def _build_text_feedback_tr(
    total_words: int, filler_ratio: float, overall_score: int
) -> tuple[str, str, str]:
    if overall_score >= 80:
        summary = "Yanıtınız güçlü ve akıcıydı."
    elif overall_score >= 50:
        summary = "Yanıtınız yeterliydi ancak bazı alanlarda gelişim var."
    else:
        summary = "Yanıtınızı yapı ve akıcılık açısından geliştirmeniz faydalı olur."

    strengths_parts: list[str] = []
    if total_words >= 80:
        strengths_parts.append("Yanıtınız yeterince detaylı.")
    if filler_ratio < 0.1:
        strengths_parts.append(
            "Dolgu kelime kullanımınız çok düşük; mesajınız net ve akıcı."
        )
    if not strengths_parts:
        strengths_parts.append("Yanıtınız geliştirmek için iyi bir başlangıç.")
    strengths = " ".join(strengths_parts)

    improvements_parts: list[str] = []
    if total_words < 80:
        improvements_parts.append(
            "Yanıtınızı biraz daha uzatın ve somut örnekler ekleyin."
        )
    if filler_ratio >= 0.2:
        improvements_parts.append(
            "Konuşurken “şey”, “yani” gibi dolgu kelimeleri azaltmaya çalışın."
        )
    if overall_score < 80:
        improvements_parts.append(
            "Yanıtlarınızı net bir giriş, gelişme ve sonuçla yapılandırmaya çalışın."
        )
    improvements = (
        " ".join(improvements_parts)
        if improvements_parts
        else "Benzer şekilde yanıtlamaya devam edebilirsiniz; seviye yeterli."
    )
    return summary, strengths, improvements


def pause_control_from_answer_text(text: str, language: str = "tr") -> int:
    """
    0–100 pause / fluency proxy from a single answer transcript (Turkish filler density).
    Used as a text-based fallback when no PCM audio data is available.
    """
    words = [_normalize_word(w) for w in (text or "").split() if _normalize_word(w)]
    total_words = len(words)
    if total_words == 0:
        return 45
    filler_count = sum(1 for w in words if w in FILLER_WORDS_TR)
    filler_ratio = filler_count / total_words if total_words else 0.0
    if filler_ratio >= 0.4:
        return 0
    return int(max(0, min(100, 100 - (filler_ratio / 0.35) * 100)))


def score_transcript(
    transcript: str,
    duration_seconds: Optional[int] = None,
) -> Dict[str, object]:
    """
    Compute basic metrics, scores and textual feedback from a transcript.

    Returns a dictionary with the following structure:
    {
        "metrics": {...},
        "scores": {...},
        "summary": "...",
        "strengths": "...",
        "improvements": "..."
    }
    """
    words = [_normalize_word(w) for w in transcript.split() if _normalize_word(w)]
    total_words = len(words)

    filler_count = sum(1 for w in words if w in FILLER_WORDS_TR)
    filler_ratio = filler_count / total_words if total_words else 0.0

    # Basit metrikler
    metrics = {
        "total_words": total_words,
        "filler_count": filler_count,
        "filler_ratio": filler_ratio,
        "duration_seconds": duration_seconds,
    }

    # Uzunluk skoru: 80–200 kelime arası ideal (100 puan)
    if total_words == 0:
        length_score = 0
    elif total_words < 80:
        length_score = int(total_words / 80 * 80)
    elif total_words > 200:
        length_score = max(60, int(200 / total_words * 100))
    else:
        length_score = 100

    # Filler kelime skoru: %0 filler = 100, %40 ve üzeri = 0
    if filler_ratio >= 0.4:
        filler_score = 0
    else:
        filler_score = int((1.0 - filler_ratio / 0.4) * 100)

    overall_score = int((length_score + filler_score) / 2)

    scores = {
        "length": length_score,
        "filler_usage": filler_score,
        "overall": overall_score,
    }

    summary, strengths, improvements = _build_text_feedback_tr(total_words, filler_ratio, overall_score)

    return {
        "metrics": metrics,
        "scores": scores,
        "summary": summary,
        "strengths": strengths,
        "improvements": improvements,
    }



