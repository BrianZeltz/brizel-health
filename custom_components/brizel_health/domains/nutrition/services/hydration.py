"""Hydration summary calculations built on top of food entries."""

from __future__ import annotations

from typing import TypedDict

from ..models.food import Food
from ..models.food_entry import FoodEntry
from .water import (
    INTERNAL_WATER_FOOD_ID,
    build_internal_water_food,
    matches_internal_water_definition,
)


class HydrationBreakdownItem(TypedDict):
    """Single food contribution within a hydration report."""

    food_id: str
    food_name: str
    food_brand: str | None
    hydration_kind: str
    hydration_source: str
    hydration_ml: float
    entry_count: int


class HydrationReport(TypedDict):
    """Hydration totals plus a food-level breakdown."""

    drank_ml: float
    food_hydration_ml: float
    total_hydration_ml: float
    breakdown: list[HydrationBreakdownItem]


def _resolve_food_for_hydration(
    food_entry: FoodEntry,
    foods_by_id: dict[str, Food],
) -> Food | None:
    """Resolve the catalog food used for hydration calculations."""
    food = foods_by_id.get(food_entry.food_id)

    # Water should still count even if the catalog food was not eagerly loaded.
    if food_entry.food_id == INTERNAL_WATER_FOOD_ID and (
        food is None or not matches_internal_water_definition(food)
    ):
        return build_internal_water_food()

    return food


def calculate_hydration_report(
    food_entries: list[FoodEntry],
    foods_by_id: dict[str, Food],
) -> HydrationReport:
    """Aggregate hydration totals and a food-level breakdown."""
    drank_ml = 0.0
    food_hydration_ml = 0.0
    breakdown_by_food: dict[str, HydrationBreakdownItem] = {}

    for food_entry in food_entries:
        food = _resolve_food_for_hydration(food_entry, foods_by_id)
        if food is None or not food.has_hydration_data():
            continue

        hydration_ml = food.calculate_hydration_ml(food_entry.grams)
        if hydration_ml <= 0:
            continue

        if food.is_hydration_drink():
            drank_ml += hydration_ml
        elif food.is_hydration_food():
            food_hydration_ml += hydration_ml

        breakdown_item = breakdown_by_food.setdefault(
            food.food_id,
            {
                "food_id": food.food_id,
                "food_name": food.name,
                "food_brand": food.brand,
                "hydration_kind": food.hydration_kind or "",
                "hydration_source": food.get_hydration_source(),
                "hydration_ml": 0.0,
                "entry_count": 0,
            },
        )
        breakdown_item["hydration_ml"] = round(
            breakdown_item["hydration_ml"] + hydration_ml,
            2,
        )
        breakdown_item["entry_count"] += 1

    breakdown = sorted(
        breakdown_by_food.values(),
        key=lambda item: (-item["hydration_ml"], item["food_name"].casefold()),
    )

    return {
        "drank_ml": round(drank_ml, 2),
        "food_hydration_ml": round(food_hydration_ml, 2),
        "total_hydration_ml": round(drank_ml + food_hydration_ml, 2),
        "breakdown": breakdown,
    }


def calculate_hydration_summary(
    food_entries: list[FoodEntry],
    foods_by_id: dict[str, Food],
) -> dict[str, float]:
    """Aggregate hydration totals from normal food entries and food metadata."""
    report = calculate_hydration_report(food_entries, foods_by_id)
    return {
        "drank_ml": float(report["drank_ml"]),
        "food_hydration_ml": float(report["food_hydration_ml"]),
        "total_hydration_ml": float(report["total_hydration_ml"]),
    }
