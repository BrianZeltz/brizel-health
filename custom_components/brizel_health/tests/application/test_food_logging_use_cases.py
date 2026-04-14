"""Tests for Food Logging UI queries and use cases."""

from __future__ import annotations

import pytest

from custom_components.brizel_health.application.nutrition.food_logging_queries import (
    get_default_logging_unit,
    get_external_food_detail_from_registry,
    get_supported_logging_units,
)
from custom_components.brizel_health.application.nutrition.food_logging_use_cases import (
    log_external_food_entry_from_registry,
)
from custom_components.brizel_health.application.nutrition.source_registry import (
    FoodSourceRegistry,
)
from custom_components.brizel_health.core.users.brizel_user import BrizelUser
from custom_components.brizel_health.core.users.errors import BrizelUserNotFoundError
from custom_components.brizel_health.domains.nutrition.errors import (
    BrizelFoodNotFoundError,
    BrizelImportedFoodValidationError,
)
from custom_components.brizel_health.domains.nutrition.models.food import Food
from custom_components.brizel_health.domains.nutrition.models.food_entry import FoodEntry
from custom_components.brizel_health.domains.nutrition.models.imported_food_cache_entry import (
    ImportedFoodCacheEntry,
)
from custom_components.brizel_health.domains.nutrition.models.imported_food_data import (
    ImportedFoodData,
)
from custom_components.brizel_health.domains.nutrition.models.recent_food_reference import (
    RecentFoodReference,
)


class InMemoryFoodRepository:
    """Simple in-memory food repository for food-logging tests."""

    def __init__(self, foods: list[Food] | None = None) -> None:
        self._foods = {food.food_id: food for food in foods or []}

    async def add(self, food: Food) -> Food:
        self._foods[food.food_id] = food
        return food

    async def update(self, food: Food) -> Food:
        self._foods[food.food_id] = food
        return food

    async def delete(self, food_id: str) -> None:
        del self._foods[food_id]

    def get_food_by_id(self, food_id: str) -> Food:
        food = self._foods.get(food_id)
        if food is None:
            raise BrizelFoodNotFoundError(f"No food found for food_id '{food_id}'.")
        return food

    def get_all_foods(self) -> list[Food]:
        return list(self._foods.values())

    def food_name_exists(
        self,
        name: str,
        brand: str | None,
        exclude_food_id: str | None = None,
    ) -> bool:
        return False

    def barcode_exists(
        self,
        barcode: str | None,
        exclude_food_id: str | None = None,
    ) -> bool:
        return False


