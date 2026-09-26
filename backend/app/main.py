from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Dict, Any

from app.config import settings

app = FastAPI(
    title="AI Virtual Try-On API",
    description="Backend API for AI Virtual Try-On Chrome Extension using CatVTON, CLIP, and MediaPipe.",
    version="0.1.0",
)

# Configure CORS for Chrome Extension and local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    database: str
    pipeline: Dict[str, str]
    timestamp: str


@app.get("/", tags=["General"])
async def root():
    return {
        "message": "AI Virtual Try-On Backend is running.",
        "docs": "/docs",
        "health": "/health",
        "version": "0.1.0",
    }


@app.get("/health", response_model=HealthResponse, tags=["Diagnostics"])
async def health_check():
    """
    Health check endpoint for extension popup and side panel status indicators.
    """
    return HealthResponse(
        status="healthy",
        service="AI Virtual Try-On Backend",
        version="0.1.0",
        database="sqlite",
        pipeline={
            "tryon": "CatVTON / IDM-VTON (Hugging Face Spaces ZeroGPU)",
            "classification": "CLIP (Open-Weight)",
            "pose": "MediaPipe (Local)",
            "styling": "Groq / Gemini (Free Tier)",
        },
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
