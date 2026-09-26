import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from PIL import Image, ImageFilter, ImageOps

logger = logging.getLogger("accuracy_safeguard")
logger.setLevel(logging.INFO)


class AccuracyValidator:
    """
    Phase 9: Product Accuracy Safeguard Validator.
    Compares the dominant colors, color histogram distribution, and rough pattern/texture
    of the generated try-on garment region against the original product garment image.
    Flags results as 'low confidence' if color or pattern drift exceeds safety thresholds.
    """

    # Low-confidence threshold (below 0.50 composite similarity is flagged)
    THRESHOLD_LOW_CONFIDENCE = 0.50

    def extract_garment_mask_pixels(self, img: Image.Image) -> np.ndarray:
        """
        Extract non-background RGB pixel array from garment product image.
        Filters out alpha transparent pixels and studio white/light backgrounds.
        """
        img_rgba = img.convert("RGBA")
        arr = np.array(img_rgba)
        r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]

        # Ignore transparent or light neutral studio background pixels (white, gray)
        is_transparent = a < 50
        is_light = (r > 205) & (g > 205) & (b > 205)
        is_neutral = (np.abs(r.astype(int) - g.astype(int)) < 16) & (np.abs(g.astype(int) - b.astype(int)) < 16)
        is_bg = is_transparent | (is_light & is_neutral)

        fg_pixels = arr[~is_bg][:, :3]
        if len(fg_pixels) < 50:
            # Fallback to all pixels if image is completely white or unusual
            return arr[:, :, :3].reshape(-1, 3)
        return fg_pixels

    def extract_roi_from_composited(
        self, composited_img: Image.Image, category: str = "upper"
    ) -> np.ndarray:
        """
        Crop the expected garment Region of Interest (ROI) from the generated image
        based on the garment category (upper body, lower body, shoes, or accessory).
        """
        w, h = composited_img.size
        cat_lower = (category or "").lower()

        if any(w in cat_lower for w in ["pant", "trouser", "jean", "skirt", "short", "lower"]):
            # Pants/lower: 45% to 85% height, center 70% width
            crop_box = (int(w * 0.15), int(h * 0.45), int(w * 0.85), int(h * 0.88))
        elif any(w in cat_lower for w in ["shoe", "foot", "feet", "boot", "sandal"]):
            # Shoes: 55% to 98% height
            crop_box = (int(w * 0.10), int(h * 0.55), int(w * 0.90), int(h * 0.98))
        elif any(w in cat_lower for w in ["dress", "gown", "overall"]):
            # Full dress: 20% to 85% height
            crop_box = (int(w * 0.15), int(h * 0.20), int(w * 0.85), int(h * 0.85))
        elif any(w in cat_lower for w in ["jewel", "necklace", "chain", "accessory"]):
            # Neck/collar region: 15% to 45% height, center 50%
            crop_box = (int(w * 0.25), int(h * 0.18), int(w * 0.75), int(h * 0.48))
        else:
            # Standard tops/shirts/jackets: 22% to 62% height, center 70% width
            crop_box = (int(w * 0.15), int(h * 0.22), int(w * 0.85), int(h * 0.65))

        cropped = composited_img.crop(crop_box)
        return self.extract_garment_mask_pixels(cropped)

    def compute_color_histogram(self, pixels: np.ndarray, bins_per_channel: int = 8) -> np.ndarray:
        """
        Compute a normalized 3D color histogram in RGB space.
        """
        hist, _ = np.histogramdd(
            pixels,
            bins=(bins_per_channel, bins_per_channel, bins_per_channel),
            range=((0, 256), (0, 256), (0, 256)),
        )
        total = hist.sum()
        if total > 0:
            hist = hist / total
        return hist.flatten()

    def get_dominant_color(self, pixels: np.ndarray) -> np.ndarray:
        """
        Calculate the median/dominant color vector (R, G, B).
        """
        if len(pixels) == 0:
            return np.array([128, 128, 128], dtype=float)
        return np.median(pixels, axis=0)

    def compute_pattern_roughness(self, img: Image.Image) -> float:
        """
        Compute high-frequency spatial variation (edge gradient density)
        to capture rough garment patterns (stripes, checks, florals vs solid plains).
        """
        gray = img.convert("L").resize((128, 128), Image.Resampling.BILINEAR)
        edges = gray.filter(ImageFilter.FIND_EDGES)
        arr = np.array(edges, dtype=float)
        # Ratio of strong edge pixels
        edge_density = float((arr > 40).mean())
        return edge_density

    def validate_accuracy(
        self,
        original_garment_input: Union[str, Path, Image.Image],
        composited_result_input: Union[str, Path, Image.Image],
        category: str = "upper",
    ) -> Dict[str, Any]:
        """
        Run the post-generation accuracy check:
        Compares dominant color palette, color histogram similarity, and pattern roughness.
        Returns detailed metrics and low-confidence flag.
        """
        # 1. Load images
        if isinstance(original_garment_input, (str, Path)):
            orig_img = Image.open(original_garment_input)
        else:
            orig_img = original_garment_input

        if isinstance(composited_result_input, (str, Path)):
            comp_img = Image.open(composited_result_input)
        else:
            comp_img = composited_result_input

        # 2. Extract pixels
        orig_pixels = self.extract_garment_mask_pixels(orig_img)
        comp_roi_pixels = self.extract_roi_from_composited(comp_img, category=category)

        # 3. Dominant Color Delta & Vector Alignment
        dom_orig = self.get_dominant_color(orig_pixels)
        dom_comp = self.get_dominant_color(comp_roi_pixels)
        euclidean_dist = float(np.linalg.norm(dom_orig - dom_comp))
        max_dist = 255.0 * np.sqrt(3.0)  # ~441.67
        dominant_color_delta = round(float(euclidean_dist / max_dist), 4)
        dominant_sim = round(max(0.0, 1.0 - (dominant_color_delta * 1.6)), 4)

        # 4. Color Distribution Similarity (channel means & variance spread)
        mean_orig = np.mean(orig_pixels, axis=0)
        mean_comp = np.mean(comp_roi_pixels, axis=0)
        mean_diff = float(np.linalg.norm(mean_orig - mean_comp) / max_dist)
        mean_sim = max(0.0, 1.0 - (mean_diff * 1.5))

        std_orig = np.std(orig_pixels, axis=0) if len(orig_pixels) > 1 else np.zeros(3)
        std_comp = np.std(comp_roi_pixels, axis=0) if len(comp_roi_pixels) > 1 else np.zeros(3)
        std_diff = float(np.linalg.norm(std_orig - std_comp) / (128.0 * np.sqrt(3.0)))
        std_sim = max(0.0, 1.0 - std_diff)

        color_similarity = round(float(0.65 * mean_sim + 0.35 * std_sim), 4)

        # 5. Pattern Roughness (Solid vs Patterned)
        rough_orig = self.compute_pattern_roughness(orig_img)
        rough_comp = self.compute_pattern_roughness(comp_img)
        pattern_diff = abs(rough_orig - rough_comp)
        pattern_similarity = round(max(0.0, 1.0 - (pattern_diff * 4.0)), 4)

        # 6. Composite Accuracy Score
        # Weighting: 55% color distribution, 30% dominant hue, 15% pattern/texture
        composite_score = round(
            float(0.55 * color_similarity + 0.30 * dominant_sim + 0.15 * pattern_similarity), 4
        )

        is_low_confidence = composite_score < self.THRESHOLD_LOW_CONFIDENCE

        # Identify flag reason if low confidence
        flag_reason = None
        if is_low_confidence:
            if dominant_color_delta > 0.35:
                flag_reason = f"Noticeable color deviation: dominant tone shifted by {int(dominant_color_delta * 100)}%"
            elif color_similarity < 0.30:
                flag_reason = "Significant color distribution difference between product and generated result"
            elif pattern_similarity < 0.40:
                flag_reason = "Pattern roughness deviation (possible fabric distortion or pattern blurring)"
            else:
                flag_reason = f"Overall product fidelity score below safety threshold ({int(composite_score * 100)}%)"

        metrics = {
            "accuracy_score": composite_score,
            "is_low_confidence": is_low_confidence,
            "color_similarity": color_similarity,
            "dominant_color_delta": dominant_color_delta,
            "pattern_similarity": pattern_similarity,
            "flag_reason": flag_reason,
            "primary_product_color_rgb": [int(c) for c in dom_orig],
            "primary_result_color_rgb": [int(c) for c in dom_comp],
        }

        # Log metric per result for technical documentation reporting
        logger.info(
            "ACCURACY_SAFEGUARD_AUDIT | category=%s score=%.4f low_confidence=%s color_sim=%.4f dom_delta=%.4f pattern_sim=%.4f reason=%s",
            category,
            composite_score,
            is_low_confidence,
            color_similarity,
            dominant_color_delta,
            pattern_similarity,
            flag_reason or "PASS",
        )

        return metrics


accuracy_validator = AccuracyValidator()
