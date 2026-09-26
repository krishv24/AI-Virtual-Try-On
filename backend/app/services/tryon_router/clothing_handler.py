import sqlite3
from pathlib import Path
from typing import List, Optional

from app.models.schemas import PhotoType
from app.services.catvton_service import catvton_service
from app.services.tryon_router.base import BaseTryOnHandler


class ClothingCatVTONHandler(BaseTryOnHandler):
    """
    Plugin handler for standard apparel/garments using CatVTON neural diffusion on ZeroGPU.
    Routes tops to upper_body, bottoms to legs/full_body, and dresses to full_body.
    """

    @property
    def name(self) -> str:
        return "CatVTON ZeroGPU Clothing Pipeline"

    @property
    def supported_categories(self) -> List[str]:
        return [
            "t-shirt/top",
            "shirt",
            "dress",
            "jacket",
            "pants/trousers",
            "upper",
            "lower",
            "overall",
        ]

    def get_preferred_photo_type(self, category: str) -> PhotoType:
        cat_lower = (category or "").lower()
        if any(w in cat_lower for w in ["pant", "trouser", "jean", "skirt", "short", "lower", "bottom"]):
            return PhotoType.LEGS
        elif any(w in cat_lower for w in ["dress", "gown", "frock", "robe"]):
            return PhotoType.FRONT_FULL_BODY
        else:
            # Tops, shirts, jackets
            return PhotoType.UPPER_BODY

    def get_fallback_photo_type(self, category: str) -> Optional[PhotoType]:
        cat_lower = (category or "").lower()
        if any(w in cat_lower for w in ["pant", "trouser", "jean", "skirt", "short", "lower", "bottom"]):
            return PhotoType.FRONT_FULL_BODY
        elif any(w in cat_lower for w in ["dress", "gown"]):
            return PhotoType.UPPER_BODY
        else:
            return PhotoType.FRONT_FULL_BODY

    def execute(
        self,
        person_photo_path: Path,
        garment_photo_path: Path,
        category: str,
        profile_id: int,
        conn: sqlite3.Connection,
    ) -> Path:
        """
        Executes diffusion synthesis via CatVTON ZeroGPU Space.
        """
        return catvton_service.execute_catvton_inference(
            person_photo_path=person_photo_path,
            garment_photo_path=garment_photo_path,
            category=category,
        )
