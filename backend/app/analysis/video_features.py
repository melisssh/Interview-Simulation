"""
Frame-based interview video analysis using MediaPipe Face/Pose landmarkers.

Produces 0–100 scores for eye contact, head stability, posture, facial expression
proxies, and confidence tone. Falls back to lightweight OpenCV metrics if models
are unavailable.
"""

from __future__ import annotations

import logging
import math
import statistics
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_MODELS_DIR = Path(__file__).resolve().parent / "models"
_FACE_MODEL = _MODELS_DIR / "face_landmarker.task"
_POSE_MODEL = _MODELS_DIR / "pose_landmarker_lite.task"

_FACE_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)
_POSE_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
)

# Face mesh landmark indices (MediaPipe)
_NOSE_TIP = 1
_LEFT_EYE_OUTER = 33
_RIGHT_EYE_OUTER = 263

# Pose landmark indices
_LEFT_SHOULDER = 11
_RIGHT_SHOULDER = 12


def resolve_interview_video_path(
    interview_id: int,
    stored_path: Optional[str] = None,
    uploads_root: Optional[Path] = None,
) -> Optional[str]:
    """Return first existing video file for an interview."""
    if stored_path:
        p = Path(stored_path)
        if p.is_file():
            return str(p.resolve())

    root = uploads_root or (Path("uploads") / "interviews")
    interview_dir = root / str(interview_id)
    if not interview_dir.is_dir():
        return None

    for pattern in ("*.webm", "*.mp4", "*.mov", "*.mkv", "*.avi"):
        matches = sorted(interview_dir.glob(pattern), key=lambda x: x.stat().st_mtime, reverse=True)
        if matches:
            return str(matches[0].resolve())
    return None


def _download_model(url: str, dest: Path) -> bool:
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Downloading MediaPipe model: %s", dest.name)
        urllib.request.urlretrieve(url, dest)
        return dest.is_file() and dest.stat().st_size > 0
    except Exception as e:
        logger.warning("Model download failed (%s): %s", dest.name, e)
        return False


def _ensure_models() -> Tuple[Optional[Path], Optional[Path]]:
    face_ok = _FACE_MODEL.is_file() or _download_model(_FACE_URL, _FACE_MODEL)
    pose_ok = _POSE_MODEL.is_file() or _download_model(_POSE_URL, _POSE_MODEL)
    return (_FACE_MODEL if face_ok else None, _POSE_MODEL if pose_ok else None)


def _clamp_score(value: float, low: float = 0.0, high: float = 100.0) -> int:
    return int(max(low, min(high, round(value))))


def _lm_xy(landmarks: Any, idx: int, w: int, h: int) -> Tuple[float, float]:
    lm = landmarks[idx]
    return lm.x * w, lm.y * h


