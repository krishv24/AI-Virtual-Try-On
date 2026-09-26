import asyncio
import logging
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
from app.services.accuracy_validator import accuracy_validator
from app.services.catvton_service import catvton_service
from app.services.clip_classifier import clip_classifier
from app.services.tryon_router import tryon_router_registry
import json

router = APIRouter(prefix="/api/tryon", tags=["Virtual Try-On"])
logger = logging.getLogger(__name__)


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
    Phase 7 & 10 Category-Aware Virtual Try-On Router with Caching:
    1. Checks cache for existing try-on result tied to (profile_id, product_id/garment).
       If found and not force_refresh, returns cached result instantly without re-generation.
    2. Downloads/decodes the product garment image.
    3. Runs CLIP classification if category is unspecified, 'auto', or 'overall'.
    4. Selects specialized plugin handler (CatVTON ZeroGPU, Footwear, or MediaPipe Landmark Placement).
    5. Fetches the optimal reference profile photo slot (upper_body, legs, feet, face, or front_full_body).
    6. Executes the plugin pipeline and saves the composited result to private storage.
    7. Validates color/pattern fidelity (Phase 9 Safeguards) and records result in database.
    """
    # 1. Determine initial category hint from request
    effective_category = (request.category or "").strip().lower()
    if not effective_category or effective_category in ["auto", "unknown"]:
        effective_category = "overall"


    # 0. Check result cache tied to profile_id + product_id unless forced refresh
    if not request.force_refresh and request.product_id:
        cursor = conn.cursor()
        cached_row = None
        if effective_category not in ["auto", "overall", "unknown"]:
            cursor.execute(
                """
                SELECT t.id, t.profile_id, t.product_id, t.category, t.image_path,
                       t.accuracy_score, t.is_low_confidence, t.accuracy_metrics, t.created_at,
                       t.garment_image_url, p.title as product_title
                FROM tryon_results t
                LEFT JOIN products p ON t.product_id = p.id
                WHERE t.profile_id = ? AND t.product_id = ? AND t.category = ?
                ORDER BY t.id DESC LIMIT 1;
                """,
                (request.profile_id, request.product_id, effective_category),
            )
            cached_row = cursor.fetchone()
        if not cached_row:
            cursor.execute(
                """
                SELECT t.id, t.profile_id, t.product_id, t.category, t.image_path,
                       t.accuracy_score, t.is_low_confidence, t.accuracy_metrics, t.created_at,
                       t.garment_image_url, p.title as product_title
                FROM tryon_results t
                LEFT JOIN products p ON t.product_id = p.id
                WHERE t.profile_id = ? AND t.product_id = ?
                ORDER BY t.id DESC LIMIT 1;
                """,
                (request.profile_id, request.product_id),
            )
            cached_row = cursor.fetchone()

        if cached_row and Path(cached_row["image_path"]).exists():
            metrics_obj = None
            if "accuracy_metrics" in cached_row.keys() and cached_row["accuracy_metrics"]:
                try:
                    metrics_obj = json.loads(cached_row["accuracy_metrics"])
                except Exception:
                    metrics_obj = None
            handler_obj = tryon_router_registry.get_handler(cached_row["category"])
            return TryOnResultResponse(
                id=cached_row["id"],
                profile_id=cached_row["profile_id"],
                product_id=cached_row["product_id"],
                category=cached_row["category"],
                handler_name=handler_obj.name if handler_obj else "Cached Synthesis",
                accuracy_score=cached_row["accuracy_score"] if "accuracy_score" in cached_row.keys() else 1.0,
                is_low_confidence=bool(cached_row["is_low_confidence"]) if "is_low_confidence" in cached_row.keys() else False,
                accuracy_metrics=metrics_obj,
                cached=True,
                created_at=cached_row["created_at"],
                access_url=f"/api/tryon/results/{cached_row['id']}/file",
                product_title=cached_row["product_title"] if "product_title" in cached_row.keys() else None,
                garment_image_url=cached_row["garment_image_url"] if "garment_image_url" in cached_row.keys() else request.garment_image_url,
            )

    # Phase 12: Validate that category is supported
    if not tryon_router_registry.is_supported(effective_category):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported category '{effective_category}'. Virtual try-on currently supports: shirts, t-shirts, dresses, jackets, pants/trousers, shoes, necklaces, and jewelry.",
        )

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
        try:
            composited_temp_path = handler.execute(
                person_photo_path=profile_photo_path,
                garment_photo_path=garment_path,
                category=effective_category,
                profile_id=request.profile_id,
                conn=conn,
            )
        except HTTPException:
            raise
        except (TimeoutError, asyncio.TimeoutError) as e:
            logger.error(f"Try-on generation timeout: {e}")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Virtual Try-On AI model timed out after waiting for compute: {str(e)}. The model space may be waking up or queue is full. Please try again."
            )
        except Exception as e:
            err_msg = str(e)
            if "timeout" in err_msg.lower() or "timed out" in err_msg.lower():
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail=f"Virtual Try-On AI model timed out: {err_msg}"
                )
            logger.error(f"Try-on synthesis error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Try-on generation failed: {err_msg}"
            )

        # 6. Phase 9 Accuracy Safeguards: validate color and pattern fidelity
        accuracy_data = accuracy_validator.validate_accuracy(
            original_garment_input=garment_path,
            composited_result_input=composited_temp_path,
            category=effective_category,
        )
        accuracy_score = accuracy_data["accuracy_score"]
        is_low_conf = 1 if accuracy_data["is_low_confidence"] else 0
        metrics_json = json.dumps(accuracy_data)

        # 7. Save final composited result to private storage
        result_filename = f"tryon_{uuid4().hex}.png"
        final_storage_path = settings.STORAGE_DIR / result_filename
        shutil.copy(composited_temp_path, final_storage_path)

        # 8. Insert into SQLite tryon_results table with accuracy metrics and garment_image_url
        created_at = datetime.now(timezone.utc).isoformat()
        cursor = conn.cursor()

        product_title = None
        if request.product_id:
            cursor.execute("SELECT title FROM products WHERE id = ?;", (request.product_id,))
            p_row = cursor.fetchone()
            if p_row:
                product_title = p_row["title"]

        cursor.execute(
            """
            INSERT INTO tryon_results (
                profile_id, product_id, category, garment_image_url, image_path,
                accuracy_score, is_low_confidence, accuracy_metrics, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                request.profile_id,
                request.product_id,
                effective_category,
                request.garment_image_url,
                str(final_storage_path),
                accuracy_score,
                is_low_conf,
                metrics_json,
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
            accuracy_score=accuracy_score,
            is_low_confidence=bool(is_low_conf),
            accuracy_metrics=accuracy_data,
            cached=False,
            created_at=created_at,
            access_url=f"/api/tryon/results/{result_id}/file",
            product_title=product_title,
            garment_image_url=request.garment_image_url,
        )

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@router.get("/results/{result_id}", response_model=TryOnResultResponse)
def get_tryon_result(result_id: int, conn: sqlite3.Connection = Depends(get_db)):
    """
    Retrieve metadata for a specific try-on result including accuracy metrics and product info.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT t.id, t.profile_id, t.product_id, t.category, t.accuracy_score,
               t.is_low_confidence, t.accuracy_metrics, t.created_at,
               t.garment_image_url, p.title as product_title
        FROM tryon_results t
        LEFT JOIN products p ON t.product_id = p.id
        WHERE t.id = ?;
        """,
        (result_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Try-on result not found")

    handler = tryon_router_registry.get_handler(row["category"])

    metrics_obj = None
    if "accuracy_metrics" in row.keys() and row["accuracy_metrics"]:
        try:
            metrics_obj = json.loads(row["accuracy_metrics"])
        except Exception:
            metrics_obj = None

    return TryOnResultResponse(
        id=row["id"],
        profile_id=row["profile_id"],
        product_id=row["product_id"],
        category=row["category"],
        handler_name=handler.name if handler else "Specialized Synthesis",
        accuracy_score=row["accuracy_score"] if "accuracy_score" in row.keys() else 1.0,
        is_low_confidence=bool(row["is_low_confidence"]) if "is_low_confidence" in row.keys() else False,
        accuracy_metrics=metrics_obj,
        cached=False,
        created_at=row["created_at"],
        access_url=f"/api/tryon/results/{row['id']}/file",
        product_title=row["product_title"] if "product_title" in row.keys() else None,
        garment_image_url=row["garment_image_url"] if "garment_image_url" in row.keys() else None,
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
    List all historical try-on results for a given profile (Closet/Wardrobe history).
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT t.id, t.profile_id, t.product_id, t.category, t.accuracy_score,
               t.is_low_confidence, t.accuracy_metrics, t.created_at,
               t.garment_image_url, p.title as product_title
        FROM tryon_results t
        LEFT JOIN products p ON t.product_id = p.id
        WHERE t.profile_id = ?
        ORDER BY t.id DESC;
        """,
        (profile_id,),
    )
    rows = cursor.fetchall()
    results = []
    for row in rows:
        metrics_obj = None
        if "accuracy_metrics" in row.keys() and row["accuracy_metrics"]:
            try:
                metrics_obj = json.loads(row["accuracy_metrics"])
            except Exception:
                metrics_obj = None
        h_obj = tryon_router_registry.get_handler(row["category"])
        results.append(
            TryOnResultResponse(
                id=row["id"],
                profile_id=row["profile_id"],
                product_id=row["product_id"],
                category=row["category"],
                handler_name=h_obj.name if h_obj else "Specialized Synthesis",
                accuracy_score=row["accuracy_score"] if "accuracy_score" in row.keys() else 1.0,
                is_low_confidence=bool(row["is_low_confidence"]) if "is_low_confidence" in row.keys() else False,
                accuracy_metrics=metrics_obj,
                cached=False,
                created_at=row["created_at"],
                access_url=f"/api/tryon/results/{row['id']}/file",
                product_title=row["product_title"] if "product_title" in row.keys() else None,
                garment_image_url=row["garment_image_url"] if "garment_image_url" in row.keys() else None,
            )
        )
    return results


@router.delete("/results/{result_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tryon_result(result_id: int, conn: sqlite3.Connection = Depends(get_db)):
    """
    Remove a specific try-on fitting from the user's virtual wardrobe and purge disk storage.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT image_path FROM tryon_results WHERE id = ?;", (result_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Try-on result not found")

    file_path = Path(row["image_path"])
    try:
        if file_path.exists():
            file_path.unlink()
    except Exception as e:
        logger.warning(f"Could not delete result file {file_path}: {e}")

    cursor.execute("DELETE FROM tryon_results WHERE id = ?;", (result_id,))
    conn.commit()
    return None

