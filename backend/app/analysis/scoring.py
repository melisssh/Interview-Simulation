"""
Pause / fluency proxy score derived from filler-word density in answer transcripts.
Used as a text-based fallback when no PCM audio data is available.
"""

# English filler / hesitation words
FILLER_WORDS_EN = [
    "um", "uh", "like", "you know", "basically", "actually", "literally",
    "i mean", "you see", "kind of", "sort of", "right so",
]


def _normalize_word(word: str) -> str:
    return word.strip(".,!?;:()[]\"'").lower()


def pause_control_from_answer_text(text: str) -> int:
    """
    0–100 pause / fluency proxy from a single answer transcript (English filler density).
    Used as a text-based fallback when no PCM audio data is available.
    """
    words = [_normalize_word(w) for w in (text or "").split() if _normalize_word(w)]
    total_words = len(words)
    if total_words == 0:
        return 45
    filler_count = sum(1 for w in words if w in FILLER_WORDS_EN)
    filler_ratio = filler_count / total_words if total_words else 0.0
    if filler_ratio >= 0.4:
        return 0
    return int(max(0, min(100, 100 - (filler_ratio / 0.35) * 100)))


