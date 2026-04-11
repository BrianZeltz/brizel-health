"""Home Assistant backed nutrition repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...domains.nutrition.common import normalize_optional_text
from ...domains.nutrition.errors import BrizelFoodNotFoundError
from ...domains.nutrition.models.food import (
    Food,
    normalize_food_name,
)

if TYPE_CHECKING:
    from ..storage.store_manager import BrizelHealthStoreManager


class HomeAssistantNutritionRepository:
    """Persist foods inside the integration store."""

    def __init__(self, store_manager: "BrizelHealthStoreManager") -> None:
        """Initialize the repository."""
        self._store_manager = store_manager

    def _foods(self) -> dict[str, dict]:
        """Return the mutable food bucket."""
        nutrition = self._store_manager.data.setdefault("nutrition", {})
        return nutrition.setdefault("foods", {})

    async def add(self, food: Food) -> Food:
        """Persist a new food."""
        self._foods()[food.food_id] = food.to_dict()
        await self._store_manager.async_save()
        return food

    async def update(self, food: Food) -> Food:
        """Persist an existing food."""
        self.get_food_by_id(food.food_id)
        self._foods()[food.food_id] = food.to_dict()
        await self._store_manager.async_save()
        return food

    async def delete(self, food_id: str) -> None:
        """Delete a food."""
        self.get_food_by_id(food_id)
        del self._foods()[food_id]
        await self._store_manager.async_save()

    def get_food_by_id(self, food_id: str) -> Food:
        """Load a food by ID."""
        food_data = self._foods().get(food_id)
        if food_data is None:
            raise BrizelFoodNotFoundError(
                f"No food found for food_id '{food_id}'."
            )
        return Food.from_dict(food_data)

    def get_all_foods(self) -> list[Food]:
        """Load all foods."""
        return [Food.from_dict(data) for data in self._foods().values()]

    def food_name_exists(
        self,
        name: str,
        brand: str | None,
        exclude_food_id: str | None = None,
    ) -> bool:
        """Return whether a food with the same name and brand already exists."""
        normalized_name = normalize_food_name(name).casefold()
        normalized_brand = normalize_optional_text(brand)
        normalized_brand_casefold = (
            normalized_brand.casefold() if normalized_brand is not None else None
        )

        for food_id, food_data in self._foods().items():
            if exclude_food_id is not None and food_id == exclude_food_id:
                continue

            existing_name = normalize_food_name(
                str(food_data.get("name", ""))
            ).casefold()
            existing_brand = normalize_optional_text(food_data.get("brand"))
            existing_brand_casefold = (
                existing_brand.casefold() if existing_brand is not None else None
            )

            if (
                existing_name == normalized_name
                and existing_brand_casefold == normalized_brand_casefold
            ):
                return True

        return False

    def barcode_exists(
        self,
        barcode: str | None,
        exclude_food_id: str | None = None,
    ) -> bool:
        """Return whether a barcode already exists."""
        normalized_barcode = normalize_optional_text(barcode)
        if normalized_barcode is None:
            return False

        for food_id, food_data in self._foods().items():
            if exclude_food_id is not None and food_id == exclude_food_id:
                continue

            existing_barcode = normalize_optional_text(food_data.get("barcode"))
            if existing_barcode == normalized_barcode:
                return True

        return False
