"""
Speech-to-text (STT) helpers.

Uses local faster-whisper for transcription. No API key needed.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

FALLBACK_NO_VIDEO = "no_video_path_or_file_missing"
FALLBACK_FFMPEG = "ffmpeg_extract_failed"
FALLBACK_LOCAL_WHISPER = "local_whisper_failed"

_LOCAL_WHISPER_MODEL = None
LOCAL_WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "tiny")

DUMMY_TEXT = (
    "This is a dummy transcript used to exercise the analysis "
    "pipeline end to end. In the real system this will contain the "
    "candidate's actual spoken answer."
)


def _get_duration_seconds(media_path: str) -> Optional[int]:
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


def _transcribe_with_local_whisper(audio_path: str) -> Tuple[Optional[str], Optional[str]]:
    global _LOCAL_WHISPER_MODEL
    try:
        from faster_whisper import WhisperModel
        if _LOCAL_WHISPER_MODEL is None:
            device = os.environ.get("WHISPER_DEVICE", "cpu")
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
    if not video_path or not Path(video_path).exists():
        return DUMMY_TEXT, None, FALLBACK_NO_VIDEO, None

    duration_seconds = _get_duration_seconds(video_path)

    fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        if not _extract_audio(video_path, tmp_path):
            return DUMMY_TEXT, duration_seconds, FALLBACK_FFMPEG, None

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
