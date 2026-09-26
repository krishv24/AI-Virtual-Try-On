import base64
import os
import shutil
import sqlite3
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple
from uuid import uuid4

import httpx
from fastapi import HTTPException
from gradio_client import Client, handle_file
from huggingface_hub import HfApi

from app.config import settings
from app.models.schemas import PhotoType
from app.services.image_processor import image_processor



class CatVTONService:
    """
    Client and coordinator service for virtual try-on inference via Hugging Face Space (ZeroGPU).
    Manages image fetching, profile photo resolution, ZeroGPU Space interaction,
    and storage of composited results.
    """

    def __init__(self):
        self.space_id = settings.HF_SPACE_ID or "krishv10/AI_Try_On"
        self.hf_token = settings.HF_TOKEN
        self._cached_client: Optional[Client] = None
        self._photo_cache: Dict[Any, Tuple[int, Path, str]] = {}

    def invalidate_photo_cache(self, profile_id: Optional[int] = None):
        """Invalidate backend-cached profile photo paths."""
        if profile_id is None:
            self._photo_cache.clear()
        else:
            keys_to_del = [k for k in self._photo_cache if k[0] == profile_id]
            for k in keys_to_del:
                self._photo_cache.pop(k, None)

    def get_space_status(self) -> dict:
        """
        Check Hugging Face Space runtime state (BUILDING, APP_STARTING, RUNNING, SLEEPING, etc.).
        """
        try:
            api = HfApi(token=self.hf_token if self.hf_token else None)
            info = api.space_info(self.space_id)
            stage = info.runtime.stage if info.runtime else "UNKNOWN"
            is_ready = stage in ["RUNNING", "SLEEPING", "PAUSED"]
            return {
                "space_id": self.space_id,
                "stage": stage,
                "is_ready": is_ready,
                "space_url": f"https://{self.space_id.replace('/', '-')}.hf.space",
            }
        except Exception as e:
            return {
                "space_id": self.space_id,
                "stage": "ERROR",
                "is_ready": False,
                "error": str(e),
                "space_url": f"https://huggingface.co/spaces/{self.space_id}",
            }

    def _get_client(self) -> Client:
        """
        Get or initialize the Gradio Client connection.
        """
        if self._cached_client is None:
            try:
                self._cached_client = Client(
                    self.space_id,
                    token=self.hf_token if self.hf_token else None,
                    verbose=False,
                )
            except Exception as e:
                # Also try direct URL if space ID lookup encounters issues
                try:
                    self._cached_client = Client(
                        settings.HF_CATVTON_SPACE_URL,
                        token=self.hf_token if self.hf_token else None,
                        verbose=False,
                    )
                except Exception:
                    raise HTTPException(
                        status_code=503,
                        detail=f"Unable to connect to CatVTON Hugging Face Space ({self.space_id}): {e}",
                    )
        return self._cached_client

    def resolve_profile_photo(
        self,
        profile_id: int,
        conn: sqlite3.Connection,
        category: Optional[str] = None,
        requested_type: Optional[PhotoType] = None,
    ) -> Tuple[int, Path, str]:
        """
        Fetch the best matching photo file for this try-on request.
        Priority:
        1. Explicitly requested photo_type
        2. Category match (upper body for tops, legs for bottoms, full body for dresses/overall)
        3. front_full_body fallback
        4. Any available photo for this profile
        """
        # 0. Check in-memory path cache
        req_type_str = requested_type.value if hasattr(requested_type, "value") else str(requested_type) if requested_type else None
        cache_key = (profile_id, (category or "overall").lower(), req_type_str)
        if cache_key in self._photo_cache:
            pid, cached_path, ptype = self._photo_cache[cache_key]
            if cached_path.exists():
                return pid, cached_path, ptype
            else:
                self._photo_cache.pop(cache_key, None)

        cursor = conn.cursor()

        # Check if profile exists
        cursor.execute("SELECT id, name FROM profiles WHERE id = ?;", (profile_id,))
        profile = cursor.fetchone()
        if not profile:
            raise HTTPException(
                status_code=404, detail=f"Profile with ID {profile_id} not found."
            )

        # Fetch all photos for this profile
        cursor.execute(
            "SELECT id, photo_type, file_path FROM profile_photos WHERE profile_id = ? ORDER BY id ASC;",
            (profile_id,),
        )
        photos = cursor.fetchall()
        if not photos:
            raise HTTPException(
                status_code=400,
                detail=f"Profile '{profile['name']}' has no uploaded photos. Please upload a profile photo first.",
            )

        photos_by_type = {p["photo_type"]: p for p in photos}

        resolved_tuple = None

        # 1. Explicit requested type
        if req_type_str and req_type_str in photos_by_type:
            selected = photos_by_type[req_type_str]
            path = Path(selected["file_path"])
            if path.exists():
                resolved_tuple = (selected["id"], path, selected["photo_type"])

        # 2. Determine preferred types based on category
        if not resolved_tuple:
            cat_lower = (category or "overall").lower()
            if any(w in cat_lower for w in ["upper", "top", "shirt", "t-shirt", "tshirt", "hoodie", "jacket", "sweater", "blouse", "coat"]):
                candidates = ["upper_body", "front_full_body"]
            elif any(w in cat_lower for w in ["lower", "pant", "jeans", "skirt", "trouser", "short", "bottom", "legging"]):
                candidates = ["legs", "front_full_body"]
            elif any(w in cat_lower for w in ["foot", "feet", "shoe", "sneaker", "boot", "sandal", "heel"]):
                candidates = ["feet", "front_full_body"]
            else:
                candidates = ["front_full_body", "upper_body"]

            for cand in candidates:
                if cand in photos_by_type:
                    p = Path(photos_by_type[cand]["file_path"])
                    if p.exists():
                        resolved_tuple = (photos_by_type[cand]["id"], p, cand)
                        break

        # 3. Fallback to any valid photo file on disk
        if not resolved_tuple:
            for p_row in photos:
                p = Path(p_row["file_path"])
                if p.exists():
                    resolved_tuple = (p_row["id"], p, p_row["photo_type"])
                    break

        if not resolved_tuple:
            raise HTTPException(
                status_code=400,
                detail="Profile photos are registered in database but the image files are missing from storage.",
            )

        # Cache resolved photo reference
        self._photo_cache[cache_key] = resolved_tuple
        return resolved_tuple


    async def download_garment_image(self, garment_url: str, output_dir: Path) -> Path:
        """
        Download or decode the garment image into a local temporary file.
        Supports standard HTTP/HTTPS URLs and base64 data URLs.
        """
        target_path = output_dir / f"garment_{uuid4().hex[:8]}.png"

        if garment_url.startswith("data:image"):
            # Parse Data URI
            try:
                header, encoded = garment_url.split(",", 1)
                data = base64.b64decode(encoded)
                with open(target_path, "wb") as f:
                    f.write(data)
                # Phase 12: Resize / Compress garment image (cap dimensions at 1024px)
                try:
                    image_processor.optimize_image_file(target_path, target_path, max_dim=1024)
                except Exception:
                    pass
                return target_path
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid base64 garment image data: {e}",
                )

        if garment_url.startswith("http://") or garment_url.startswith("https://"):
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                }
                async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                    response = await client.get(garment_url, headers=headers)
                    response.raise_for_status()
                    with open(target_path, "wb") as f:
                        f.write(response.content)

                # Phase 12: Resize / Compress garment image (cap dimensions at 1024px)
                try:
                    image_processor.optimize_image_file(target_path, target_path, max_dim=1024)
                except Exception:
                    pass
                return target_path
            except httpx.TimeoutException:
                raise HTTPException(
                    status_code=504,
                    detail="Product Image Timeout: Download of product garment image timed out from retailer site. Please try again or use another product.",
                )
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to fetch garment image from URL: {e}",
                )

        # Check local file path
        local_path = Path(garment_url)
        if local_path.exists():
            shutil.copy(local_path, target_path)
            try:
                image_processor.optimize_image_file(target_path, target_path, max_dim=1024)
            except Exception:
                pass
            return target_path

        raise HTTPException(
            status_code=400,
            detail=f"Unsupported garment image URL format: {garment_url[:50]}...",
        )

    def execute_catvton_inference(
        self,
        person_photo_path: Path,
        garment_photo_path: Path,
        category: str = "overall",
    ) -> Path:
        """
        Execute try-on inference by calling the CatVTON Hugging Face Space endpoint.
        """
        client = self._get_client()

        # Map category to CatVTON cloth_type: "upper", "lower", "overall"
        cat_lower = (category or "overall").lower()
        if any(w in cat_lower for w in ["upper", "top", "shirt", "t-shirt", "tshirt", "hoodie", "jacket", "sweater", "blouse"]):
            cloth_type = "upper"
        elif any(w in cat_lower for w in ["lower", "pant", "jeans", "skirt", "trouser", "short", "bottom", "legging"]):
            cloth_type = "lower"
        else:
            cloth_type = "overall"

        try:
            # Call predict on /tryon endpoint exposed in app.py
            result = client.predict(
                person_image=handle_file(str(person_photo_path)),
                cloth_image=handle_file(str(garment_photo_path)),
                cloth_type=cloth_type,
                num_inference_steps=30,
                guidance_scale=2.5,
                seed=42,
                api_name="/tryon",
            )

            # Gradio returns either a string filepath or a dict containing filepath
            if isinstance(result, str) and os.path.exists(result):
                return Path(result)
            elif isinstance(result, dict) and "path" in result and os.path.exists(result["path"]):
                return Path(result["path"])
            elif isinstance(result, (tuple, list)) and len(result) > 0 and os.path.exists(result[0]):
                return Path(result[0])
            else:
                raise RuntimeError(f"Unexpected result format from CatVTON Space: {result}")

        except HTTPException:
            raise
        except Exception as e:
            err_msg = str(e)
            if "timeout" in err_msg.lower() or "timed out" in err_msg.lower():
                raise HTTPException(
                    status_code=504,
                    detail="Model Timeout: Virtual try-on inference exceeded time limit (30s). The ZeroGPU worker may be busy or waking up. Please click Re-try in a few moments.",
                )

            # Check space status to give detailed feedback
            status = self.get_space_status()
            stage = status.get("stage", "UNKNOWN")
            if stage in ["BUILDING", "APP_STARTING"]:
                raise HTTPException(
                    status_code=503,
                    detail=f"Model Warming Up: Hugging Face ZeroGPU Space is currently {stage}. Cold starts take 30–60 seconds. Please retry shortly.",
                )
            elif stage in ["SLEEPING", "PAUSED"]:
                raise HTTPException(
                    status_code=503,
                    detail="Model Sleeping: The ZeroGPU space is currently waking up from sleep mode. Please retry in 20 seconds.",
                )
            raise HTTPException(
                status_code=500,
                detail=f"CatVTON inference execution failed: {err_msg}",
            )



catvton_service = CatVTONService()
