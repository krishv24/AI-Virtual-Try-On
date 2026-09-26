from typing import Dict, List, Optional
from app.services.tryon_router.base import BaseTryOnHandler
from app.services.tryon_router.clothing_handler import ClothingCatVTONHandler
from app.services.tryon_router.shoes_handler import ShoesHandler
from app.services.tryon_router.accessory_handler import AccessoryMediaPipeHandler


class TryOnRouterRegistry:
    """
    Extensible plugin-style try-on router registry.
    Maps categories to specialized execution handlers (diffusion, landmark placement, footwear).
    New categories/handlers can be registered dynamically without modifying existing handlers.
    """

    def __init__(self):
        self._handlers: List[BaseTryOnHandler] = []
        self._default_handler = ClothingCatVTONHandler()
        self._register_defaults()

    def _register_defaults(self):
        """Register built-in Phase 7 handlers in priority order."""
        # 1. Shoes handler
        self.register_handler(ShoesHandler())
        # 2. Accessory & Jewellery landmark handler
        self.register_handler(AccessoryMediaPipeHandler())
        # 3. CatVTON apparel handler
        self.register_handler(self._default_handler)

    def register_handler(self, handler: BaseTryOnHandler):
        """Register a new plugin handler (prepended for high priority matching)."""
        if handler not in self._handlers:
            self._handlers.insert(0, handler)

    def get_handler(self, category: str) -> BaseTryOnHandler:
        """Find the matching handler for a category, fallback to default CatVTON handler."""
        for handler in self._handlers:
            if handler.can_handle(category):
                return handler
        return self._default_handler

    def list_handlers(self) -> List[Dict[str, any]]:
        """Return introspection info on registered handlers."""
        return [
            {
                "name": h.name,
                "supported_categories": h.supported_categories,
            }
            for h in self._handlers
        ]


# Singleton instance
tryon_router_registry = TryOnRouterRegistry()
