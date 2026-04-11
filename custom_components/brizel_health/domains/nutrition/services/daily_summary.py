"""Daily nutrition summary calculations."""

from __future__ import annotations

from ..models.food_entry import FoodEntry


def calculate_daily_summary(food_entries: list[FoodEntry]) -> dict[str, float]:
    """Aggregate nutrition totals for a list of food entries."""
    return {
        "kcal": round(sum(food_entry.kcal for food_entry in food_entries), 2),
        "protein": round(sum(food_entry.protein for food_entry in food_entries), 2),
        "carbs": round(sum(food_entry.carbs for food_entry in food_entries), 2),
        "fat": round(sum(food_entry.fat for food_entry in food_entries), 2),
    }
