from typing import List
from pydantic_settings import BaseSettings
from pathlib import Path
import os

# Locate backend root
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = True
    
    # CORS
    CORS_ORIGINS: List[str] = ["*"]
    
    # Database
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'tryon.db'}"
    DB_PATH: Path = BASE_DIR / "tryon.db"
    
    # Private storage directory for photos (NEVER exposed publicly as static files)
    STORAGE_DIR: Path = BASE_DIR / "storage" / "private_uploads"
    
    # AI Models (Free tiers from techstack.txt)
    HF_TOKEN: str = ""
    HF_CATVTON_SPACE_URL: str = ""
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

# Ensure private storage directory exists
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
