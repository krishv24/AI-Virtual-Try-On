import base64
import io
import sys
from pathlib import Path
from unittest.mock import patch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.config import settings



def create_test_image_bytes(w=200, h=200, color=(100, 150, 200)):
    img = Image.new("RGB", (w, h), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_phase10_11_suite():
    client = TestClient(app)

    print("\n=== Phase 11: Privacy & Security Hardening Tests ===")

    # 1. Profile Creation with Explicit Consent Flag
    profile_payload = {
        "name": "Privacy Conscious User",
        "consent_no_training": True,
    }
    res = client.post("/api/profiles", json=profile_payload)
    assert res.status_code == 201, f"Failed to create profile: {res.text}"
    profile_data = res.json()
    profile_id = profile_data["id"]
    assert profile_data["name"] == "Privacy Conscious User"
    assert profile_data["consent_no_training"] is True
    print(f"PASS: Profile created with consent_no_training=True (ID: {profile_id})")

    # Verify GET /api/profiles/{id} returns consent flag
    get_res = client.get(f"/api/profiles/{profile_id}")
    assert get_res.status_code == 200
    assert get_res.json()["consent_no_training"] is True
    print("PASS: Profile retrieval returns consent confirmation flag")

    # 2. Upload Reference Profile Photo
    photo_bytes = create_test_image_bytes(color=(120, 80, 50))
    with patch("app.routers.profiles.validate_photo_landmarks", return_value=(True, "Keypoints valid", {})):
        upload_res = client.post(
            f"/api/profiles/{profile_id}/photos",
            data={"photo_type": "upper_body"},
            files={"file": ("profile.png", photo_bytes, "image/png")},
        )
    assert upload_res.status_code == 201
    photo_info = upload_res.json()
    photo_id = photo_info["id"]
    print(f"PASS: Reference photo uploaded (ID: {photo_id})")

    # Verify photo file is in private storage (non-public) and streams via authenticated route
    photo_file_res = client.get(f"/api/photos/{photo_id}/file")
    assert photo_file_res.status_code == 200
    assert photo_file_res.headers["content-type"] in ["image/png", "image/jpeg"]
    print("PASS: Private photo streams securely via backend route")

    # 3. Create a Test Product
    prod_res = client.post(
        "/api/products",
        json={
            "source_url": "https://example.com/item/privacy-jacket",
            "title": "Minimalist Utility Jacket",
            "category": "jacket",
            "image_urls": ["https://example.com/img/jacket.png"],
        },
    )
    assert prod_res.status_code == 201
    product_id = prod_res.json()["id"]

    print("\n=== Phase 10: Results, Caching, and Wardrobe Tests ===")

    # 4. First Try-On Request (Cache Miss -> Generates Result)
    garment_bytes = create_test_image_bytes(color=(200, 40, 40))
    garment_b64 = "data:image/png;base64," + base64.b64encode(garment_bytes).decode("utf-8")

    mock_temp = settings.STORAGE_DIR / "temp_mock_out.png"
    Image.new("RGB", (300, 400), color=(180, 50, 50)).save(mock_temp)

    with patch("app.services.tryon_router.clothing_handler.ClothingCatVTONHandler.execute", return_value=mock_temp):
        tryon_payload = {
            "profile_id": profile_id,
            "product_id": product_id,
            "garment_image_url": garment_b64,
            "category": "jacket",
            "force_refresh": False,
        }

        t1_res = client.post("/api/tryon", json=tryon_payload)
        assert t1_res.status_code == 201, f"Try-on failed: {t1_res.text}"
        t1_data = t1_res.json()
        assert t1_data["cached"] is False, "First execution should be a cache miss"
        result_id_1 = t1_data["id"]
        print(f"PASS: First try-on execution generated fresh result (ID: {result_id_1}, cached=False)")

    # 5. Second Try-On Request with SAME profile_id + product_id (Cache HIT -> Instant Return)
    t2_res = client.post("/api/tryon", json=tryon_payload)
    assert t2_res.status_code == 201
    t2_data = t2_res.json()
    assert t2_data["cached"] is True, "Second execution must be a CACHE HIT"
    assert t2_data["id"] == result_id_1, "Cached response must return identical result ID"
    print(f"PASS: Re-trying same product returned cached result instantly (ID: {t2_data['id']}, cached=True)")

    # 6. Third Try-On with force_refresh = True (Bypasses Cache)
    with patch("app.services.tryon_router.clothing_handler.ClothingCatVTONHandler.execute", return_value=mock_temp):
        refresh_payload = dict(tryon_payload)
        refresh_payload["force_refresh"] = True
        t3_res = client.post("/api/tryon", json=refresh_payload)
        assert t3_res.status_code == 201
        t3_data = t3_res.json()
        assert t3_data["cached"] is False, "force_refresh=True must bypass cache"
        result_id_2 = t3_data["id"]
        assert result_id_2 != result_id_1, "Forced regeneration must yield a new result record"
        print(f"PASS: force_refresh=True successfully bypassed cache (New ID: {result_id_2}, cached=False)")


    # 7. Closet / Wardrobe History View
    closet_res = client.get(f"/api/tryon/profile/{profile_id}")
    assert closet_res.status_code == 200
    closet_items = closet_res.json()
    assert len(closet_items) >= 2, f"Expected at least 2 closet items, got {len(closet_items)}"
    assert closet_items[0]["product_title"] == "Minimalist Utility Jacket"
    assert "access_url" in closet_items[0]
    print(f"PASS: Closet/Wardrobe history returned {len(closet_items)} fittings with product metadata")

    # 8. Physical File Purge on DELETE /api/profiles/{id}
    print("\n=== Phase 11: Physical File Purge & Right-to-be-Forgotten Tests ===")

    # Get disk paths before deletion
    from app.database import get_connection
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT file_path FROM profile_photos WHERE profile_id = ?", (profile_id,))
    stored_photos = [Path(row["file_path"]) for row in c.fetchall()]
    c.execute("SELECT image_path FROM tryon_results WHERE profile_id = ?", (profile_id,))
    stored_results = [Path(row["image_path"]) for row in c.fetchall()]
    conn.close()

    assert len(stored_photos) > 0, "Should have stored photo files on disk"
    assert len(stored_results) > 0, "Should have stored tryon result files on disk"
    for p in stored_photos:
        assert p.exists(), f"Photo file {p} should exist before deletion"
    for r in stored_results:
        assert r.exists(), f"Try-on file {r} should exist before deletion"

    # Execute DELETE /api/profiles/{id}
    del_res = client.delete(f"/api/profiles/{profile_id}")
    assert del_res.status_code == 204
    print(f"PASS: DELETE /api/profiles/{profile_id} returned HTTP 204")

    # Verify database records are deleted
    assert client.get(f"/api/profiles/{profile_id}").status_code == 404
    assert client.get(f"/api/photos/{photo_id}/file").status_code == 404
    assert client.get(f"/api/tryon/results/{result_id_1}/file").status_code == 404
    print("PASS: Database records and streaming routes return 404")

    # Verify physical files are unlinked from disk
    for p in stored_photos:
        assert not p.exists(), f"Photo file {p} was NOT purged from disk!"
    for r in stored_results:
        assert not r.exists(), f"Tryon result file {r} was NOT purged from disk!"
    print("PASS: All physical photo and result files permanently erased from disk!")

    # Clean up mock temp file if exists
    if mock_temp.exists():
        mock_temp.unlink()

    print("\nALL PHASE 10 & 11 TESTS PASSED SUCCESSFULLY! [SUCCESS]")


if __name__ == "__main__":
    test_phase10_11_suite()
