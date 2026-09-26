from app.services.tryon_router.base import BaseTryOnHandler
from app.services.tryon_router.clothing_handler import ClothingCatVTONHandler
from app.services.tryon_router.shoes_handler import ShoesHandler
from app.services.tryon_router.accessory_handler import AccessoryMediaPipeHandler
from app.services.tryon_router.registry import (
    TryOnRouterRegistry,
    tryon_router_registry,
)

__all__ = [
    "BaseTryOnHandler",
    "ClothingCatVTONHandler",
    "ShoesHandler",
    "AccessoryMediaPipeHandler",
    "TryOnRouterRegistry",
    "tryon_router_registry",
]
