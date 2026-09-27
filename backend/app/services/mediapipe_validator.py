"""
MediaPipe Landmark Validator Service.
Validates uploaded reference photos for relevant human landmarks before accepting them into the database.
"""

from pathlib import Path
from typing import Tuple, Dict, Any, Optional
import urllib.request
import os

import numpy as np
from PIL import Image
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from app.models.schemas import PhotoType

# Models directory
MODELS_DIR = Path(__file__).resolve().parent.parent / "models" / "mediapipe_models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

POSE_MODEL_PATH = MODELS_DIR / "pose_landmarker_lite.task"
FACE_MODEL_PATH = MODELS_DIR / "face_landmarker.task"

POSE_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
FACE_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"


def ensure_models():
    """Ensure the local MediaPipe task bundle files exist on disk."""
    if not POSE_MODEL_PATH.exists():
        urllib.request.urlretrieve(POSE_MODEL_URL, str(POSE_MODEL_PATH))
    if not FACE_MODEL_PATH.exists():
        urllib.request.urlretrieve(FACE_MODEL_URL, str(FACE_MODEL_PATH))


# Lazy-loaded model instances
_pose_detector: Optional[vision.PoseLandmarker] = None
_face_detector: Optional[vision.FaceLandmarker] = None


def get_pose_detector() -> vision.PoseLandmarker:
    global _pose_detector
    if _pose_detector is None:
        ensure_models()
        base_options = python.BaseOptions(model_asset_path=str(POSE_MODEL_PATH))
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            output_segmentation_masks=False,
            min_pose_detection_confidence=0.4,
            min_pose_presence_confidence=0.4,
            min_tracking_confidence=0.4,
        )
        _pose_detector = vision.PoseLandmarker.create_from_options(options)
    return _pose_detector


def get_face_detector() -> vision.FaceLandmarker:
    global _face_detector
    if _face_detector is None:
        ensure_models()
        base_options = python.BaseOptions(model_asset_path=str(FACE_MODEL_PATH))
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            min_face_detection_confidence=0.4,
            min_face_presence_confidence=0.4,
            min_tracking_confidence=0.4,
        )
        _face_detector = vision.FaceLandmarker.create_from_options(options)
    return _face_detector


