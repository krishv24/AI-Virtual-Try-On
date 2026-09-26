from pathlib import Path
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.database import get_db
from app.models.schemas import ProfilePhotoResponse, PhotoType

router = APIRouter(prefix="/api/photos", tags=["Photos"])

@router.get("/{photo_id}", response_model=ProfilePhotoResponse)
def get_photo_metadata(photo_id: int, conn: sqlite3.Connection = Depends(get_db)):
    """Retrieve metadata for a specific photo."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, profile_id, photo_type, file_path, created_at FROM profile_photos WHERE id = ?;",
        (photo_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Photo not found")

    return ProfilePhotoResponse(
        id=row["id"],
        profile_id=row["profile_id"],
        photo_type=PhotoType(row["photo_type"]),
        created_at=row["created_at"],
        access_url=f"/api/photos/{row['id']}/file",
    )


@router.get("/{photo_id}/file")
def get_photo_file(photo_id: int, conn: sqlite3.Connection = Depends(get_db)):
    """
    Securely stream the photo file from private disk.
    This guarantees that the disk storage directory is never exposed publicly as a static folder.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT file_path, photo_type FROM profile_photos WHERE id = ?;", (photo_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Photo not found")

    disk_path = Path(row["file_path"])
    if not disk_path.exists():
        raise HTTPException(status_code=404, detail="Image file missing from storage disk")

    # Determine media type by extension
    ext = disk_path.suffix.lower()
    media_type = "image/jpeg"
    if ext == ".png":
        media_type = "image/png"
    elif ext == ".webp":
        media_type = "image/webp"

    return FileResponse(
        path=str(disk_path),
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=86400"},
    )


@router.delete("/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_photo(photo_id: int, conn: sqlite3.Connection = Depends(get_db)):
    """Delete a photo record and remove the file from private disk."""
    cursor = conn.cursor()
    cursor.execute("SELECT file_path FROM profile_photos WHERE id = ?;", (photo_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Photo not found")

    file_path = Path(row["file_path"])
    if file_path.exists():
        try:
            file_path.unlink()
        except OSError:
            pass

    cursor.execute("DELETE FROM profile_photos WHERE id = ?;", (photo_id,))
    return None
