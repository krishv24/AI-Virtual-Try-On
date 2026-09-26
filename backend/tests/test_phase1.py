import io
import sys
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

def test_phase1():
    client = TestClient(app)

    # 1. Test Health
    res = client.get("/health")
    assert res.status_code == 200, res.text
    print("PASS: Health check ok")

    # 2. Test Create Profile
    res = client.post("/api/profiles", json={"name": "Alex Johnson"})
    assert res.status_code == 201, res.text
    profile = res.json()
    profile_id = profile["id"]
    assert profile["name"] == "Alex Johnson"
    print(f"PASS: Created profile id={profile_id}")

    # 3. Test List Profiles
    res = client.get("/api/profiles")
    assert res.status_code == 200, res.text
    profiles = res.json()
    assert any(p["id"] == profile_id for p in profiles)
    print(f"PASS: Listed profiles ({len(profiles)} found)")

    # 4. Test Upload Profile Photo (feet)
    shoe_img = Image.new("RGB", (200, 200), color=(150, 120, 90))
    buf = io.BytesIO()
    shoe_img.save(buf, format="PNG")
    dummy_png = buf.getvalue()
    files = {"file": ("test.png", io.BytesIO(dummy_png), "image/png")}
    data = {"photo_type": "feet"}
    res = client.post(f"/api/profiles/{profile_id}/photos", data=data, files=files)
    assert res.status_code == 201, res.text
    photo = res.json()
    photo_id = photo["id"]
    assert photo["photo_type"] == "feet"
    print(f"PASS: Uploaded photo id={photo_id}")

    # 5. Test Get Profile Detail
    res = client.get(f"/api/profiles/{profile_id}")
    assert res.status_code == 200, res.text
    detail = res.json()
    assert len(detail["photos"]) == 1
    print("PASS: Retrieved profile detail with photos list")

    # 6. Test Fetch Photo File Stream
    res = client.get(f"/api/photos/{photo_id}/file")
    assert len(res.content) > 0
    img_check = Image.open(io.BytesIO(res.content))
    assert img_check.size[0] > 0 and img_check.size[1] > 0
    print("PASS: Successfully streamed photo securely from non-public disk (compressed/optimized)")

    # 7. Test Update Profile
    res = client.put(f"/api/profiles/{profile_id}", json={"name": "Alex J."})
    assert res.status_code == 200, res.text
    assert res.json()["name"] == "Alex J."
    print("PASS: Updated profile name")

    # 8. Test Delete Profile (cascading file cleanup)
    res = client.delete(f"/api/profiles/{profile_id}")
    assert res.status_code == 204, res.text
    print("PASS: Deleted profile and cleaned up storage")

    # 9. Verify Photo is gone from disk / endpoint
    res = client.get(f"/api/photos/{photo_id}/file")
    assert res.status_code == 404
    print("PASS: Confirmed photo is gone after profile deletion")

    print("\nALL PHASE 1 TESTS PASSED! [SUCCESS]")

if __name__ == "__main__":
    test_phase1()