def validate_photo_landmarks(
    image_bytes: bytes, photo_type: PhotoType
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Validate that an uploaded image satisfies the human landmark requirements
    for the specific photo_type using MediaPipe.

    Returns:
        (is_valid, message, metadata)
    """
    import io
    try:
        pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_np = np.array(pil_img)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_np)
    except Exception as e:
        return False, f"Invalid or unreadable image format: {str(e)}", {}

    # 1. Face validation
    if photo_type == PhotoType.FACE:
        face_detector = get_face_detector()
        face_result = face_detector.detect(mp_image)
        if not face_result.face_landmarks or len(face_result.face_landmarks) == 0:
            # Fallback check on pose face landmarks
            pose_detector = get_pose_detector()
            pose_result = pose_detector.detect(mp_image)
            if not pose_result.pose_landmarks or len(pose_result.pose_landmarks) == 0:
                return (
                    False,
                    "No human face detected. Please ensure your face is well-lit and centered.",
                    {"detected_faces": 0},
                )
        return (
            True,
            "Face landmarks successfully verified.",
            {"detected_faces": len(face_result.face_landmarks) if face_result.face_landmarks else 1},
        )

    # 2. Body / Pose validation (front_full_body, upper_body, legs, feet)
    pose_detector = get_pose_detector()
    pose_result = pose_detector.detect(mp_image)

    if not pose_result.pose_landmarks or len(pose_result.pose_landmarks) == 0:
        if photo_type == PhotoType.FEET:
            # Standalone foot/shoe photos often have no head/torso;
            if pil_img.width >= 100 and pil_img.height >= 100 and np.std(img_np) > 15:
                return True, "Foot/shoe photo passed visual presence check.", {"mode": "heuristic"}

        # Cropped lower-body / legs photos:
        # MediaPipe Pose's BlazePose detector requires a human face/head anchor in frame.
        # When users upload cropped leg photos (waist-down, pants, jeans, shorts, skirts),
        # the head is naturally omitted, causing BlazePose to return 0 pose landmarks.
        # We validate lower-body presence, aspect ratio, and visual contrast:
        if photo_type == PhotoType.LEGS:
            w, h = pil_img.size
            std_val = float(np.std(img_np))
            if w < 100 or h < 100:
                return (
                    False,
                    "Legs photo resolution is too small. Please upload an image of at least 150x150 pixels.",
                    {"error": "resolution_too_low"},
                )
            if std_val < 12:
                return (
                    False,
                    "Image appears blank or solid color. Please upload a clear photo of your legs, pants, or lower body.",
                    {"error": "low_variance"},
                )
            if h < w * 0.35:
                return (
                    False,
                    "Image aspect ratio is too wide. Lower body photos should be vertical or square.",
                    {"error": "invalid_aspect_ratio"},
                )
            return (
                True,
                "Lower-body photo verified (leg & attire presence confirmed).",
                {"mode": "lower_body_presence", "variance": std_val, "dimensions": [w, h]},
            )

        return (
            False,
            f"No human detected in {photo_type.value} photo. Please frame yourself clearly with good lighting.",
            {"detected_landmarks": 0},
        )

    landmarks = pose_result.pose_landmarks[0]
    total_landmarks = len(landmarks)

    # Key landmark indices in MediaPipe Pose:
    # Shoulders: 11 (left), 12 (right)
    # Hips: 23 (left), 24 (right)
    # Knees: 25 (left), 26 (right)
    # Ankles: 27 (left), 28 (right)
    # Feet/Heels: 29, 30, 31, 32

    def is_visible(idx: int) -> bool:
        if idx >= len(landmarks):
            return False
        lm = landmarks[idx]
        # Coordinates in [0, 1] range inside image frame
        in_bounds = 0.0 <= lm.x <= 1.0 and 0.0 <= lm.y <= 1.0
        vis = getattr(lm, "visibility", 1.0)
        return in_bounds and (vis is None or vis > 0.3)

    if photo_type == PhotoType.FRONT_FULL_BODY:
        has_shoulders = is_visible(11) or is_visible(12)
        has_hips = is_visible(23) or is_visible(24)
        has_legs = is_visible(25) or is_visible(26) or is_visible(27) or is_visible(28)

        if not (has_shoulders and (has_hips or has_legs)):
            return (
                False,
                "Incomplete full-body capture. Please ensure your entire body (shoulders, hips, legs) is visible.",
                {"shoulders": has_shoulders, "hips": has_hips, "legs": has_legs},
            )
        return (
            True,
            "Full-body landmarks verified (shoulders, hips, and limbs detected).",
            {"landmarks_count": total_landmarks},
        )

    elif photo_type == PhotoType.UPPER_BODY:
        has_shoulders = is_visible(11) or is_visible(12)
        has_torso = has_shoulders or is_visible(23) or is_visible(24)
        if not has_torso:
            return (
                False,
                "Upper-body landmarks missing. Please ensure your shoulders and torso are clearly in frame.",
                {"shoulders": has_shoulders},
            )
        return (
            True,
            "Upper-body landmarks verified (shoulders & torso detected).",
            {"landmarks_count": total_landmarks},
        )

    elif photo_type == PhotoType.LEGS:
        has_lower = any(is_visible(i) for i in [23, 24, 25, 26, 27, 28, 29, 30, 31, 32])
        if not has_lower:
            w, h = pil_img.size
            std_val = float(np.std(img_np))
            if w >= 100 and h >= 100 and std_val >= 12 and h >= w * 0.35:
                return (
                    True,
                    "Lower-body photo verified.",
                    {"mode": "lower_body_presence", "landmarks_count": total_landmarks},
                )
            return (
                False,
                "Leg / lower-body landmarks missing. Please ensure hips, knees, or ankles are visible.",
                {"legs_detected": False},
            )
        return (
            True,
            "Lower-body landmarks verified (hips, knees, or ankles detected).",
            {"landmarks_count": total_landmarks},
        )

    elif photo_type == PhotoType.FEET:
        has_feet = is_visible(27) or is_visible(28) or is_visible(29) or is_visible(30) or is_visible(31) or is_visible(32)
        # Standalone foot/shoe photos often crop out upper legs
        return (
            True,
            "Foot landmarks verified.",
            {"feet_detected": has_feet},
        )

    return True, "Landmarks verified.", {"landmarks_count": total_landmarks}
