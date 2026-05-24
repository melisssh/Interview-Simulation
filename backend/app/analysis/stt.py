"""
Speech-to-text (STT) helpers.

Uses OpenAI Whisper API when OPENAI_API_KEY is set and has quota.
Otherwise falls back to local Whisper (faster-whisper). No API key or billing needed for local.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

# Reason returned when we fall back to dummy (for debugging)
FALLBACK_NO_VIDEO = "no_video_path_or_file_missing"
FALLBACK_FFMPEG = "ffmpeg_extract_failed"
FALLBACK_WHISPER_API = "whisper_api_failed"
FALLBACK_LOCAL_WHISPER = "local_whisper_failed"

# Local Whisper model (lazy-loaded). "tiny" = fastest, "base" = better quality.
_LOCAL_WHISPER_MODEL = None
LOCAL_WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "tiny")

DUMMY_TEXT = (
    "This is a dummy transcript used to exercise the analysis "
    "pipeline end to end. In the real system this will contain the "
    "candidate's actual spoken answer."
)


def _get_duration_seconds(media_path: str) -> Optional[int]:
    """Get duration in seconds using ffprobe. Returns None if ffprobe fails."""
    try:
        out = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                media_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if out.returncode == 0 and out.stdout.strip():
            return int(float(out.stdout.strip()))
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    return None


def _extract_audio(video_path: str, out_path: str) -> bool:
    """Extract audio from video to out_path (e.g. .mp3). Returns True on success."""
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i", video_path,
                "-vn",
                "-acodec", "libmp3lame",
                "-q:a", "2",
                out_path,
            ],
            capture_output=True,
            timeout=300,
        )
        return Path(out_path).exists()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _transcribe_with_whisper_api(audio_path: str) -> Tuple[Optional[str], Optional[str]]:
    """Call OpenAI Whisper API. Returns (transcript, error_message)."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or not api_key.strip():
        return None, "API key empty"
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key.strip())
        with open(audio_path, "rb") as f:
            resp = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
            )
        text = resp.text if hasattr(resp, "text") else str(resp)
        return (text, None)
    except Exception as e:
        return None, str(e)


def _transcribe_with_local_whisper(audio_path: str) -> Tuple[Optional[str], Optional[str]]:
    """Transcribe using local faster-whisper (no API key). Returns (transcript, error_message)."""
    global _LOCAL_WHISPER_MODEL
    try:
        from faster_whisper import WhisperModel
        if _LOCAL_WHISPER_MODEL is None:
            # MacBook Metal GPU acceleration
            device = os.environ.get("WHISPER_DEVICE", "cpu")  # "metal" or "cpu"
            # Metal device ise float32, CPU ise int8 quantization
            compute_type = "float32" if device == "metal" else "int8"

            _LOCAL_WHISPER_MODEL = WhisperModel(
                LOCAL_WHISPER_MODEL_SIZE,
                device=device,
                compute_type=compute_type,
            )
        segments, _ = _LOCAL_WHISPER_MODEL.transcribe(audio_path)
        parts = [s.text for s in segments if s.text]
        text = " ".join(parts).strip() if parts else None
        return (text, None) if text else (None, "No speech detected")
    except Exception as e:
        return None, str(e)


def get_transcript(
    interview_id: int,
    video_path: Optional[str] = None,
) -> Tuple[str, Optional[int], Optional[str], Optional[str]]:
    """
    Return transcript, duration, fallback_reason, and optional error_detail.

    When Whisper fails, error_detail contains the exception message for debugging.
    """
    if not video_path or not Path(video_path).exists():
        return DUMMY_TEXT, None, FALLBACK_NO_VIDEO, None

    duration_seconds = _get_duration_seconds(video_path)

    fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        if not _extract_audio(video_path, tmp_path):
            return DUMMY_TEXT, duration_seconds, FALLBACK_FFMPEG, None

        # 1) Try OpenAI API if key is set
        api_key = os.environ.get("OPENAI_API_KEY") and os.environ.get("OPENAI_API_KEY").strip()
        if api_key:
            text, api_error = _transcribe_with_whisper_api(tmp_path)
            if text and text.strip():
                return text.strip(), duration_seconds, None, None

        # 2) Fallback: local Whisper (no API key or quota needed)
        text, local_error = _transcribe_with_local_whisper(tmp_path)
        if text and text.strip():
            return text.strip(), duration_seconds, None, None
        return DUMMY_TEXT, duration_seconds, FALLBACK_LOCAL_WHISPER, local_error
    finally:
        if Path(tmp_path).exists():
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
