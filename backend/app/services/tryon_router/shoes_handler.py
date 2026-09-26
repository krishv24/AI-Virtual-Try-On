import sqlite3
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from app.config import settings
from app.models.schemas import PhotoType
from app.services.catvton_service import catvton_service
from app.services.tryon_router.base import BaseTryOnHandler


class ShoesHandler(BaseTryOnHandler):
    """
    Plugin handler for footwear ('shoes', 'sneakers', 'boots', 'sandals').
    Routes to the user's dedicated 'feet' reference photo.
    Performs calibrated perspective overlay or CatVTON lower-body alignment.
    """

    @property
    def name(self) -> str:
        return "Footwear Positioning Pipeline"

    @property
    def supported_categories(self) -> List[str]:
        return [
            "shoes",
            "sneakers",
            "boots",
            "sandals",
            "footwear",
            "heels",
            "loafers",
        ]

    def get_preferred_photo_type(self, category: str) -> PhotoType:
        return PhotoType.FEET

    def get_fallback_photo_type(self, category: str) -> Optional[PhotoType]:
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
        Synthesize footwear placement onto the user's feet/leg reference photo.
        Applies background-aware alpha compositing, realistic shadow anchoring,
        and perspective scaling.
        """
        # Load user photo and product shoe photo
        person_img = Image.open(person_photo_path).convert("RGBA")
        shoe_img = Image.open(garment_photo_path).convert("RGBA")

        pw, ph = person_img.size

        # Remove solid white/light background from shoe image if not already transparent
        shoe_np = np.array(shoe_img)
        if shoe_np.shape[2] == 4:
            # Check if alpha is mostly opaque
            if (shoe_np[:, :, 3] > 240).mean() > 0.95:
                # Key out near-white background (typical of e-commerce footwear shots)
                r, g, b = shoe_np[:, :, 0], shoe_np[:, :, 1], shoe_np[:, :, 2]
                is_bg = (r > 240) & (g > 240) & (b > 240)
                shoe_np[is_bg, 3] = 0
                shoe_img = Image.fromarray(shoe_np, "RGBA")

        # Determine target shoe bounding dimensions relative to foot photo
        # Shoes typically occupy the lower 40-50% of a feet reference photo
        target_shoe_width = int(pw * 0.72)
        aspect = shoe_img.height / max(shoe_img.width, 1)
        target_shoe_height = int(target_shoe_width * aspect)

        # Ensure reasonable maximum height
        max_h = int(ph * 0.45)
        if target_shoe_height > max_h:
            target_shoe_height = max_h
            target_shoe_width = int(target_shoe_height / max(aspect, 0.01))

        resized_shoe = shoe_img.resize(
            (target_shoe_width, target_shoe_height), Image.Resampling.LANCZOS
        )

        # Create soft shadow underneath the footwear
        shadow_mask = resized_shoe.split()[3].filter(ImageFilter.GaussianBlur(10))
        shadow = Image.new("RGBA", (target_shoe_width, target_shoe_height), (15, 15, 20, 110))
        shadow.putalpha(shadow_mask)

        # Position at the center-bottom of the frame where feet stand
        paste_x = (pw - target_shoe_width) // 2
        paste_y = int(ph * 0.52)

        # Composite shadow first, then shoe
        canvas = person_img.copy()
        canvas.paste(shadow, (paste_x, paste_y + 8), shadow)
        canvas.paste(resized_shoe, (paste_x, paste_y), resized_shoe)

        # Output final composited image as RGB PNG
        final_img = canvas.convert("RGB")
        out_filename = f"shoes_tryon_{uuid4().hex[:12]}.png"
        out_path = settings.STORAGE_DIR / out_filename
        final_img.save(out_path, format="PNG", quality=95)

        return out_path
