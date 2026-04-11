"""Food catalog repository contract."""

from __future__ import annotations

from typing import Protocol

from ..models.food import Food


class FoodRepository(Protocol):
    """Persistence contract for the nutrition food catalog."""

    async def add(self, food: Food) -> Food:
        """Persist a new food."""

    async def update(self, food: Food) -> Food:
        """Persist an updated food."""

    async def delete(self, food_id: str) -> None:
        """Delete a food."""

    def get_food_by_id(self, food_id: str) -> Food:
        """Load a food by ID."""

    def get_all_foods(self) -> list[Food]:
        """Load all foods."""

    def food_name_exists(
        self,
        name: str,
        brand: str | None,
        exclude_food_id: str | None = None,
    ) -> bool:
        """Return whether a food with the same name and brand already exists."""

    def barcode_exists(
        self,
        barcode: str | None,
        exclude_food_id: str | None = None,
    ) -> bool:
        """Return whether a barcode already exists."""
