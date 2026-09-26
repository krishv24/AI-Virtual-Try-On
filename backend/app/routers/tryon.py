import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.config import settings
from app.database import get_db
from app.models.schemas import (
    ClassifyRequest,
    ClassifyResponse,
    TryOnRequest,
    TryOnResultResponse,
    TryOnStatusResponse,
)
from app.services.catvton_service import catvton_service
from app.services.clip_classifier import clip_classifier
from app.services.tryon_router import tryon_router_registry

router = APIRouter(prefix="/api/tryon", tags=["Virtual Try-On"])


@router.get("/status", response_model=TryOnStatusResponse)
def get_tryon_status():
    """
    Check the current health and runtime status of the Hugging Face ZeroGPU Space.
    """
    status_info = catvton_service.get_space_status()
    return TryOnStatusResponse(
        space_id=status_info.get("space_id", settings.HF_SPACE_ID),
        stage=status_info.get("stage", "UNKNOWN"),
        is_ready=status_info.get("is_ready", False),
        space_url=status_info.get("space_url", settings.HF_CATVTON_SPACE_URL),
    )


@router.get("/handlers")
def list_tryon_handlers():
    """
    List all active plugin try-on handlers and their supported categories.
    """
    return {
        "handlers": tryon_router_registry.list_handlers(),
    }


@router.post("/classify", response_model=ClassifyResponse)
async def classify_product_image(request: ClassifyRequest):
    """
    Zero-shot CLIP classification endpoint:
    Classifies a product image into one of the 9 target categories:
    t-shirt/top, shirt, dress, jacket, pants/trousers, shoes, jewellery, necklace, accessory.
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="classify_temp_"))
    try:
        garment_path = await catvton_service.download_garment_image(
            request.image_url, temp_dir
        )
        result = clip_classifier.classify_image(
            image_input=garment_path,
            text_hint=request.text_hint,
        )
        return ClassifyResponse(
            category=result["category"],
            confidence=result["confidence"],
            all_scores=result["all_scores"],
            method=result["method"],
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@router.post("", response_model=TryOnResultResponse, status_code=status.HTTP_201_CREATED)
async def create_tryon(
    request: TryOnRequest,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Phase 7 Category-Aware Virtual Try-On Router:
    1. Downloads/decodes the product garment image.
    2. Runs CLIP classification if category is unspecified, 'auto', or 'overall'.
    3. Selects specialized plugin handler (CatVTON ZeroGPU, Footwear, or MediaPipe Landmark Placement).
    4. Fetches the optimal reference profile photo slot (upper_body, legs, feet, face, or front_full_body).
    5. Executes the plugin pipeline and saves the composited result to private storage.
    """
    # 1. Determine initial category hint from request
    effective_category = (request.category or "").strip().lower()
    if not effective_category or effective_category in ["auto", "unknown"]:
        effective_category = "overall"

    # 2. Resolve profile photo upfront (validates profile exists and has uploaded photos)
    handler = tryon_router_registry.get_handler(effective_category)
    requested_type = request.photo_type or handler.get_preferred_photo_type(effective_category)
    photo_id, profile_photo_path, matched_photo_type = catvton_service.resolve_profile_photo(
        profile_id=request.profile_id,
        conn=conn,
        category=effective_category,
        requested_type=requested_type,
    )

    temp_dir = Path(tempfile.mkdtemp(prefix="tryon_temp_"))
    try:
        # 3. Download/decode garment image
        garment_path = await catvton_service.download_garment_image(
            request.garment_image_url, temp_dir
        )

        # 4. Refine category using CLIP classification if auto/overall
        if (not request.category) or request.category.strip().lower() in ["auto", "overall", "unknown"]:
            clip_res = clip_classifier.classify_image(garment_path)
            if clip_res and clip_res.get("confidence", 0) > 0.35:
                effective_category = clip_res["category"]
                handler = tryon_router_registry.get_handler(effective_category)
                # Re-resolve photo if newly classified category has a different preferred slot
                pref_slot = handler.get_preferred_photo_type(effective_category)
                if pref_slot != matched_photo_type:
                    try:
                        _, profile_photo_path, matched_photo_type = catvton_service.resolve_profile_photo(
                            profile_id=request.profile_id,
                            conn=conn,
                            category=effective_category,
                            requested_type=pref_slot,
                        )
                    except Exception:
                        pass

        # 5. Execute handler synthesis pipeline
        composited_temp_path = handler.execute(
            person_photo_path=profile_photo_path,
            garment_photo_path=garment_path,
            category=effective_category,
            profile_id=request.profile_id,
            conn=conn,
        )

        # 6. Save final composited result to private storage
        result_filename = f"tryon_{uuid4().hex}.png"
        final_storage_path = settings.STORAGE_DIR / result_filename
        shutil.copy(composited_temp_path, final_storage_path)

        # 7. Insert into SQLite tryon_results table
        created_at = datetime.now(timezone.utc).isoformat()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO tryon_results (profile_id, product_id, category, image_path, created_at)
            VALUES (?, ?, ?, ?, ?);
            """,
            (
                request.profile_id,
                request.product_id,
                effective_category,
                str(final_storage_path),
                created_at,
            ),
        )
        result_id = cursor.lastrowid

        return TryOnResultResponse(
            id=result_id,
            profile_id=request.profile_id,
            product_id=request.product_id,
            category=effective_category,
            handler_name=handler.name,
            created_at=created_at,
            access_url=f"/api/tryon/results/{result_id}/file",
        )

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@router.get("/results/{result_id}", response_model=TryOnResultResponse)
def get_tryon_result(result_id: int, conn: sqlite3.Connection = Depends(get_db)):
    """
    Retrieve metadata for a specific try-on result.
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, profile_id, product_id, category, created_at FROM tryon_results WHERE id = ?;",
        (result_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Try-on result not found")

    # Match handler name for introspection
    handler = tryon_router_registry.get_handler(row["category"])

    return TryOnResultResponse(
        id=row["id"],
        profile_id=row["profile_id"],
        product_id=row["product_id"],
        category=row["category"],
        handler_name=handler.name,
        created_at=row["created_at"],
        access_url=f"/api/tryon/results/{row['id']}/file",
    )


@router.get("/results/{result_id}/file")
def get_tryon_result_file(result_id: int, conn: sqlite3.Connection = Depends(get_db)):
    """
    Securely stream the composited try-on result image from private disk.
    Guarantees private storage is never exposed as a public static folder.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT image_path FROM tryon_results WHERE id = ?;", (result_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Try-on result not found")

    disk_path = Path(row["image_path"])
    if not disk_path.exists():
        raise HTTPException(
            status_code=404, detail="Result image file missing from storage disk"
        )

    return FileResponse(
        path=str(disk_path),
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=86400"},
    )


@router.get("/profile/{profile_id}", response_model=List[TryOnResultResponse])
def get_profile_tryon_history(profile_id: int, conn: sqlite3.Connection = Depends(get_db)):
    """
    List all historical try-on results for a given profile.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, profile_id, product_id, category, created_at
        FROM tryon_results
        WHERE profile_id = ?
        ORDER BY id DESC;
        """,
        (profile_id,),
    )
    rows = cursor.fetchall()
    return [
        TryOnResultResponse(
            id=row["id"],
            profile_id=row["profile_id"],
            product_id=row["product_id"],
            category=row["category"],
            handler_name=tryon_router_registry.get_handler(row["category"]).name,
            created_at=row["created_at"],
            access_url=f"/api/tryon/results/{row['id']}/file",
        )
        for row in rows
    ]
