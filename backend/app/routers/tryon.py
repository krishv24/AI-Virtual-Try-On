import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.config import settings
from app.database import get_db
from app.models.schemas import (
    TryOnRequest,
    TryOnResultResponse,
    TryOnStatusResponse,
)
from app.services.catvton_service import catvton_service

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


@router.post("", response_model=TryOnResultResponse, status_code=status.HTTP_201_CREATED)
async def create_tryon(
    request: TryOnRequest,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Core virtual try-on endpoint:
    1. Fetches the appropriate profile photo for the given profile_id & garment category.
    2. Downloads / decodes the product garment image.
    3. Calls the CatVTON Hugging Face Space endpoint on ZeroGPU.
    4. Saves the resulting composited image securely to private disk storage.
    5. Records the result in the tryon_results database table and returns access URL.
    """
    # 1. Resolve profile photo
    photo_id, profile_photo_path, matched_photo_type = catvton_service.resolve_profile_photo(
        profile_id=request.profile_id,
        conn=conn,
        category=request.category,
        requested_type=request.photo_type,
    )

    # 2. Download/decode garment image in a temporary directory
    temp_dir = Path(tempfile.mkdtemp(prefix="tryon_temp_"))
    try:
        garment_path = await catvton_service.download_garment_image(
            request.garment_image_url, temp_dir
        )

        # 3. Call CatVTON model on Hugging Face Space
        composited_temp_path = catvton_service.execute_catvton_inference(
            person_photo_path=profile_photo_path,
            garment_photo_path=garment_path,
            category=request.category or "overall",
        )

        # 4. Save to private storage
        result_filename = f"tryon_{uuid4().hex}.png"
        final_storage_path = settings.STORAGE_DIR / result_filename
        shutil.copy(composited_temp_path, final_storage_path)

        # 5. Insert into tryon_results SQLite table
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
                request.category or "overall",
                str(final_storage_path),
                created_at,
            ),
        )
        result_id = cursor.lastrowid

        return TryOnResultResponse(
            id=result_id,
            profile_id=request.profile_id,
            product_id=request.product_id,
            category=request.category or "overall",
            created_at=created_at,
            access_url=f"/api/tryon/results/{result_id}/file",
        )

    finally:
        # Clean up temporary garment image and workspace
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

    return TryOnResultResponse(
        id=row["id"],
        profile_id=row["profile_id"],
        product_id=row["product_id"],
        category=row["category"],
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
            created_at=row["created_at"],
            access_url=f"/api/tryon/results/{row['id']}/file",
        )
        for row in rows
    ]
