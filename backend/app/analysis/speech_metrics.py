"""Speech and proxy metrics derived from raw PCM and ASR segment timings."""

from __future__ import annotations

import math
import statistics
import struct
from typing import List, Optional


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


def pause_frequency_score_from_pcm(audio_bytes: bytes, sample_rate: int = 48000) -> int:
    """
    0–100 fluency score from raw PCM by detecting actual silence-based pauses.

    Divides audio into 80 ms windows, computes RMS per window, then finds
    runs of silence (< 12 % of mean speech energy for ≥ 200 ms) as pauses.
    Penalises high pause count and high silence ratio.
    Falls back to 65 if audio is too short or too quiet.
    """
    window_ms = 80
    window_samples = max(64, int(sample_rate * window_ms / 1000))
    rms_vals = _window_rms_values(audio_bytes, sample_rate, window_samples)

    if len(rms_vals) < 5:
        return 65

    mean_rms = sum(rms_vals) / len(rms_vals)
    if mean_rms < 30:          # essentially silent / very quiet recording
        return 55

    threshold = mean_rms * 0.12

    # Identify silence windows and group into runs (≥ 3 windows = ≥ 240 ms)
    pause_count = 0
    total_silence = 0
    run_len = 0
    max_run = 0
    for rms in rms_vals:
        if rms < threshold:
            run_len += 1
            total_silence += 1
        else:
            if run_len >= 3:
                pause_count += 1
                max_run = max(max_run, run_len)
            run_len = 0
    if run_len >= 3:
        pause_count += 1
        max_run = max(max_run, run_len)

    silence_ratio = total_silence / len(rms_vals)

    # Penalise:  >2 pauses costs 8 pts each; >25 % silence adds extra penalty
    pause_penalty   = max(0, (pause_count - 2) * 8)
    silence_penalty = max(0.0, (silence_ratio - 0.25) * 120.0)
    score = 90.0 - pause_penalty - silence_penalty
    return int(max(20, min(100, round(score))))


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
