import io
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
from PIL import Image

TARGET_CATEGORIES: List[str] = [
    "t-shirt/top",
    "shirt",
    "dress",
    "jacket",
    "pants/trousers",
    "shoes",
    "jewellery",
    "necklace",
    "accessory",
]

# Enriched prompts for high zero-shot CLIP contrast
CATEGORY_PROMPTS: Dict[str, str] = {
    "t-shirt/top": "a photo of a casual t-shirt or graphic tee top",
    "shirt": "a photo of a button-down collared dress shirt or formal blouse",
    "dress": "a photo of a one-piece dress, frock, or evening gown",
    "jacket": "a photo of a jacket, coat, blazer, hoodie, or outerwear",
    "pants/trousers": "a photo of pants, trousers, jeans, sweatpants, or shorts",
    "shoes": "a photo of a pair of shoes, sneakers, boots, or sandals",
    "jewellery": "a photo of jewellery, earrings, bracelet, or rings",
    "necklace": "a photo of a necklace, pendant, chain, or choker",
    "accessory": "a photo of a fashion accessory, sunglasses, belt, scarf, or handbag",
}

KEYWORD_MAP: Dict[str, List[str]] = {
    "t-shirt/top": ["t-shirt", "tshirt", "tee", "top", "crop top", "tank"],
    "shirt": ["shirt", "button-down", "blouse", "collared", "polo"],
    "dress": ["dress", "gown", "frock", "maxi", "midi", "sundress"],
    "jacket": ["jacket", "coat", "overcoat", "blazer", "hoodie", "cardigan", "sweater", "outerwear", "parka", "windbreaker"],
    "pants/trousers": ["pant", "pants", "trouser", "trousers", "jean", "jeans", "denim", "short", "shorts", "jogger", "legging"],
    "shoes": ["shoe", "shoes", "sneaker", "sneakers", "boot", "boots", "sandal", "sandals", "heel", "heels", "loafer", "footwear"],
    "necklace": ["necklace", "choker", "pendant", "chain", "locket"],
    "jewellery": ["jewel", "jewellery", "jewelry", "earring", "earrings", "ring", "rings", "bracelet", "bangle"],
    "accessory": ["accessory", "sunglass", "sunglasses", "glasses", "belt", "scarf", "hat", "cap", "bag", "handbag", "purse", "wallet"],
}


class CLIPClassifier:
    """
    CLIP-based zero-shot garment and product classifier.
    Classifies product images into 9 standard fashion categories.
    Uses open-weight CLIP from transformers with lazy loading and local caching.
    """

    def __init__(self, model_name: str = "openai/clip-vit-base-patch32"):
        self.model_name = model_name
        self._model = None
        self._processor = None
        self._text_features = None

    def _ensure_model_loaded(self):
        """Lazily load the CLIP model and processor on first call."""
        if self._model is None:
            try:
                import torch
                from transformers import CLIPModel, CLIPProcessor
                from app.config import settings

                token = settings.HF_TOKEN if settings.HF_TOKEN else None
                self._processor = CLIPProcessor.from_pretrained(self.model_name, token=token)
                self._model = CLIPModel.from_pretrained(self.model_name, token=token)
                self._model.eval()

                # Precompute text embeddings for the 9 target categories
                prompts = [CATEGORY_PROMPTS[cat] for cat in TARGET_CATEGORIES]
                inputs = self._processor(text=prompts, return_tensors="pt", padding=True)
                with torch.no_grad():
                    text_embeds = self._model.get_text_features(**inputs)
                    self._text_features = text_embeds / text_embeds.norm(dim=-1, keepdim=True)
            except Exception as e:
                # Keep None so fallback heuristic can be used
                self._model = None

    def classify_from_text(self, text: str) -> Optional[Tuple[str, float]]:
        """Fast keyword/regex classifier based on product title/category description."""
        if not text:
            return None
        text_lower = text.lower()

        # Check in priority order: necklace first before general jewellery/accessory
        for cat in ["necklace", "jewellery", "shoes", "dress", "jacket", "shirt", "t-shirt/top", "pants/trousers", "accessory"]:
            keywords = KEYWORD_MAP.get(cat, [])
            for kw in keywords:
                if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
                    return cat, 0.88
        return None

    def classify_image(
        self,
        image_input: Union[str, Path, bytes, Image.Image],
        text_hint: Optional[str] = None,
    ) -> Dict[str, any]:
        """
        Classify product image into one of the 9 target categories.
        Returns:
            {
                "category": str,
                "confidence": float,
                "all_scores": Dict[str, float],
                "method": "clip" | "text_hint" | "heuristic"
            }
        """
        # 1. Check strong text hint first if available
        text_match = self.classify_from_text(text_hint) if text_hint else None

        # 2. Convert input to PIL image
        pil_img = None
        try:
            if isinstance(image_input, (str, Path)):
                pil_img = Image.open(image_input).convert("RGB")
            elif isinstance(image_input, bytes):
                pil_img = Image.open(io.BytesIO(image_input)).convert("RGB")
            elif isinstance(image_input, Image.Image):
                pil_img = image_input.convert("RGB")
        except Exception:
            pass

        # 3. Try CLIP Inference
        self._ensure_model_loaded()
        if self._model is not None and self._processor is not None and pil_img is not None:
            try:
                import torch

                inputs = self._processor(images=pil_img, return_tensors="pt")
                with torch.no_grad():
                    image_features = self._model.get_image_features(**inputs)
                    image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                    # Cosine similarities
                    similarity = (image_features @ self._text_features.T)[0]
                    # Temperature scaling
                    probs = torch.nn.functional.softmax(similarity * 20.0, dim=-1).cpu().numpy()

                scores = {cat: float(probs[i]) for i, cat in enumerate(TARGET_CATEGORIES)}

                # If text hint reinforces a category, blend with text prior
                if text_match:
                    hint_cat, hint_conf = text_match
                    for cat in scores:
                        prior = hint_conf if cat == hint_cat else ((1.0 - hint_conf) / (len(TARGET_CATEGORIES) - 1))
                        scores[cat] = 0.35 * scores[cat] + 0.65 * prior
                    total = sum(scores.values())
                    scores = {k: v / total for k, v in scores.items()}

                best_category = max(scores, key=scores.get)
                confidence = float(scores[best_category])

                return {
                    "category": best_category,
                    "confidence": round(confidence, 4),
                    "all_scores": {k: round(v, 4) for k, v in scores.items()},
                    "method": "clip",
                }
            except Exception:
                pass

        # 4. Fallback: If text match exists
        if text_match:
            cat, conf = text_match
            scores = {c: 0.05 for c in TARGET_CATEGORIES}
            scores[cat] = conf
            return {
                "category": cat,
                "confidence": conf,
                "all_scores": scores,
                "method": "text_hint",
            }

        # 5. Default fallback based on image aspect ratio
        if pil_img is not None:
            w, h = pil_img.size
            aspect = h / max(w, 1)
            # Very tall images are often dresses or pants
            if aspect > 1.8:
                cat = "pants/trousers"
            elif aspect > 1.4:
                cat = "dress"
            # Wide or small square images are often shoes or accessories
            elif aspect < 0.7:
                cat = "shoes"
            else:
                cat = "t-shirt/top"
        else:
            cat = "t-shirt/top"

        return {
            "category": cat,
            "confidence": 0.60,
            "all_scores": {c: (0.60 if c == cat else 0.05) for c in TARGET_CATEGORIES},
            "method": "heuristic",
        }


# Singleton instance
clip_classifier = CLIPClassifier()
