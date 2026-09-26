from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional
import sqlite3
from app.models.schemas import PhotoType


class BaseTryOnHandler(ABC):
    """
    Abstract base class for try-on category handlers in the plugin router.
    Each handler is responsible for a specific family of garments/items (clothing, shoes, accessories),
    determines the optimal reference photo type, and executes the synthesis/compositing pipeline.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable handler name."""
        pass

    @property
    @abstractmethod
    def supported_categories(self) -> List[str]:
        """List of category identifiers handled by this plugin."""
        pass

    def can_handle(self, category: str) -> bool:
        """Return True if this plugin can handle the given category."""
        clean = (category or "").lower().strip()
        return any(
            clean == sc.lower() or sc.lower() in clean
            for sc in self.supported_categories
        )

    @abstractmethod
    def get_preferred_photo_type(self, category: str) -> PhotoType:
        """Return the ideal photo slot for this category (e.g. UPPER_BODY, LEGS, FEET, FACE)."""
        pass

    @abstractmethod
    def get_fallback_photo_type(self, category: str) -> Optional[PhotoType]:
        """Return secondary fallback photo slot if preferred is not uploaded."""
        pass

    @abstractmethod
    def execute(
        self,
        person_photo_path: Path,
        garment_photo_path: Path,
        category: str,
        profile_id: int,
        conn: sqlite3.Connection,
    ) -> Path:
        """
        Execute the compositing/synthesis process.
        Returns the Path to the generated composited image file.
        """
        pass
