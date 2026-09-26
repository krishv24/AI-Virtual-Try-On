import base64
import io
import sys
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.services.catvton_service import catvton_service
from app.services.accuracy_validator import accuracy_validator


def create_colored_image_bytes(w=200, h=200, color=(200, 40, 40)):
    img = Image.new("RGB", (w, h), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def create_striped_image(w=200, h=200):
    img = Image.new("RGB", (w, h), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    for x in range(0, w, 10):
        draw.line([(x, 0), (x, h)], fill=(0, 0, 0), width=4)
    return img


def test_phase9():
    print("--- 1. Testing AccuracyValidator Unit Checks ---")

    # A. Matching Colors (Red garment vs Red Try-On Result)
    orig_red_shirt = Image.new("RGB", (300, 300), color=(210, 30, 30))
    comp_red_result = Image.new("RGB", (768, 1024), color=(220, 220, 220)) # background
    # Paint red shirt in upper body region (y: 250 to 600)
    draw = ImageDraw.Draw(comp_red_result)
    draw.rectangle([150, 250, 618, 620], fill=(205, 32, 28))

    match_metrics = accuracy_validator.validate_accuracy(
        orig_red_shirt, comp_red_result, category="upper"
    )
    print(f"PASS: Matching color test -> Score: {match_metrics['accuracy_score']}, Low Confidence: {match_metrics['is_low_confidence']}")
    assert match_metrics["accuracy_score"] >= 0.50, f"Expected >= 0.50, got {match_metrics['accuracy_score']}"
    assert match_metrics["is_low_confidence"] is False
    assert match_metrics["dominant_color_delta"] < 0.20

    # B. Drastic Color Mismatch (Red Garment vs Generated Blue Shirt)
    comp_blue_result = Image.new("RGB", (768, 1024), color=(220, 220, 220))
    draw_blue = ImageDraw.Draw(comp_blue_result)
    draw_blue.rectangle([150, 250, 618, 620], fill=(20, 40, 220)) # BLUE garment!

    mismatch_metrics = accuracy_validator.validate_accuracy(
        orig_red_shirt, comp_blue_result, category="upper"
    )
    print(f"PASS: Color mismatch test -> Score: {mismatch_metrics['accuracy_score']}, Low Confidence: {mismatch_metrics['is_low_confidence']}, Reason: {mismatch_metrics['flag_reason']}")
    assert mismatch_metrics["is_low_confidence"] is True
    assert mismatch_metrics["accuracy_score"] < 0.50
    assert mismatch_metrics["dominant_color_delta"] > 0.30
    assert mismatch_metrics["flag_reason"] is not None

    # C. Pattern Roughness Check
    solid_img = Image.new("RGB", (200, 200), color=(100, 100, 100))
    striped_img = create_striped_image(200, 200)
    solid_rough = accuracy_validator.compute_pattern_roughness(solid_img)
    striped_rough = accuracy_validator.compute_pattern_roughness(striped_img)
    assert striped_rough > solid_rough
    print(f"PASS: Pattern roughness detected (Solid={solid_rough:.3f}, Striped={striped_rough:.3f})")

    print("\n--- 2. Testing End-to-End API Integration with Accuracy Safeguards ---")
    client = TestClient(app)

    # Setup Test Profile
    res = client.post("/api/profiles", json={"name": "Accuracy Safeguard Test User"})
    assert res.status_code == 201
    profile_id = res.json()["id"]

    try:
        # Upload valid test photo
        photo_bytes = create_colored_image_bytes(300, 400, (180, 200, 220))
        with patch("app.routers.profiles.validate_photo_landmarks", return_value=(True, "Mock landmark valid", {})):
            r = client.post(
                f"/api/profiles/{profile_id}/photos",
                data={"photo_type": "upper_body"},
                files={"file": ("upper.png", io.BytesIO(photo_bytes), "image/png")},
            )
            assert r.status_code == 201

        # Garment Data URI (Red T-Shirt)
        garment_bytes = create_colored_image_bytes(200, 200, (220, 30, 30))
        garment_data_uri = "data:image/png;base64," + base64.b64encode(garment_bytes).decode("utf-8")

        # Mock CatVTON inference returning a matching red composited image
        def mock_matching_inference(person_photo_path, garment_photo_path, category="overall"):
            comp = Image.new("RGB", (768, 1024), color=(240, 240, 240))
            d = ImageDraw.Draw(comp)
            d.rectangle([150, 240, 618, 620], fill=(215, 35, 35))
            out_p = Path(settings.STORAGE_DIR) / "test_acc_match.png"
            comp.save(out_p)
            return out_p

        catvton_service.execute_catvton_inference = mock_matching_inference

        res_tryon_match = client.post(
            "/api/tryon",
            json={
                "profile_id": profile_id,
                "garment_image_url": garment_data_uri,
                "category": "t-shirt/top",
            },
        )
        assert res_tryon_match.status_code == 201, res_tryon_match.text
        match_data = res_tryon_match.json()
        assert "accuracy_score" in match_data
        assert match_data["is_low_confidence"] is False
        assert match_data["accuracy_score"] >= 0.50
        result_id_1 = match_data["id"]
        print(f"PASS: High fidelity try-on generated (id={result_id_1}, score={match_data['accuracy_score']}, low_conf={match_data['is_low_confidence']})")

        # Mock CatVTON inference returning a severe color drift (Neon Green instead of Red)
        def mock_drifting_inference(person_photo_path, garment_photo_path, category="overall"):
            comp = Image.new("RGB", (768, 1024), color=(240, 240, 240))
            d = ImageDraw.Draw(comp)
            d.rectangle([150, 240, 618, 620], fill=(20, 230, 40)) # NEON GREEN!
            out_p = Path(settings.STORAGE_DIR) / "test_acc_drift.png"
            comp.save(out_p)
            return out_p

        catvton_service.execute_catvton_inference = mock_drifting_inference

        res_tryon_drift = client.post(
            "/api/tryon",
            json={
                "profile_id": profile_id,
                "garment_image_url": garment_data_uri,
                "category": "t-shirt/top",
            },
        )
        assert res_tryon_drift.status_code == 201, res_tryon_drift.text
        drift_data = res_tryon_drift.json()
        assert drift_data["is_low_confidence"] is True
        assert drift_data["accuracy_score"] < 0.50
        assert drift_data["accuracy_metrics"]["flag_reason"] is not None
        result_id_2 = drift_data["id"]
        print(f"PASS: Safeguard flagged color-drifted try-on as LOW CONFIDENCE (id={result_id_2}, score={drift_data['accuracy_score']}, reason='{drift_data['accuracy_metrics']['flag_reason']}')")

        # 3. Test Database Persistence & Retrieval
        res_get = client.get(f"/api/tryon/results/{result_id_2}")
        assert res_get.status_code == 200
        get_data = res_get.json()
        assert get_data["id"] == result_id_2
        assert get_data["is_low_confidence"] is True
        assert get_data["accuracy_metrics"]["dominant_color_delta"] > 0.30
        print("PASS: Verified accuracy metrics persisted in SQLite database and retrieved via GET /results/{id}")

        # 4. Test Profile History
        res_hist = client.get(f"/api/tryon/profile/{profile_id}")
        assert res_hist.status_code == 200
        hist_items = res_hist.json()
        assert len(hist_items) == 2
        assert any(item["is_low_confidence"] is True for item in hist_items)
        assert any(item["is_low_confidence"] is False for item in hist_items)
        print("PASS: Profile try-on history accurately reports accuracy flags per generation")

    finally:
        client.delete(f"/api/profiles/{profile_id}")

    print("\nALL PHASE 9 ACCURACY SAFEGUARD TESTS PASSED SUCCESSFULLY! [SUCCESS]")


if __name__ == "__main__":
    test_phase9()
