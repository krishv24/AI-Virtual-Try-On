import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app

def test_phase4_products():
    client = TestClient(app)

    # 1. Register a scraped product
    product_payload = {
        "source_url": "https://www.example-store.com/products/oversized-hoodie",
        "title": "Minimalist Oversized Fleece Hoodie",
        "image_urls": [
            "https://images.example.com/hoodie-front.jpg",
            "https://images.example.com/hoodie-back.jpg",
            "https://images.example.com/hoodie-model.jpg"
        ],
        "category": "Upper Body",
        "price": "$68.00"
    }

    res = client.post("/api/products", json=product_payload)
    assert res.status_code == 201, res.text
    prod = res.json()
    prod_id = prod["id"]
    assert prod["title"] == product_payload["title"]
    assert len(prod["image_urls"]) == 3
    assert prod["price"] == "$68.00"
    print(f"PASS: Product registered with ID {prod_id}")

    # 2. Update existing product with same source_url (idempotent upsert)
    product_payload["price"] = "$62.00"
    res_update = client.post("/api/products", json=product_payload)
    assert res_update.status_code == 201
    assert res_update.json()["id"] == prod_id
    assert res_update.json()["price"] == "$62.00"
    print("PASS: Product upsert on matching source_url verified")

    # 3. List products
    res_list = client.get("/api/products")
    assert res_list.status_code == 200
    products = res_list.json()
    assert any(p["id"] == prod_id for p in products)
    print(f"PASS: Products list verified ({len(products)} products found)")

    # 4. Get product detail
    res_get = client.get(f"/api/products/{prod_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == prod_id
    print("PASS: Product get by ID verified")

    print("\nALL PHASE 4 BACKEND TESTS PASSED! [SUCCESS]")

if __name__ == "__main__":
    test_phase4_products()
