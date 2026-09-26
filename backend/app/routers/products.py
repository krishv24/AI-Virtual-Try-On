import json
from datetime import datetime, timezone
from typing import List, Optional
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from app.database import get_db
from app.models.schemas import ProductCreate, ProductResponse

router = APIRouter(prefix="/api/products", tags=["Products"])

def format_product_row(row: sqlite3.Row) -> ProductResponse:
    images = []
    if row["image_urls"]:
        try:
            images = json.loads(row["image_urls"])
        except Exception:
            images = [row["image_urls"]]

    return ProductResponse(
        id=row["id"],
        source_url=row["source_url"],
        title=row["title"],
        image_urls=images,
        category=row["category"],
        price=row["price"],
        detected_at=row["detected_at"],
    )

@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def register_product(payload: ProductCreate, conn: sqlite3.Connection = Depends(get_db)):
    """Register or save a detected product into the database."""
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.cursor()

    # Check if product with this source_url already exists
    cursor.execute("SELECT id FROM products WHERE source_url = ?;", (payload.source_url,))
    existing = cursor.fetchone()

    images_json = json.dumps(payload.image_urls)
    if existing:
        product_id = existing["id"]
        cursor.execute(
            """
            UPDATE products
            SET title = ?, image_urls = ?, category = ?, price = ?, detected_at = ?
            WHERE id = ?;
            """,
            (payload.title, images_json, payload.category, payload.price, now, product_id),
        )
    else:
        cursor.execute(
            """
            INSERT INTO products (source_url, title, image_urls, category, price, detected_at)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (payload.source_url, payload.title, images_json, payload.category, payload.price, now),
        )
        product_id = cursor.lastrowid

    cursor.execute("SELECT * FROM products WHERE id = ?;", (product_id,))
    row = cursor.fetchone()
    return format_product_row(row)


@router.get("", response_model=List[ProductResponse])
def list_products(limit: int = 50, conn: sqlite3.Connection = Depends(get_db)):
    """List detected and saved products."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products ORDER BY id DESC LIMIT ?;", (limit,))
    rows = cursor.fetchall()
    return [format_product_row(r) for r in rows]


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, conn: sqlite3.Connection = Depends(get_db)):
    """Get a specific product by ID."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?;", (product_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    return format_product_row(row)
