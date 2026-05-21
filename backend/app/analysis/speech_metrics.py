"""Speech and proxy metrics derived from raw PCM and ASR segment timings."""

from __future__ import annotations

import math
import statistics
import struct
from typing import List, Optional, Sequence, Tuple


def pcm_duration_seconds(byte_len: int, sample_rate: int = 48000, sample_width: int = 2) -> float:
    if byte_len <= 0:
        return 0.0
    return byte_len / float(sample_rate * sample_width)


def _window_rms_values(audio_bytes: bytes, sample_rate: int, window_samples: int) -> List[float]:
    n = (len(audio_bytes) // 2) * 2
    if n < window_samples:
        return []
    fmt = "<" + str(n // 2) + "h"
    try:
        samples = struct.unpack(fmt, audio_bytes[:n])
    except struct.error:
        return []
    out: List[float] = []
    for i in range(0, len(samples), window_samples):
        chunk = samples[i : i + window_samples]
        if len(chunk) < max(32, window_samples // 4):
            continue
        mean_sq = sum(s * s for s in chunk) / float(len(chunk))
        out.append(math.sqrt(mean_sq))
    return out


def pcm_volume_stability_score(audio_bytes: bytes, sample_rate: int = 48000) -> int:
    """0–100: steady RMS across short windows = stable volume."""
    window = max(int(sample_rate * 0.08), 64)
    rms = _window_rms_values(audio_bytes, sample_rate, window)
    if len(rms) < 2:
        return 50
    mean_r = sum(rms) / len(rms)
    if mean_r < 1e-6:
        return 50
    cv = statistics.pstdev(rms) / mean_r
    return int(max(35, min(100, 100 - cv * 38)))


def pcm_tone_variation_score(audio_bytes: bytes, sample_rate: int = 48000) -> int:
    """0–100: moderate energy variation reads as expressive but controlled."""
    window = max(int(sample_rate * 0.05), 64)
    rms = _window_rms_values(audio_bytes, sample_rate, window)
    if len(rms) < 4:
        return 55
    mean_r = statistics.mean(rms) + 1e-6
    cv = statistics.pstdev(rms) / mean_r
    if cv < 0.07:
        return 48
    if cv < 0.38:
        return int(68 + min(27, (cv - 0.07) * 100))
    return int(max(52, 95 - (cv - 0.38) * 110))


def pause_frequency_score_from_segments(segment_ranges: Sequence[Tuple[float, float]]) -> int:
    """0–100 from Whisper (start,end): penalize long gaps between segments."""
    segs = sorted(segment_ranges, key=lambda x: x[0])
    if not segs:
        return 50
    if len(segs) == 1:
        return 78
    gaps: List[float] = []
    for i in range(1, len(segs)):
        g = segs[i][0] - segs[i - 1][1]
        if g > 0.04:
            gaps.append(g)
    if not gaps:
        return 82
    long_g = sum(1 for g in gaps if g > 0.85)
    avg = sum(gaps) / len(gaps)
    score = 100.0 - long_g * 13.0 - max(0.0, (avg - 0.32)) * 52.0
    return int(max(0, min(100, score)))


def words_per_minute(word_count: int, duration_seconds: float) -> Optional[int]:
    if duration_seconds <= 0.15 or word_count <= 0:
        return None
    wpm = int(round(word_count / (duration_seconds / 60.0)))
    return max(0, min(320, wpm))


def wpm_clarity_score(wpm: Optional[int]) -> int:
    """0–100: comfortable conversational rate around ~120–150 WPM."""
    if wpm is None or wpm <= 0:
        return 50
    ideal = 135
    return int(max(0, min(100, 100 - abs(wpm - ideal) * 0.55)))
