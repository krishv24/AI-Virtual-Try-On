import io
import sys
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.services.catvton_service import catvton_service


def test_phase6():
    client = TestClient(app)

    # 1. Test Try-On Status Endpoint
    res = client.get("/api/tryon/status")
    assert res.status_code == 200, res.text
    status_data = res.json()
    assert "space_id" in status_data
    assert "stage" in status_data
    print(f"PASS: Space status retrieved ({status_data['space_id']}: stage={status_data['stage']}, ready={status_data['is_ready']})")

    # 2. Test Try-On with Non-Existent Profile -> 404
    res = client.post(
        "/api/tryon",
        json={
            "profile_id": 999999,
            "garment_image_url": "https://example.com/shirt.jpg",
            "category": "upper",
        },
    )
    assert res.status_code == 404, res.text
    print("PASS: Non-existent profile rejected with 404")

    # 3. Create a test profile without photos -> 400
    res = client.post("/api/profiles", json={"name": "TryOn Test User"})
    assert res.status_code == 201, res.text
    profile_id = res.json()["id"]

    res = client.post(
        "/api/tryon",
        json={
            "profile_id": profile_id,
            "garment_image_url": "https://example.com/shirt.jpg",
            "category": "upper",
        },
    )
    assert res.status_code == 400, res.text
    print("PASS: Profile with no photos rejected with 400")

    # 4. Upload photos for this profile (mocking validator for synthetic test image)
    from unittest.mock import patch

    img = Image.new("RGB", (300, 400), color=(180, 200, 220))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    with patch("app.routers.profiles.validate_photo_landmarks", return_value=(True, "Mock landmark valid", {})):
        res_up = client.post(
            f"/api/profiles/{profile_id}/photos",
            data={"photo_type": "upper_body"},
            files={"file": ("upper.png", io.BytesIO(png_bytes), "image/png")},
        )
        assert res_up.status_code == 201, res_up.text

        res_full = client.post(
            f"/api/profiles/{profile_id}/photos",
            data={"photo_type": "front_full_body"},
            files={"file": ("full.png", io.BytesIO(png_bytes), "image/png")},
        )
        assert res_full.status_code == 201, res_full.text
    print("PASS: Uploaded test reference photos")

    # 5. Test Try-On Execution
    # Create garment image data URI
    garment_img = Image.new("RGB", (200, 200), color=(220, 50, 50))
    g_buf = io.BytesIO()
    garment_img.save(g_buf, format="PNG")
    import base64
    garment_data_uri = "data:image/png;base64," + base64.b64encode(g_buf.getvalue()).decode("utf-8")

    # Mock execute_catvton_inference for fast unit verification
    original_inference = catvton_service.execute_catvton_inference

    def mock_inference(person_photo_path, garment_photo_path, category="overall"):
        # Synthesize a composited test image
        comp = Image.new("RGB", (768, 1024), color=(100, 150, 200))
        out_path = Path(settings.STORAGE_DIR) / "test_mock_result.png"
        comp.save(out_path)
        return out_path

    catvton_service.execute_catvton_inference = mock_inference

    try:
        res = client.post(
            "/api/tryon",
            json={
                "profile_id": profile_id,
                "garment_image_url": garment_data_uri,
                "category": "upper",
            },
        )
        assert res.status_code == 201, res.text
        tryon_data = res.json()
        assert "id" in tryon_data
        assert "access_url" in tryon_data
        result_id = tryon_data["id"]
        access_url = tryon_data["access_url"]
        print(f"PASS: Created tryon result id={result_id}, url={access_url}")

        # 6. Test Fetch TryOn Result Metadata
        res = client.get(f"/api/tryon/results/{result_id}")
        assert res.status_code == 200, res.text
        assert res.json()["id"] == result_id
        print("PASS: Retrieved tryon result metadata")

        # 7. Test Stream Result Image File
        res = client.get(access_url)
        assert res.status_code == 200, res.text
        assert res.headers["content-type"] == "image/png"
        print("PASS: Successfully streamed composited tryon image")

        # 8. Test Profile TryOn History
        res = client.get(f"/api/tryon/profile/{profile_id}")
        assert res.status_code == 200, res.text
        history = res.json()
        assert len(history) >= 1
        assert history[0]["id"] == result_id
        print(f"PASS: Profile history returned {len(history)} tryon result(s)")

    finally:
        catvton_service.execute_catvton_inference = original_inference
        # Cleanup test profile and files
        client.delete(f"/api/profiles/{profile_id}")

    print("\nALL PHASE 6 TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    test_phase6()
