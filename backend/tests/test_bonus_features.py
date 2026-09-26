import io
import sys
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.config import settings


def create_dummy_png():
    img = Image.new("RGB", (100, 100), color=(100, 140, 220))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_bonus_features_suite():
    client = TestClient(app)

    print("\n=== Bonus Features Automated Test Suite ===")

    # -------------------------------------------------------------
    # 1. Bonus Feature 2: Multiple User Profiles & Data Isolation
    # -------------------------------------------------------------
    print("\n--- 1. Testing Multiple User Profiles & Data Isolation ---")
    # Create Profile A (Alex)
    res_a = client.post("/api/profiles", json={"name": "Alex Profile"})
    assert res_a.status_code == 201
    profile_a_id = res_a.json()["id"]

    # Create Profile B (Jordan)
    res_b = client.post("/api/profiles", json={"name": "Jordan Profile"})
    assert res_b.status_code == 201
    profile_b_id = res_b.json()["id"]

    # Verify both exist in list
    profiles_res = client.get("/api/profiles")
    assert profiles_res.status_code == 200
    p_ids = [p["id"] for p in profiles_res.json()]
    assert profile_a_id in p_ids and profile_b_id in p_ids
    print(f"PASS: Created separate profiles: Alex (ID: {profile_a_id}) and Jordan (ID: {profile_b_id})")

    # Upload reference photo for Alex
    dummy_bytes = create_dummy_png()
    with patch_mp():
        photo_a_res = client.post(
            f"/api/profiles/{profile_a_id}/photos",
            data={"photo_type": "front_full_body"},
            files={"file": ("alex.png", dummy_bytes, "image/png")},
        )
    assert photo_a_res.status_code == 201
    photo_a_id = photo_a_res.json()["id"]

    # Verify Jordan has 0 photos while Alex has 1 photo
    detail_a = client.get(f"/api/profiles/{profile_a_id}").json()
    detail_b = client.get(f"/api/profiles/{profile_b_id}").json()
    assert len(detail_a["photos"]) == 1
    assert len(detail_b["photos"]) == 0
    print("PASS: Verified photo storage isolation between Profile A and Profile B")

    # -------------------------------------------------------------
    # 2. Bonus Feature 1: Virtual Wardrobe & Category Browsing
    # -------------------------------------------------------------
    print("\n--- 2. Testing Virtual Wardrobe & Category History ---")

    # Insert two test fittings for Alex (one Tops, one Bottoms)
    from app.database import get_connection
    conn = get_connection()
    c = conn.cursor()

    dummy_result_a_path = settings.STORAGE_DIR / f"test_wardrobe_top_{profile_a_id}.png"
    Image.new("RGB", (200, 300), color=(80, 160, 240)).save(dummy_result_a_path)

    dummy_result_b_path = settings.STORAGE_DIR / f"test_wardrobe_bottom_{profile_a_id}.png"
    Image.new("RGB", (200, 300), color=(40, 80, 120)).save(dummy_result_b_path)

    c.execute(
        """
        INSERT INTO tryon_results (profile_id, category, image_path, accuracy_score, is_low_confidence, created_at)
        VALUES (?, ?, ?, ?, ?, ?);
        """,
        (profile_a_id, "shirt", str(dummy_result_a_path), 0.96, 0, "2026-09-26T12:00:00Z"),
    )
    result_top_id = c.lastrowid

    c.execute(
        """
        INSERT INTO tryon_results (profile_id, category, image_path, accuracy_score, is_low_confidence, created_at)
        VALUES (?, ?, ?, ?, ?, ?);
        """,
        (profile_a_id, "pants/trousers", str(dummy_result_b_path), 0.92, 0, "2026-09-26T12:05:00Z"),
    )
    result_bottom_id = c.lastrowid
    conn.commit()
    conn.close()

    # Query virtual wardrobe for Alex
    history_res = client.get(f"/api/tryon/profile/{profile_a_id}")
    assert history_res.status_code == 200
    alex_closet = history_res.json()
    assert len(alex_closet) == 2
    categories = [item["category"] for item in alex_closet]
    assert "shirt" in categories and "pants/trousers" in categories
    print(f"PASS: Retrieved Alex's wardrobe with {len(alex_closet)} fittings spanning categories: {categories}")

    # Query virtual wardrobe for Jordan (should be empty, verifying isolation)
    history_jordan = client.get(f"/api/tryon/profile/{profile_b_id}").json()
    assert len(history_jordan) == 0
    print("PASS: Verified complete wardrobe isolation (Jordan has 0 fittings)")

    # -------------------------------------------------------------
    # 3. Test Wardrobe Item Deletion (Physical & DB Purge)
    # -------------------------------------------------------------
    print("\n--- 3. Testing Wardrobe Item Deletion ---")
    del_res = client.delete(f"/api/tryon/results/{result_top_id}")
    assert del_res.status_code == 204
    assert not dummy_result_a_path.exists()

    # Verify item is removed from wardrobe list
    updated_closet = client.get(f"/api/tryon/profile/{profile_a_id}").json()
    assert len(updated_closet) == 1
    assert updated_closet[0]["id"] == result_bottom_id
    print("PASS: DELETE /api/tryon/results/{id} successfully removed item and purged physical file")

    # -------------------------------------------------------------
    # Clean up test profiles
    # -------------------------------------------------------------
    client.delete(f"/api/profiles/{profile_a_id}")
    client.delete(f"/api/profiles/{profile_b_id}")
    if dummy_result_b_path.exists():
        dummy_result_b_path.unlink()

    print("\nALL BONUS CHALLENGES AUTOMATED TESTS PASSED! [SUCCESS]")


def patch_mp():
    from unittest.mock import patch
    return patch("app.routers.profiles.validate_photo_landmarks", return_value=(True, "Keypoints detected", {}))


if __name__ == "__main__":
    test_bonus_features_suite()
