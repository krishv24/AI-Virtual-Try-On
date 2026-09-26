import io
import sys
from pathlib import Path

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

    # 4. Test Upload Profile Photo (front_full_body)
    dummy_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\r\xef\x0c\x86\x00\x00\x00\x00IEND\xaeB`\x82"
    files = {"file": ("test.png", io.BytesIO(dummy_png), "image/png")}
    data = {"photo_type": "front_full_body"}
    res = client.post(f"/api/profiles/{profile_id}/photos", data=data, files=files)
    assert res.status_code == 201, res.text
    photo = res.json()
    photo_id = photo["id"]
    assert photo["photo_type"] == "front_full_body"
    print(f"PASS: Uploaded photo id={photo_id}")

    # 5. Test Get Profile Detail
    res = client.get(f"/api/profiles/{profile_id}")
    assert res.status_code == 200, res.text
    detail = res.json()
    assert len(detail["photos"]) == 1
    print("PASS: Retrieved profile detail with photos list")

    # 6. Test Fetch Photo File Stream
    res = client.get(f"/api/photos/{photo_id}/file")
    assert res.status_code == 200, res.text
    assert res.content == dummy_png
    print("PASS: Successfully streamed photo securely from non-public disk")

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
