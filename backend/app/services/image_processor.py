import io
import os
from pathlib import Path
from typing import Optional, Union
from PIL import Image, ImageOps


class ImageProcessor:
    """
    High-performance image optimization service:
    1. Resizes photos and garment images so max dimension does not exceed max_dim (default 1024px).
    2. Preserves aspect ratios with LANCZOS resampling.
    3. Handles EXIF orientations automatically.
    4. Compresses with optimal quality (JPEG/WebP) to speed up model transfer and ZeroGPU payload delivery.
    """

    MAX_DIMENSION = 1024
    JPEG_QUALITY = 88
    WEBP_QUALITY = 85

    @classmethod
    def optimize_image_bytes(
        cls,
        image_bytes: bytes,
        max_dim: int = MAX_DIMENSION,
        output_format: str = "JPEG",
        quality: int = JPEG_QUALITY,
    ) -> bytes:
        """
        Process in-memory image bytes: cap dimension at max_dim and compress.
        """
        with Image.open(io.BytesIO(image_bytes)) as img:
            img = ImageOps.exif_transpose(img)
            img = cls._resize_if_needed(img, max_dim)

            fmt = output_format.upper()
            if fmt in ["JPEG", "JPG"]:
                if img.mode in ("RGBA", "LA", "P"):
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                    img = bg
                elif img.mode != "RGB":
                    img = img.convert("RGB")
                save_kwargs = {"quality": quality, "optimize": True}
            elif fmt == "WEBP":
                save_kwargs = {"quality": cls.WEBP_QUALITY, "optimize": True}
            else:
                save_kwargs = {"optimize": True}

            buf = io.BytesIO()
            img.save(buf, format="JPEG" if fmt in ["JPEG", "JPG"] else fmt, **save_kwargs)
            return buf.getvalue()

    @classmethod
    def optimize_image_file(
        cls,
        input_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        max_dim: int = MAX_DIMENSION,
        quality: int = JPEG_QUALITY,
    ) -> Path:
        """
        Process an image on disk: caps dimension at max_dim (e.g. 1024px) and compresses.
        Can overwrite in-place or write to a new destination.
        """
        in_p = Path(input_path)
        out_p = Path(output_path) if output_path else in_p

        with Image.open(in_p) as img:
            img = ImageOps.exif_transpose(img)
            w, h = img.size

            ext = out_p.suffix.lower()
            fmt = "PNG" if ext == ".png" else "WEBP" if ext == ".webp" else "JPEG"

            # If already small enough and same format, only save if writing to different path
            if max(w, h) <= max_dim and in_p == out_p:
                return out_p

            resized_img = cls._resize_if_needed(img, max_dim)

            if fmt == "JPEG":
                if resized_img.mode in ("RGBA", "LA", "P"):
                    bg = Image.new("RGB", resized_img.size, (255, 255, 255))
                    bg.paste(
                        resized_img,
                        mask=resized_img.split()[-1] if resized_img.mode in ("RGBA", "LA") else None,
                    )
                    resized_img = bg
                elif resized_img.mode != "RGB":
                    resized_img = resized_img.convert("RGB")
                save_kwargs = {"quality": quality, "optimize": True}
            elif fmt == "WEBP":
                save_kwargs = {"quality": cls.WEBP_QUALITY, "optimize": True}
            else:
                save_kwargs = {"optimize": True}

            resized_img.save(out_p, format=fmt, **save_kwargs)
            return out_p

    @classmethod
    def _resize_if_needed(cls, img: Image.Image, max_dim: int) -> Image.Image:
        w, h = img.size
        if max(w, h) > max_dim:
            scale = max_dim / float(max(w, h))
            new_w = max(1, int(round(w * scale)))
            new_h = max(1, int(round(h * scale)))
            return img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        return img


image_processor = ImageProcessor()
