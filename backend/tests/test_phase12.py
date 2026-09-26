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
from app.services.image_processor import image_processor
from app.services.catvton_service import catvton_service


def create_image_bytes(w=2000, h=1500, color=(120, 180, 240)):
    img = Image.new("RGB", (w, h), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def test_phase12_suite():
    client = TestClient(app)

    print("\n=== Phase 12: Performance & Error Handling Tests ===")

    # 1. Test ImageProcessor Unit Resizing & Compression
    print("\n--- 1. Testing ImageProcessor Capping at 1024px ---")
    large_bytes = create_image_bytes(w=2400, h=1600)
    assert len(large_bytes) > 0
    with Image.open(io.BytesIO(large_bytes)) as img:
        assert img.size == (2400, 1600)

    # Optimize bytes capping at 1024px
    optimized_bytes = image_processor.optimize_image_bytes(large_bytes, max_dim=1024, output_format="JPEG")
    with Image.open(io.BytesIO(optimized_bytes)) as opt_img:
        w, h = opt_img.size
        print(f"PASS: Large image (2400x1600) resized to ({w}x{h}), max dimension: {max(w, h)}")
        assert max(w, h) == 1024
        assert w == 1024
        assert h == round(1600 * (1024 / 2400))
        assert len(optimized_bytes) < len(large_bytes)

    # Test disk file optimization
    temp_large_file = settings.STORAGE_DIR / "test_p12_oversized.png"
    Image.new("RGB", (1500, 2500), color=(50, 150, 50)).save(temp_large_file)
    try:
        out_file = image_processor.optimize_image_file(temp_large_file, temp_large_file, max_dim=1024)
        with Image.open(out_file) as disk_img:
            dw, dh = disk_img.size
            print(f"PASS: Disk file (1500x2500) capped at ({dw}x{dh}), max dimension: {max(dw, dh)}")
            assert max(dw, dh) == 1024
            assert dh == 1024
    finally:
        if temp_large_file.exists():
            temp_large_file.unlink()

    # 2. Test Profile Photo Upload Automatic Capping
    print("\n--- 2. Testing Profile Photo Upload Resizing ---")
    p_res = client.post("/api/profiles", json={"name": "Perf Test Profile"})
    assert p_res.status_code == 201
    profile_id = p_res.json()["id"]

    oversized_photo = create_image_bytes(w=2048, h=1536)
    with patch("app.routers.profiles.validate_photo_landmarks", return_value=(True, "Keypoints valid", {})):
        up_res = client.post(
            f"/api/profiles/{profile_id}/photos",
            data={"photo_type": "upper_body"},
            files={"file": ("large_person.jpg", oversized_photo, "image/jpeg")},
        )
    assert up_res.status_code == 201
    photo_id = up_res.json()["id"]

    # Verify saved file on disk does not exceed 1024px
    from app.database import get_connection
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT file_path FROM profile_photos WHERE id = ?", (photo_id,))
    saved_path = Path(c.fetchone()["file_path"])
    conn.close()

    assert saved_path.exists()
    with Image.open(saved_path) as saved_img:
        sw, sh = saved_img.size
        print(f"PASS: Uploaded profile photo saved on disk as ({sw}x{sh}) <= 1024px")
        assert max(sw, sh) == 1024

    # 3. Test Garment Image Download Automatic Capping
    print("\n--- 3. Testing Garment Image Capping ---")
    oversized_garment_bytes = create_image_bytes(w=1800, h=1800, color=(220, 30, 30))
    garment_b64 = "data:image/png;base64," + base64.b64encode(oversized_garment_bytes).decode("utf-8")

    import tempfile
    temp_dir = Path(tempfile.mkdtemp(prefix="test_garment_"))
    try:
        import asyncio
        downloaded_garment_path = asyncio.run(
            catvton_service.download_garment_image(garment_b64, temp_dir)
        )
        with Image.open(downloaded_garment_path) as g_img:
            gw, gh = g_img.size
            print(f"PASS: Downloaded garment image normalized to ({gw}x{gh}) <= 1024px")
            assert max(gw, gh) == 1024
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

    # 4. Test Unsupported Category Failure Surfacing
    print("\n--- 4. Testing Unsupported Category Handling ---")
    bad_cat_res = client.post(
        "/api/tryon",
        json={
            "profile_id": profile_id,
            "garment_image_url": garment_b64,
            "category": "refrigerator_electronics",
        },
    )
    assert bad_cat_res.status_code == 422
    err_detail = bad_cat_res.json()["detail"]
    assert "Unsupported category 'refrigerator_electronics'" in err_detail
    assert "shirts" in err_detail or "shoes" in err_detail
    print(f"PASS: Unsupported category rejected with distinct message: '{err_detail}'")

    # 5. Test Model Timeout Handling
    print("\n--- 5. Testing Model Timeout Failure Surfacing ---")
    with patch(
        "app.services.tryon_router.clothing_handler.ClothingCatVTONHandler.execute",
        side_effect=TimeoutError("Connection to Gradio ZeroGPU space timed out after 30 seconds"),
    ):
        timeout_res = client.post(
            "/api/tryon",
            json={
                "profile_id": profile_id,
                "garment_image_url": garment_b64,
                "category": "shirt",
                "force_refresh": True,
            },
        )
        # Handler wraps TimeoutError in CatVTON execution or exception handler
        assert timeout_res.status_code in [500, 504]
        timeout_detail = timeout_res.json()["detail"]
        print(f"PASS: Model timeout handled and surfaced with user guidance: '{timeout_detail}'")

    # Clean up profile
    client.delete(f"/api/profiles/{profile_id}")

    print("\nALL PHASE 12 PERFORMANCE & ERROR HANDLING TESTS PASSED! [SUCCESS]")


if __name__ == "__main__":
    test_phase12_suite()