class InMemoryImportedFoodCacheRepository:
    """Simple in-memory imported-food cache for food-logging tests."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], ImportedFoodCacheEntry] = {}

    def get_by_source_ref(
        self,
        source_name: str,
        source_id: str,
    ) -> ImportedFoodCacheEntry | None:
        return self._entries.get((source_name.strip().lower(), source_id.strip()))

    async def upsert(
        self,
        cache_entry: ImportedFoodCacheEntry,
    ) -> ImportedFoodCacheEntry:
        self._entries[(cache_entry.source_name, cache_entry.source_id)] = cache_entry
        return cache_entry


class InMemoryFoodEntryRepository:
    """Simple in-memory food-entry repository for food-logging tests."""

    def __init__(self) -> None:
        self._food_entries: dict[str, FoodEntry] = {}

    async def add(self, food_entry: FoodEntry) -> FoodEntry:
        self._food_entries[food_entry.food_entry_id] = food_entry
        return food_entry

    async def delete(self, food_entry_id: str) -> FoodEntry:
        return self._food_entries.pop(food_entry_id)

    def get_all_food_entries(self) -> list[FoodEntry]:
        return list(self._food_entries.values())


class InMemoryUserRepository:
    """Simple user repository for food-logging tests."""

    def __init__(self, users: list[BrizelUser]) -> None:
        self._users = {user.user_id: user for user in users}

    async def add(self, user: BrizelUser) -> BrizelUser:
        self._users[user.user_id] = user
        return user

    async def update(self, user: BrizelUser) -> BrizelUser:
        self._users[user.user_id] = user
        return user

    async def delete(self, user_id: str) -> BrizelUser:
        return self._users.pop(user_id)

    def get_by_id(self, user_id: str) -> BrizelUser:
        user = self._users.get(user_id)
        if user is None:
            raise BrizelUserNotFoundError(
                f"No profile found for profile_id '{user_id}'."
            )
        return user

    def get_all(self) -> list[BrizelUser]:
        return list(self._users.values())

    def display_name_exists(
        self,
        display_name: str,
        exclude_user_id: str | None = None,
    ) -> bool:
        return False


class InMemoryRecentFoodRepository:
    """Simple recent-food repository for food-logging tests."""

    def __init__(self) -> None:
        self._entries: dict[str, list[RecentFoodReference]] = {}

    async def touch(
        self,
        profile_id: str,
        food_id: str,
        used_at: str | None = None,
        max_items: int = 20,
    ) -> list[RecentFoodReference]:
        reference = RecentFoodReference.create(food_id, used_at)
        updated = [reference] + [
            item
            for item in self._entries.get(profile_id, [])
            if item.food_id != reference.food_id
        ]
        updated = updated[:max_items]
        self._entries[profile_id] = updated
        return updated

    def get_recent(
        self,
        profile_id: str,
        limit: int = 10,
    ) -> list[RecentFoodReference]:
        return self._entries.get(profile_id, [])[:limit]


class FixtureExternalFoodSourceAdapter:
    """Simple fixture-backed adapter for food-logging tests."""

    def __init__(
        self,
        source_name: str,
        imported_foods: list[ImportedFoodData] | None = None,
    ) -> None:
        self.source_name = source_name
        self._foods = {food.source_id: food for food in imported_foods or []}

    async def fetch_food_by_id(self, source_id: str) -> ImportedFoodData | None:
        return self._foods.get(source_id.strip())

    async def search_foods(self, query: str, limit: int = 10) -> list[object]:
        return []


def _build_imported_food() -> ImportedFoodData:
    return ImportedFoodData.create(
        source_name="usda",
        source_id="454004",
        name="Apple, raw",
        brand=None,
        barcode=None,
        kcal_per_100g=52,
        protein_per_100g=0.3,
        carbs_per_100g=14,
        fat_per_100g=0.2,
        hydration_ml_per_100g=85.6,
        fetched_at="2026-04-12T09:00:00+00:00",
    )


def _build_off_imported_food() -> ImportedFoodData:
    return ImportedFoodData.create(
        source_name="open_food_facts",
        source_id="3017624010701",
        name="Nutella",
        brand="Ferrero",
        barcode="3017624010701",
        kcal_per_100g=539,
        protein_per_100g=6.3,
        carbs_per_100g=57.5,
        fat_per_100g=30.9,
        fetched_at="2026-04-12T09:05:00+00:00",
    )


def _build_bls_imported_food() -> ImportedFoodData:
    return ImportedFoodData.create(
        source_name="bls",
        source_id="BLS123",
        name="Gouda",
        brand=None,
        barcode=None,
        kcal_per_100g=356,
        protein_per_100g=24.0,
        carbs_per_100g=0.1,
        fat_per_100g=28.0,
        hydration_ml_per_100g=42.0,
        fetched_at="2026-04-12T09:06:00+00:00",
    )


@pytest.mark.asyncio
async def test_get_external_food_detail_from_registry_returns_imported_food() -> None:
    """Food logging detail query should return one enabled-source payload."""
    registry = FoodSourceRegistry()
    imported_food = _build_imported_food()
    registry.register_source(
        "usda",
        FixtureExternalFoodSourceAdapter("usda", [imported_food]),
        enabled=True,
    )

    result = await get_external_food_detail_from_registry(
        registry,
        source_name="usda",
        source_id="454004",
    )

    assert result.source_name == "usda"
    assert result.source_id == "454004"
    assert result.kcal_per_100g == 52
    assert get_supported_logging_units(result) == ("g",)
    assert get_default_logging_unit(result) == "g"


@pytest.mark.asyncio
async def test_get_external_food_detail_from_registry_rejects_disabled_source() -> None:
    """Disabled external sources should fail cleanly for the logging detail flow."""
    registry = FoodSourceRegistry()
    registry.register_source(
        "usda",
        FixtureExternalFoodSourceAdapter("usda", [_build_imported_food()]),
        enabled=False,
    )

    with pytest.raises(BrizelImportedFoodValidationError):
        await get_external_food_detail_from_registry(
            registry,
            source_name="usda",
            source_id="454004",
        )


@pytest.mark.asyncio
async def test_log_external_food_entry_from_registry_imports_then_creates_entry() -> None:
    """Logging one external food should import it and immediately create a diary entry."""
    registry = FoodSourceRegistry()
    imported_food = _build_imported_food()
    registry.register_source(
        "usda",
        FixtureExternalFoodSourceAdapter("usda", [imported_food]),
        enabled=True,
    )
    food_repository = InMemoryFoodRepository()
    cache_repository = InMemoryImportedFoodCacheRepository()
    food_entry_repository = InMemoryFoodEntryRepository()
    user_repository = InMemoryUserRepository(
        [
            BrizelUser(
                user_id="profile-1",
                display_name="Brian",
                linked_ha_user_id="ha-user-1",
                created_at="2026-04-12T08:00:00+00:00",
            )
        ]
    )
    recent_food_repository = InMemoryRecentFoodRepository()

    result = await log_external_food_entry_from_registry(
        registry=registry,
        food_repository=food_repository,
        cache_repository=cache_repository,
        food_entry_repository=food_entry_repository,
        user_repository=user_repository,
        recent_food_repository=recent_food_repository,
        profile_id="profile-1",
        source_name="usda",
        source_id="454004",
        amount=175,
        unit="g",
        consumed_at="2026-04-12T10:15:00+00:00",
    )

    assert result.food.name == "Apple, raw"
    assert result.unit == "g"
    assert result.logged_grams == 175
    assert result.food_entry.profile_id == "profile-1"
    assert result.food_entry.food_id == result.food.food_id
    assert result.food_entry.grams == 175
    assert cache_repository.get_by_source_ref("usda", "454004") is not None
    assert recent_food_repository.get_recent("profile-1")[0].food_id == result.food.food_id


@pytest.mark.asyncio
async def test_log_external_food_entry_from_registry_rejects_invalid_amount() -> None:
    """Food logging should reject zero or negative amounts."""
    registry = FoodSourceRegistry()
    registry.register_source(
        "usda",
        FixtureExternalFoodSourceAdapter("usda", [_build_imported_food()]),
        enabled=True,
    )

    with pytest.raises(BrizelImportedFoodValidationError):
        await log_external_food_entry_from_registry(
            registry=registry,
            food_repository=InMemoryFoodRepository(),
            cache_repository=InMemoryImportedFoodCacheRepository(),
            food_entry_repository=InMemoryFoodEntryRepository(),
            user_repository=InMemoryUserRepository(
                [
                    BrizelUser(
                        user_id="profile-1",
                        display_name="Brian",
                        linked_ha_user_id="ha-user-1",
                        created_at="2026-04-12T08:00:00+00:00",
                    )
                ]
            ),
            recent_food_repository=None,
            profile_id="profile-1",
            source_name="usda",
            source_id="454004",
            amount=0,
        )


@pytest.mark.asyncio
async def test_log_external_food_entry_from_registry_rejects_unsupported_unit() -> None:
    """Food logging should fail clearly when the requested unit is not supported yet."""
    registry = FoodSourceRegistry()
    registry.register_source(
        "usda",
        FixtureExternalFoodSourceAdapter("usda", [_build_imported_food()]),
        enabled=True,
    )

    with pytest.raises(BrizelImportedFoodValidationError):
        await log_external_food_entry_from_registry(
            registry=registry,
            food_repository=InMemoryFoodRepository(),
            cache_repository=InMemoryImportedFoodCacheRepository(),
            food_entry_repository=InMemoryFoodEntryRepository(),
            user_repository=InMemoryUserRepository(
                [
                    BrizelUser(
                        user_id="profile-1",
                        display_name="Brian",
                        linked_ha_user_id="ha-user-1",
                        created_at="2026-04-12T08:00:00+00:00",
                    )
                ]
            ),
            recent_food_repository=None,
            profile_id="profile-1",
            source_name="usda",
            source_id="454004",
            amount=125,
            unit="ml",
        )


@pytest.mark.asyncio
async def test_log_external_food_entry_from_registry_supports_open_food_facts_results() -> None:
    """The logging flow should work the same way for OFF-backed results."""
    registry = FoodSourceRegistry()
    registry.register_source(
        "open_food_facts",
        FixtureExternalFoodSourceAdapter("open_food_facts", [_build_off_imported_food()]),
        enabled=True,
    )

    result = await log_external_food_entry_from_registry(
        registry=registry,
        food_repository=InMemoryFoodRepository(),
        cache_repository=InMemoryImportedFoodCacheRepository(),
        food_entry_repository=InMemoryFoodEntryRepository(),
        user_repository=InMemoryUserRepository(
            [
                BrizelUser(
                    user_id="profile-1",
                    display_name="Brian",
                    linked_ha_user_id="ha-user-1",
                    created_at="2026-04-12T08:00:00+00:00",
                )
            ]
        ),
        recent_food_repository=None,
        profile_id="profile-1",
        source_name="open_food_facts",
        source_id="3017624010701",
        amount=40,
        unit="g",
    )

    assert result.food.name == "Nutella"
    assert result.food.barcode == "3017624010701"
    assert result.food_entry.profile_id == "profile-1"
    assert result.food_entry.grams == 40


@pytest.mark.asyncio
async def test_log_external_food_entry_from_registry_supports_bls_results() -> None:
    """The logging flow should also work for the local BLS source."""
    registry = FoodSourceRegistry()
    registry.register_source(
        "bls",
        FixtureExternalFoodSourceAdapter("bls", [_build_bls_imported_food()]),
        enabled=True,
    )

    result = await log_external_food_entry_from_registry(
        registry=registry,
        food_repository=InMemoryFoodRepository(),
        cache_repository=InMemoryImportedFoodCacheRepository(),
        food_entry_repository=InMemoryFoodEntryRepository(),
        user_repository=InMemoryUserRepository(
            [
                BrizelUser(
                    user_id="profile-1",
                    display_name="Brian",
                    linked_ha_user_id="ha-user-1",
                    created_at="2026-04-12T08:00:00+00:00",
                )
            ]
        ),
        recent_food_repository=None,
        profile_id="profile-1",
        source_name="bls",
        source_id="BLS123",
        amount=50,
        unit="g",
    )

    assert result.food.name == "Gouda"
    assert result.food_entry.profile_id == "profile-1"
    assert result.food_entry.grams == 50
