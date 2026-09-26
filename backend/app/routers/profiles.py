import os
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import List
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status

from app.database import get_db
from app.config import settings
from app.models.schemas import (
    ProfileCreate,
    ProfileUpdate,
    ProfileResponse,
    ProfileDetailResponse,
    ProfilePhotoResponse,
    PhotoType,
)

router = APIRouter(prefix="/api/profiles", tags=["Profiles"])

ALLOWED_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

def format_photo_response(row: sqlite3.Row) -> ProfilePhotoResponse:
    return ProfilePhotoResponse(
        id=row["id"],
        profile_id=row["profile_id"],
        photo_type=PhotoType(row["photo_type"]),
        created_at=row["created_at"],
        access_url=f"/api/photos/{row['id']}/file",
    )

# --- Profile Endpoints ---

@router.post("", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
def create_profile(payload: ProfileCreate, conn: sqlite3.Connection = Depends(get_db)):
    """Create a new user reference profile."""
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO profiles (name, created_at) VALUES (?, ?);",
        (payload.name.strip(), now),
    )
    profile_id = cursor.lastrowid
    return ProfileResponse(id=profile_id, name=payload.name.strip(), created_at=now, photo_count=0)


@router.get("", response_model=List[ProfileResponse])
def list_profiles(conn: sqlite3.Connection = Depends(get_db)):
    """List all profiles with their photo counts."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.name, p.created_at, COUNT(ph.id) AS photo_count
        FROM profiles p
        LEFT JOIN profile_photos ph ON p.id = ph.profile_id
        GROUP BY p.id
        ORDER BY p.id DESC;
    """)
    rows = cursor.fetchall()
    return [
        ProfileResponse(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
            photo_count=row["photo_count"],
        )
        for row in rows
    ]


@router.get("/{profile_id}", response_model=ProfileDetailResponse)
def get_profile(profile_id: int, conn: sqlite3.Connection = Depends(get_db)):
    """Get a specific profile along with its uploaded reference photos."""
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, created_at FROM profiles WHERE id = ?;", (profile_id,))
    profile_row = cursor.fetchone()
    if not profile_row:
        raise HTTPException(status_code=404, detail="Profile not found")

    cursor.execute(
        "SELECT id, profile_id, photo_type, file_path, created_at FROM profile_photos WHERE profile_id = ? ORDER BY id ASC;",
        (profile_id,),
    )
    photo_rows = cursor.fetchall()

    return ProfileDetailResponse(
        id=profile_row["id"],
        name=profile_row["name"],
        created_at=profile_row["created_at"],
        photos=[format_photo_response(p) for p in photo_rows],
    )


@router.put("/{profile_id}", response_model=ProfileResponse)
def update_profile(profile_id: int, payload: ProfileUpdate, conn: sqlite3.Connection = Depends(get_db)):
    """Update profile name."""
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, created_at FROM profiles WHERE id = ?;", (profile_id,))
    profile_row = cursor.fetchone()
    if not profile_row:
        raise HTTPException(status_code=404, detail="Profile not found")

    cursor.execute(
        "UPDATE profiles SET name = ? WHERE id = ?;",
        (payload.name.strip(), profile_id),
    )

    cursor.execute("SELECT COUNT(*) FROM profile_photos WHERE profile_id = ?;", (profile_id,))
    photo_count = cursor.fetchone()[0]

    return ProfileResponse(
        id=profile_id,
        name=payload.name.strip(),
        created_at=profile_row["created_at"],
        photo_count=photo_count,
    )


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(profile_id: int, conn: sqlite3.Connection = Depends(get_db)):
    """Delete a profile and purge all its stored photo files from the non-public disk."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM profiles WHERE id = ?;", (profile_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Profile not found")

    # Fetch all photo files for this profile to delete from disk
    cursor.execute("SELECT file_path FROM profile_photos WHERE profile_id = ?;", (profile_id,))
    photos = cursor.fetchall()
    for p in photos:
        file_path = Path(p["file_path"])
        if file_path.exists():
            try:
                file_path.unlink()
            except OSError:
                pass

    # Cascading delete removes profile_photos & tryon_results records
    cursor.execute("DELETE FROM profiles WHERE id = ?;", (profile_id,))
    return None


# --- Profile Photos Endpoints ---

@router.post("/{profile_id}/photos", response_model=ProfilePhotoResponse, status_code=status.HTTP_201_CREATED)
async def upload_profile_photo(
    profile_id: int,
    photo_type: PhotoType = Form(...),
    file: UploadFile = File(...),
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Upload a user reference body/face photo.
    Saves image to a secure local disk path that is NEVER publicly exposed.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM profiles WHERE id = ?;", (profile_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Profile not found")

    # Validate MIME type
    content_type = file.content_type or ""
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{content_type}'. Allowed types: JPG, PNG, WEBP.",
        )

    ext = ALLOWED_MIME_TYPES[content_type]
    # Unique safe disk filename: profile_{profile_id}_{photo_type}_{uuid}{ext}
    safe_filename = f"p{profile_id}_{photo_type.value}_{uuid.uuid4().hex[:12]}{ext}"
    destination_path = settings.STORAGE_DIR / safe_filename

    # Write file to non-public local disk
    try:
        contents = await file.read()
        if len(contents) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        with open(destination_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Failed to save image: {str(e)}")

    now = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        """
        INSERT INTO profile_photos (profile_id, photo_type, file_path, created_at)
        VALUES (?, ?, ?, ?);
        """,
        (profile_id, photo_type.value, str(destination_path), now),
    )
    photo_id = cursor.lastrowid

    return ProfilePhotoResponse(
        id=photo_id,
        profile_id=profile_id,
        photo_type=photo_type,
        created_at=now,
        access_url=f"/api/photos/{photo_id}/file",
    )


@router.get("/{profile_id}/photos", response_model=List[ProfilePhotoResponse])
def list_profile_photos(profile_id: int, conn: sqlite3.Connection = Depends(get_db)):
    """List all photos for a profile."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM profiles WHERE id = ?;", (profile_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Profile not found")

    cursor.execute(
        "SELECT id, profile_id, photo_type, file_path, created_at FROM profile_photos WHERE profile_id = ? ORDER BY id ASC;",
        (profile_id,),
    )
    rows = cursor.fetchall()
    return [format_photo_response(r) for r in rows]
