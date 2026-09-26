import io
import sys
from pathlib import Path
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.services.mediapipe_validator import validate_photo_landmarks
from app.models.schemas import PhotoType

def create_blank_image_bytes():
    img = Image.new("RGB", (200, 200), color=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def test_phase2():
    client = TestClient(app)

    # 1. Test Multiple Saved Profiles
    res1 = client.post("/api/profiles", json={"name": "Everyday Fit"})
    assert res1.status_code == 201
    profile_id_1 = res1.json()["id"]

    res2 = client.post("/api/profiles", json={"name": "Athletic Wear"})
    assert res2.status_code == 201
    profile_id_2 = res2.json()["id"]

    res_list = client.get("/api/profiles")
    assert res_list.status_code == 200
    ids = [p["id"] for p in res_list.json()]
    assert profile_id_1 in ids and profile_id_2 in ids
    print(f"PASS: Multiple profiles created successfully (IDs: {profile_id_1}, {profile_id_2})")

    # 2. Test MediaPipe rejection on invalid blank image for front_full_body
    blank_bytes = create_blank_image_bytes()
    files = {"file": ("blank.png", io.BytesIO(blank_bytes), "image/png")}
    data = {"photo_type": "front_full_body"}
    res_reject = client.post(f"/api/profiles/{profile_id_1}/photos", data=data, files=files)
    assert res_reject.status_code == 422, f"Expected 422 rejection, got {res_reject.status_code}: {res_reject.text}"
    error_detail = res_reject.json()["detail"]
    assert "MediaPipe validation rejected" in error_detail
    print(f"PASS: MediaPipe correctly rejected invalid photo with message: {error_detail}")

    # 3. Test MediaPipe rejection on invalid blank image for face
    files = {"file": ("blank.png", io.BytesIO(blank_bytes), "image/png")}
    data = {"photo_type": "face"}
    res_face_reject = client.post(f"/api/profiles/{profile_id_1}/photos", data=data, files=files)
    assert res_face_reject.status_code == 422
    print("PASS: MediaPipe correctly rejected blank image for face photo slot")

    # 4. Test foot heuristic acceptance
    # Standalone shoes on textured ground
    shoe_img = Image.new("RGB", (300, 300), color=(180, 140, 100))
    draw = ImageDraw.Draw(shoe_img)
    draw.rectangle([50, 80, 120, 240], fill=(20, 20, 20)) # left shoe
    draw.rectangle([180, 80, 250, 240], fill=(20, 20, 20)) # right shoe
    buf = io.BytesIO()
    shoe_img.save(buf, format="PNG")
    shoe_bytes = buf.getvalue()

    files = {"file": ("shoes.png", io.BytesIO(shoe_bytes), "image/png")}
    data = {"photo_type": "feet"}
    res_feet = client.post(f"/api/profiles/{profile_id_1}/photos", data=data, files=files)
    assert res_feet.status_code == 201, f"Feet upload error: {res_feet.text}"
    print("PASS: Foot/shoe photo upload passed validation")

    # 5. Verify Profile 1 has 1 photo, Profile 2 has 0 photos
    detail1 = client.get(f"/api/profiles/{profile_id_1}").json()
    detail2 = client.get(f"/api/profiles/{profile_id_2}").json()
    assert len(detail1["photos"]) == 1
    assert len(detail2["photos"]) == 0
    print("PASS: Verified photo isolation across multiple profiles")

    # 6. Clean up test profiles
    client.delete(f"/api/profiles/{profile_id_1}")
    client.delete(f"/api/profiles/{profile_id_2}")
    print("PASS: Profile cleanup completed")

    print("\nALL PHASE 2 TESTS PASSED! [SUCCESS]")

if __name__ == "__main__":
    test_phase2()