def _opencv_fallback(video_path: str, sample_every: int = 6) -> Dict[str, Any]:
    """Basic metrics when MediaPipe models are unavailable."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {}

    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    face_centers: List[Tuple[float, float]] = []
    frame_idx = 0
    detected = 0
    sampled = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1
        if frame_idx % sample_every != 0:
            continue
        sampled += 1
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, 1.1, 4, minSize=(80, 80))
        if len(faces) == 0:
            continue
        detected += 1
        x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
        h_img, w_img = frame.shape[:2]
        cx = (x + fw / 2) / w_img
        cy = (y + fh / 2) / h_img
        face_centers.append((cx, cy))

    cap.release()
    if sampled == 0:
        return {}

    detection_rate = detected / sampled
    if detection_rate == 0:
        logger.info("OpenCV fallback: no face detected (detection_rate=0), skipping nonverbal.")
        return {}

    if len(face_centers) < 2:
        stability = 50.0
        centering = 50.0
    else:
        xs = [p[0] for p in face_centers]
        ys = [p[1] for p in face_centers]
        stability = max(0.0, 100.0 - (statistics.pstdev(xs) + statistics.pstdev(ys)) * 400.0)
        centering = max(0.0, 100.0 - statistics.mean(abs(x - 0.5) for x in xs) * 180.0)

    eye = _clamp_score(centering * 0.7 + detection_rate * 30.0)
    head = _clamp_score(stability)
    posture = _clamp_score(55.0 + detection_rate * 25.0)

    return {
        "eye_contact_score": eye,
        "head_stability_score": head,
        "posture_score": posture,
        "video_face_detection_rate": round(detection_rate, 3),
        "video_frames_sampled": sampled,
        "video_analysis_method": "opencv_haar",
    }


def analyze_interview_video(
    video_path: str,
    *,
    target_fps: float = 8.0,
    max_frames: int = 480,
    start_sec: float = 0.0,
    end_sec: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Analyze full interview video and return nonverbal scores (0–100).

    Returns empty dict if video cannot be opened or no usable frames.
    """
    path = Path(video_path)
    if not path.is_file():
        logger.warning("Video not found: %s", video_path)
        return {}

    face_model_path, pose_model_path = _ensure_models()
    if not face_model_path:
        logger.warning("Face landmarker model unavailable; using OpenCV fallback")
        return _opencv_fallback(str(path))

    try:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision
    except ImportError as e:
        logger.warning("MediaPipe tasks import failed: %s", e)
        return _opencv_fallback(str(path))

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return {}

    native_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    sample_every = max(1, int(round(native_fps / max(1.0, target_fps))))

    if start_sec > 0.0:
        cap.set(cv2.CAP_PROP_POS_MSEC, start_sec * 1000.0)

    face_base = mp_python.BaseOptions(model_asset_path=str(face_model_path))
    face_options = vision.FaceLandmarkerOptions(
        base_options=face_base,
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
    )
    face_landmarker = vision.FaceLandmarker.create_from_options(face_options)

    pose_landmarker = None
    if pose_model_path:
        pose_base = mp_python.BaseOptions(model_asset_path=str(pose_model_path))
        pose_options = vision.PoseLandmarkerOptions(
            base_options=pose_base,
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
        )
        pose_landmarker = vision.PoseLandmarker.create_from_options(pose_options)

    eye_scores: List[float] = []
    head_jitter: List[float] = []
    posture_scores: List[float] = []
    frame_idx = 0
    processed = 0
    faces_found = 0
    prev_nose: Optional[Tuple[float, float]] = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1
        current_sec = start_sec + frame_idx / native_fps
        if end_sec is not None and current_sec > end_sec:
            break
        if frame_idx % sample_every != 0:
            continue
        if processed >= max_frames:
            break

        rgb = np.ascontiguousarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        h, w = rgb.shape[:2]
        ts_ms = int(current_sec * 1000)  # absolute video timestamp for MediaPipe
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        face_result = face_landmarker.detect_for_video(mp_image, ts_ms)
        processed += 1

        if not face_result.face_landmarks:
            prev_nose = None
            continue

        faces_found += 1
        lm = face_result.face_landmarks[0]

        nose_x, nose_y = _lm_xy(lm, _NOSE_TIP, w, h)
        le_x, _ = _lm_xy(lm, _LEFT_EYE_OUTER, w, h)
        re_x, _ = _lm_xy(lm, _RIGHT_EYE_OUTER, w, h)

        eye_mid = (le_x + re_x) / 2.0
        face_w = max(1.0, abs(re_x - le_x))
        gaze_offset = abs(nose_x - eye_mid) / (face_w * 0.5)
        frame_center_offset = abs((nose_x / w) - 0.5)
        eye_score = 100.0 - min(100.0, gaze_offset * 35.0 + frame_center_offset * 120.0)
        eye_scores.append(eye_score)

        if prev_nose is not None:
            dx = (nose_x - prev_nose[0]) / w
            dy = (nose_y - prev_nose[1]) / h
            head_jitter.append(math.sqrt(dx * dx + dy * dy))
        prev_nose = (nose_x, nose_y)

        if pose_landmarker is not None:
            pose_result = pose_landmarker.detect_for_video(mp_image, ts_ms)
            if pose_result.pose_landmarks:
                plm = pose_result.pose_landmarks[0]
                ls = plm[_LEFT_SHOULDER]
                rs = plm[_RIGHT_SHOULDER]
                ls_x, ls_y = ls.x * w, ls.y * h
                rs_x, rs_y = rs.x * w, rs.y * h
                shoulder_tilt = abs(ls_y - rs_y) / h
                mid_shoulder_y = (ls_y + rs_y) / 2.0
                shoulder_span = max(1.0, abs(rs_x - ls_x))
                # Head-to-shoulder distance normalized by shoulder width.
                # Works for seated interviews where hips are not in frame.
                head_shoulder_dist = max(0.0, mid_shoulder_y - nose_y)
                upright_ratio = head_shoulder_dist / shoulder_span
                posture_scores.append(
                    max(0.0, min(100.0, 75.0 - shoulder_tilt * 250.0 + min(15.0, upright_ratio * 8.0)))
                )

    cap.release()
    face_landmarker.close()
    if pose_landmarker is not None:
        pose_landmarker.close()

    if processed == 0 or faces_found == 0:
        return _opencv_fallback(str(path))

    detection_rate = faces_found / processed
    if detection_rate < 0.15:
        logger.warning("Low face detection rate (%.2f); fallback", detection_rate)
        return _opencv_fallback(str(path))

    eye_avg = statistics.mean(eye_scores) if eye_scores else 50.0
    if head_jitter:
        jitter_avg = statistics.mean(head_jitter)
        head_score = max(0.0, 100.0 - jitter_avg * 600.0)
    else:
        head_score = 60.0

    posture_avg = statistics.mean(posture_scores) if posture_scores else 58.0

    eye = _clamp_score(eye_avg * 0.85 + detection_rate * 15.0)
    head = _clamp_score(head_score)
    posture = _clamp_score(posture_avg)

    return {
        "eye_contact_score": eye,
        "head_stability_score": head,
        "posture_score": posture,
        "video_face_detection_rate": round(detection_rate, 3),
        "video_frames_sampled": processed,
        "video_faces_detected": faces_found,
        "video_analysis_method": "mediapipe",
    }


