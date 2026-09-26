import io
import sys
from pathlib import Path
from unittest.mock import patch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.services.catvton_service import catvton_service
from app.services.tryon_router import (
    BaseTryOnHandler,
    tryon_router_registry,
)
from app.models.schemas import PhotoType


def create_test_image_bytes(w=200, h=200, color=(180, 200, 220)):
    img = Image.new("RGB", (w, h), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_phase7():
    client = TestClient(app)

    # 1. Test Handlers List Endpoint
    res = client.get("/api/tryon/handlers")
    assert res.status_code == 200, res.text
    handlers_data = res.json()["handlers"]
    handler_names = [h["name"] for h in handlers_data]
    print(f"PASS: Handlers introspection ({len(handlers_data)} registered: {handler_names})")
    assert any("Footwear" in name for name in handler_names)
    assert any("Accessory" in name for name in handler_names)
    assert any("CatVTON" in name for name in handler_names)

    # 2. Test Classification Endpoint with Text Hints
    categories_to_test = [
        ("Classic Oxford Cotton Shirt", "shirt"),
        ("Vintage High-Waist Denim Jeans", "pants/trousers"),
        ("Summer Floral Sundress", "dress"),
        ("Leather Athletic Running Sneakers", "shoes"),
        ("Gold Choker Pendant Chain", "necklace"),
        ("Diamond Stud Earrings", "jewellery"),
        ("Wool Blend Winter Overcoat", "jacket"),
    ]

    import base64
    dummy_data_uri = "data:image/png;base64," + base64.b64encode(create_test_image_bytes(100, 100)).decode("utf-8")

    for title, expected_cat in categories_to_test:
        res = client.post(
            "/api/tryon/classify",
            json={"image_url": dummy_data_uri, "text_hint": title},
        )
        assert res.status_code == 200, res.text
        pred_cat = res.json()["category"]
        assert pred_cat == expected_cat, f"Expected {expected_cat} for '{title}', got {pred_cat}"
        assert res.json()["confidence"] > 0
    print("PASS: Verified zero-shot CLIP / text-hint classifier on all test categories")

    # 3. Setup Test User Profile
    res = client.post("/api/profiles", json={"name": "Phase7 Router User"})
    assert res.status_code == 201
    profile_id = res.json()["id"]

    try:
        # Upload mock upper_body, feet, and front_full_body photos
        upper_bytes = create_test_image_bytes(300, 400, (200, 210, 220))
        feet_bytes = create_test_image_bytes(300, 300, (150, 140, 130))
        full_bytes = create_test_image_bytes(300, 600, (210, 220, 230))

        with patch("app.routers.profiles.validate_photo_landmarks", return_value=(True, "Mock landmark valid", {})):
            r1 = client.post(
                f"/api/profiles/{profile_id}/photos",
                data={"photo_type": "upper_body"},
                files={"file": ("upper.png", io.BytesIO(upper_bytes), "image/png")},
            )
            assert r1.status_code == 201, r1.text

            r2 = client.post(
                f"/api/profiles/{profile_id}/photos",
                data={"photo_type": "feet"},
                files={"file": ("feet.png", io.BytesIO(feet_bytes), "image/png")},
            )
            assert r2.status_code == 201, r2.text

            r3 = client.post(
                f"/api/profiles/{profile_id}/photos",
                data={"photo_type": "front_full_body"},
                files={"file": ("full.png", io.BytesIO(full_bytes), "image/png")},
            )
            assert r3.status_code == 201, r3.text
        print("PASS: Uploaded reference photos for upper_body, feet, and full_body")

        # 4. Test Shoes Routing -> Uses ShoesHandler and Feet Photo
        res_shoes = client.post(
            "/api/tryon",
            json={
                "profile_id": profile_id,
                "garment_image_url": dummy_data_uri,
                "category": "shoes",
            },
        )
        assert res_shoes.status_code == 201, res_shoes.text
        shoes_data = res_shoes.json()
        assert shoes_data["category"] == "shoes"
        assert "Footwear" in shoes_data["handler_name"]
        assert shoes_data["access_url"].startswith("/api/tryon/results/")

        # Verify streamed output image is a valid PNG
        stream_res = client.get(shoes_data["access_url"])
        assert stream_res.status_code == 200
        assert stream_res.headers["content-type"] == "image/png"
        print(f"PASS: Shoes routed to {shoes_data['handler_name']} using feet photo")

        # 5. Test Accessory / Necklace Routing -> Uses AccessoryMediaPipeHandler
        res_necklace = client.post(
            "/api/tryon",
            json={
                "profile_id": profile_id,
                "garment_image_url": dummy_data_uri,
                "category": "necklace",
            },
        )
        assert res_necklace.status_code == 201, res_necklace.text
        necklace_data = res_necklace.json()
        assert necklace_data["category"] == "necklace"
        assert "MediaPipe" in necklace_data["handler_name"]

        stream_res2 = client.get(necklace_data["access_url"])
        assert stream_res2.status_code == 200
        assert stream_res2.headers["content-type"] == "image/png"
        print(f"PASS: Necklace routed to {necklace_data['handler_name']} using MediaPipe")

        # 6. Test Apparel Routing -> Uses ClothingCatVTONHandler
        original_inference = catvton_service.execute_catvton_inference

        def mock_apparel_inference(person_photo_path, garment_photo_path, category="overall"):
            comp = Image.new("RGB", (768, 1024), color=(120, 160, 200))
            out_path = Path(settings.STORAGE_DIR) / "mock_apparel_result.png"
            comp.save(out_path)
            return out_path

        catvton_service.execute_catvton_inference = mock_apparel_inference

        try:
            res_shirt = client.post(
                "/api/tryon",
                json={
                    "profile_id": profile_id,
                    "garment_image_url": dummy_data_uri,
                    "category": "shirt",
                },
            )
            assert res_shirt.status_code == 201, res_shirt.text
            shirt_data = res_shirt.json()
            assert shirt_data["category"] == "shirt"
            assert "CatVTON" in shirt_data["handler_name"]
            print(f"PASS: Shirt routed to {shirt_data['handler_name']}")
        finally:
            catvton_service.execute_catvton_inference = original_inference

        # 7. Test Plugin Extensibility: Add a new custom category handler without touching existing code
        class CustomHatHandler(BaseTryOnHandler):
            @property
            def name(self) -> str:
                return "Custom Headwear & Hat Handler"

            @property
            def supported_categories(self):
                return ["hat", "beanie", "cap"]

            def get_preferred_photo_type(self, category):
                return PhotoType.FACE

            def get_fallback_photo_type(self, category):
                return PhotoType.UPPER_BODY

            def execute(self, person_photo_path, garment_photo_path, category, profile_id, conn):
                comp = Image.new("RGB", (400, 400), color=(10, 20, 30))
                out_path = Path(settings.STORAGE_DIR) / "hat_test.png"
                comp.save(out_path)
                return out_path

        # Register plugin dynamically
        hat_handler = CustomHatHandler()
        tryon_router_registry.register_handler(hat_handler)

        resolved_handler = tryon_router_registry.get_handler("beanie")
        assert resolved_handler.name == "Custom Headwear & Hat Handler"
        print(f"PASS: Dynamic plugin registered and retrieved: {resolved_handler.name}")

    finally:
        client.delete(f"/api/profiles/{profile_id}")

    print("\nALL PHASE 7 TESTS PASSED SUCCESSFULLY! [SUCCESS]")


if __name__ == "__main__":
    test_phase7()
