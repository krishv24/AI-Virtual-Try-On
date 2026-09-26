from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field
import os
from pathlib import Path

# Locate backend root for .env
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = True
    
    # CORS
    CORS_ORIGINS: List[str] = ["*"]
    
    # Database
    DATABASE_URL: str = "sqlite:///./tryon.db"
    
    # AI Models (Free tiers)
    HF_TOKEN: str = ""
    HF_CATVTON_SPACE_URL: str = ""
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
