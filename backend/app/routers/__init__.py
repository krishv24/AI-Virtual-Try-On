"""API Routers package."""
from app.routers.profiles import router as profiles_router
from app.routers.photos import router as photos_router

__all__ = ["profiles_router", "photos_router"]
