import sqlite3
from contextlib import contextmanager
from typing import Generator
from app.config import settings

def get_connection() -> sqlite3.Connection:
    """Create a new SQLite connection with foreign keys and WAL enabled."""
    conn = sqlite3.connect(
        settings.DB_PATH,
        check_same_thread=False,
        timeout=10.0,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

@contextmanager
def get_db_context() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite operations."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def get_db() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency for database access."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """Initialize database tables according to the Phase 1 schema."""
    with get_db_context() as conn:
        cursor = conn.cursor()

        # 1. profiles table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)

        # 2. profile_photos table
        # photo_type values: front_full_body, upper_body, legs, feet, face
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS profile_photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                photo_type TEXT NOT NULL CHECK(photo_type IN ('front_full_body', 'upper_body', 'legs', 'feet', 'face')),
                file_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            );
        """)

        # 3. products table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_url TEXT NOT NULL,
                title TEXT,
                image_urls TEXT,
                category TEXT,
                price TEXT,
                detected_at TEXT NOT NULL
            );
        """)

        # 4. tryon_results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tryon_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                product_id INTEGER,
                category TEXT NOT NULL,
                image_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
            );
        """)

        # Indexing for high-performance lookup
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_photos_profile_id ON profile_photos(profile_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_photos_type ON profile_photos(photo_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tryon_profile_id ON tryon_results(profile_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_source_url ON products(source_url);")
