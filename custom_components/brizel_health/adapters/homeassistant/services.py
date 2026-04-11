"""Home Assistant service adapter for Brizel Health."""

from __future__ import annotations

from datetime import UTC, datetime
from inspect import isawaitable
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

from ...application.body.body_profile_use_cases import (
    get_body_profile,
    upsert_body_profile,
)
from ...application.body.body_target_queries import get_body_targets
from ...application.nutrition.add_water import add_water
from ...application.nutrition.daily_summary_queries import get_daily_summary
from ...application.nutrition.food_entry_queries import (
    get_food_entry,
    get_food_entries,
    get_food_entries_for_profile,
    get_food_entries_for_profile_date,
)
from ...application.nutrition.food_entry_use_cases import (
    create_food_entry,
    delete_food_entry,
)
from ...application.nutrition.food_import_use_cases import import_food_from_registry
from ...application.nutrition.food_search_queries import search_foods_from_sources
from ...application.nutrition.food_queries import get_food, get_foods
from ...application.nutrition.food_use_cases import (
    clear_food_compatibility_metadata,
    clear_food_hydration_metadata,
    create_food,
    delete_food,
    update_food,
    update_food_compatibility_metadata,
    update_food_hydration_metadata,
)
from ...application.nutrition.hydration_queries import (
    get_daily_hydration_breakdown,
    get_daily_hydration_report,
    get_daily_hydration_summary,
)
from ...application.nutrition.recent_food_use_cases import get_recent_foods
from ...application.queries.daily_overview_queries import get_daily_overview
from ...application.queries.compatibility_queries import get_food_compatibility
from ...application.users.user_use_cases import (
    create_user,
    delete_user,
    get_all_users,
    get_user,
    resolve_profile_id,
    update_user,
)
from ...const import (
    DATA_BRIZEL,
    DOMAIN,
    SERVICE_ADD_WATER,
    SERVICE_CLEAR_FOOD_COMPATIBILITY_METADATA,
    SERVICE_CLEAR_FOOD_HYDRATION_METADATA,
    SERVICE_CREATE_FOOD,
    SERVICE_CREATE_FOOD_ENTRY,
    SERVICE_CREATE_PROFILE,
    SERVICE_DELETE_FOOD,
    SERVICE_DELETE_FOOD_ENTRY,
    SERVICE_DELETE_PROFILE,
    SERVICE_GET_BODY_PROFILE,
    SERVICE_GET_BODY_TARGETS,
    SERVICE_GET_DAILY_HYDRATION_BREAKDOWN,
    SERVICE_GET_DAILY_HYDRATION_REPORT,
    SERVICE_GET_DAILY_HYDRATION_SUMMARY,
    SERVICE_GET_DAILY_OVERVIEW,
    SERVICE_GET_DAILY_SUMMARY,
    SERVICE_GET_FOOD,
    SERVICE_GET_FOOD_COMPATIBILITY,
    SERVICE_IMPORT_EXTERNAL_FOOD,
    SERVICE_GET_RECENT_FOODS,
    SERVICE_GET_FOOD_ENTRIES,
    SERVICE_GET_FOOD_ENTRIES_FOR_PROFILE,
    SERVICE_GET_FOOD_ENTRIES_FOR_PROFILE_DATE,
    SERVICE_GET_FOOD_ENTRY,
    SERVICE_GET_FOODS,
    SERVICE_GET_PROFILE,
    SERVICE_GET_PROFILES,
    SERVICE_SEARCH_EXTERNAL_FOODS,
    SERVICE_UPDATE_FOOD,
    SERVICE_UPDATE_FOOD_COMPATIBILITY_METADATA,
    SERVICE_UPDATE_FOOD_HYDRATION_METADATA,
    SERVICE_UPDATE_BODY_PROFILE,
    SERVICE_UPDATE_PROFILE,
    SIGNAL_BODY_PROFILE_UPDATED,
    SIGNAL_FOOD_CATALOG_CHANGED,
    SIGNAL_FOOD_ENTRY_CHANGED,
    SIGNAL_PROFILE_CREATED,
    SIGNAL_PROFILE_DELETED,
    SIGNAL_PROFILE_UPDATED,
)
from ...core.users.brizel_user import BrizelUser
from ...core.users.errors import (
    BrizelUserAlreadyExistsError,
    BrizelUserNotFoundError,
    BrizelUserValidationError,
)
from ...domains.body.errors import BrizelBodyProfileValidationError
from ...domains.body.models.dietary_restrictions import DietaryRestrictions
from ...domains.body.models.body_profile import BodyProfile
from ...domains.body.models.body_targets import BodyTargets
from ...domains.nutrition.errors import (
    BrizelFoodAlreadyExistsError,
    BrizelFoodEntryNotFoundError,
    BrizelFoodEntryValidationError,
    BrizelFoodNotFoundError,
    BrizelFoodValidationError,
    BrizelImportedFoodNotFoundError,
    BrizelImportedFoodSourceError,
    BrizelImportedFoodValidationError,
)
from ...domains.nutrition.models.food import Food, HYDRATION_SOURCE_EXPLICIT
from ...domains.nutrition.models.food_compatibility import (
    FOOD_COMPATIBILITY_SOURCE_EXPLICIT,
    FoodCompatibilityMetadata,
)
from ...domains.nutrition.models.food_entry import FoodEntry

_REGISTERED_SERVICES = (
    SERVICE_CREATE_PROFILE,
    SERVICE_GET_PROFILE,
    SERVICE_GET_PROFILES,
    SERVICE_UPDATE_PROFILE,
    SERVICE_DELETE_PROFILE,
    SERVICE_GET_BODY_PROFILE,
    SERVICE_UPDATE_BODY_PROFILE,
    SERVICE_GET_BODY_TARGETS,
    SERVICE_CREATE_FOOD,
    SERVICE_GET_FOOD,
    SERVICE_GET_FOODS,
    SERVICE_UPDATE_FOOD,
    SERVICE_DELETE_FOOD,
    SERVICE_UPDATE_FOOD_HYDRATION_METADATA,
    SERVICE_CLEAR_FOOD_HYDRATION_METADATA,
    SERVICE_UPDATE_FOOD_COMPATIBILITY_METADATA,
    SERVICE_CLEAR_FOOD_COMPATIBILITY_METADATA,
    SERVICE_CREATE_FOOD_ENTRY,
    SERVICE_GET_FOOD_ENTRY,
    SERVICE_GET_FOOD_ENTRIES,
    SERVICE_GET_FOOD_ENTRIES_FOR_PROFILE,
    SERVICE_GET_FOOD_ENTRIES_FOR_PROFILE_DATE,
    SERVICE_DELETE_FOOD_ENTRY,
    SERVICE_GET_DAILY_SUMMARY,
    SERVICE_GET_DAILY_OVERVIEW,
    SERVICE_ADD_WATER,
    SERVICE_GET_DAILY_HYDRATION_SUMMARY,
    SERVICE_GET_DAILY_HYDRATION_BREAKDOWN,
    SERVICE_GET_DAILY_HYDRATION_REPORT,
    SERVICE_GET_FOOD_COMPATIBILITY,
    SERVICE_GET_RECENT_FOODS,
    SERVICE_SEARCH_EXTERNAL_FOODS,
    SERVICE_IMPORT_EXTERNAL_FOOD,
)

_TRANSLATABLE_ERRORS = (
    BrizelUserAlreadyExistsError,
    BrizelUserNotFoundError,
    BrizelUserValidationError,
    BrizelBodyProfileValidationError,
    BrizelFoodAlreadyExistsError,
    BrizelFoodNotFoundError,
    BrizelFoodValidationError,
    BrizelFoodEntryNotFoundError,
    BrizelFoodEntryValidationError,
    BrizelImportedFoodValidationError,
    BrizelImportedFoodNotFoundError,
    BrizelImportedFoodSourceError,
)

_STRING_LIST_VALUE = vol.Any(cv.string, [cv.string])
_EMPTY_SERVICE_SCHEMA = vol.Schema({}, extra=vol.PREVENT_EXTRA)
_PROFILE_ID_SERVICE_SCHEMA = vol.Schema(
    {vol.Required("profile_id"): cv.string},
    extra=vol.PREVENT_EXTRA,
)
_FOOD_ID_SERVICE_SCHEMA = vol.Schema(
    {vol.Required("food_id"): cv.string},
    extra=vol.PREVENT_EXTRA,
)
_FOOD_ENTRY_ID_SERVICE_SCHEMA = vol.Schema(
    {vol.Required("food_entry_id"): cv.string},
    extra=vol.PREVENT_EXTRA,
)
_PROFILE_DATE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("profile_id"): cv.string,
        vol.Required("date"): cv.string,
    },
    extra=vol.PREVENT_EXTRA,
)
_OPTIONAL_PROFILE_ID_SERVICE_SCHEMA = vol.Schema(
    {vol.Optional("profile_id"): cv.string},
    extra=vol.PREVENT_EXTRA,
)
_CREATE_PROFILE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("display_name"): cv.string,
        vol.Optional("linked_ha_user_id"): cv.string,
    },
    extra=vol.PREVENT_EXTRA,
)
_UPDATE_PROFILE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("profile_id"): cv.string,
        vol.Required("display_name"): cv.string,
    },
    extra=vol.PREVENT_EXTRA,
)
_UPDATE_BODY_PROFILE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("profile_id"): cv.string,
        vol.Optional("age_years"): vol.Coerce(int),
        vol.Optional("sex"): cv.string,
        vol.Optional("height_cm"): vol.Coerce(float),
        vol.Optional("weight_kg"): vol.Coerce(float),
        vol.Optional("activity_level"): cv.string,
    },
    extra=vol.PREVENT_EXTRA,
)
_CREATE_OR_UPDATE_FOOD_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
        vol.Required("kcal_per_100g"): vol.Coerce(float),
        vol.Required("protein_per_100g"): vol.Coerce(float),
        vol.Required("carbs_per_100g"): vol.Coerce(float),
        vol.Required("fat_per_100g"): vol.Coerce(float),
        vol.Optional("brand"): cv.string,
        vol.Optional("barcode"): cv.string,
    },
    extra=vol.PREVENT_EXTRA,
)
_CREATE_FOOD_SERVICE_SCHEMA = _CREATE_OR_UPDATE_FOOD_SERVICE_SCHEMA
_UPDATE_FOOD_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("food_id"): cv.string,
        **dict(_CREATE_OR_UPDATE_FOOD_SERVICE_SCHEMA.schema),
    },
    extra=vol.PREVENT_EXTRA,
)
_UPDATE_FOOD_HYDRATION_METADATA_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("food_id"): cv.string,
        vol.Optional("hydration_kind"): cv.string,
        vol.Optional("hydration_ml_per_100g"): vol.Coerce(float),
        vol.Optional("hydration_source"): cv.string,
    },
    extra=vol.PREVENT_EXTRA,
)
_UPDATE_FOOD_COMPATIBILITY_METADATA_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("food_id"): cv.string,
        vol.Optional("ingredients"): _STRING_LIST_VALUE,
        vol.Optional("ingredients_known"): cv.boolean,
        vol.Optional("allergens"): _STRING_LIST_VALUE,
        vol.Optional("allergens_known"): cv.boolean,
        vol.Optional("labels"): _STRING_LIST_VALUE,
        vol.Optional("labels_known"): cv.boolean,
        vol.Optional("compatibility_source"): cv.string,
    },
    extra=vol.PREVENT_EXTRA,
)
_CREATE_FOOD_ENTRY_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional("profile_id"): cv.string,
        vol.Required("food_id"): cv.string,
        vol.Required("grams"): vol.Coerce(float),
        vol.Optional("consumed_at"): cv.string,
        vol.Optional("meal_type"): cv.string,
        vol.Optional("note"): cv.string,
        vol.Optional("source"): cv.string,
    },
    extra=vol.PREVENT_EXTRA,
)
_ADD_WATER_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("profile_id"): cv.string,
        vol.Optional("amount_ml"): vol.Coerce(float),
        vol.Optional("consumed_at"): cv.string,
    },
    extra=vol.PREVENT_EXTRA,
)
_GET_FOOD_COMPATIBILITY_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("food_id"): cv.string,
        vol.Optional("dietary_pattern"): cv.string,
        vol.Optional("allergens"): _STRING_LIST_VALUE,
        vol.Optional("intolerances"): _STRING_LIST_VALUE,
    },
    extra=vol.PREVENT_EXTRA,
)
_GET_RECENT_FOODS_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("profile_id"): cv.string,
        vol.Optional("limit", default=10): vol.Coerce(int),
    },
    extra=vol.PREVENT_EXTRA,
)
_SEARCH_EXTERNAL_FOODS_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("query"): cv.string,
        vol.Optional("source_name"): cv.string,
        vol.Optional("limit", default=10): vol.Coerce(int),
    },
    extra=vol.PREVENT_EXTRA,
)
_IMPORT_EXTERNAL_FOOD_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("source_name"): cv.string,
        vol.Required("source_id"): cv.string,
    },
    extra=vol.PREVENT_EXTRA,
)


def _data(hass: HomeAssistant) -> dict[str, Any]:
    """Return integration runtime data."""
    return hass.data[DATA_BRIZEL]


def _serialize_profile(user: BrizelUser) -> dict[str, object]:
    """Serialize a user into the legacy profile shape."""
    return user.to_dict()


def _serialize_body_profile(body_profile: BodyProfile) -> dict[str, object]:
    """Serialize a body profile for service responses."""
    return body_profile.to_dict()


def _serialize_body_targets(body_targets: BodyTargets) -> dict[str, object]:
    """Serialize body targets for service responses."""
    return body_targets.to_dict()


def _serialize_food(food: Food) -> dict[str, object]:
    """Serialize a food into the legacy shape."""
    return food.to_dict()


def _serialize_food_entry(food_entry: FoodEntry) -> dict[str, object]:
    """Serialize a food entry into the legacy shape."""
    return food_entry.to_dict()


def _normalize_optional_string_list(
    value: Any,
    *,
    field_name: str,
) -> list[str] | None:
    """Normalize a tolerant string-list service input."""
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        return [] if not normalized else [normalized]
    if isinstance(value, (list, tuple, set)):
        values: list[str] = []
        for item in value:
            normalized = str(item).strip()
            if normalized:
                values.append(normalized)
        return values
    raise HomeAssistantError(f"{field_name} must be a string or a list of strings.")


def _build_compatibility_metadata(data: dict[str, Any]) -> FoodCompatibilityMetadata:
    """Build food compatibility metadata from service input."""
    ingredients = _normalize_optional_string_list(
        data.get("ingredients"),
        field_name="ingredients",
    )
    allergens = _normalize_optional_string_list(
        data.get("allergens"),
        field_name="allergens",
    )
    labels = _normalize_optional_string_list(
        data.get("labels"),
        field_name="labels",
    )

    ingredients_known = bool(data.get("ingredients_known", ingredients is not None))
    allergens_known = bool(data.get("allergens_known", allergens is not None))
    labels_known = bool(data.get("labels_known", labels is not None))
    source = data.get("compatibility_source")
    if source is None and (ingredients_known or allergens_known or labels_known):
        source = FOOD_COMPATIBILITY_SOURCE_EXPLICIT

    return FoodCompatibilityMetadata.create(
        ingredients=ingredients,
        ingredients_known=ingredients_known,
        allergens=allergens,
        allergens_known=allergens_known,
        labels=labels,
        labels_known=labels_known,
        source=source,
    )


def _build_dietary_restrictions(data: dict[str, Any]) -> DietaryRestrictions:
    """Build dietary restrictions from service input."""
    try:
        return DietaryRestrictions.create(
            dietary_pattern=data.get("dietary_pattern"),
            allergens=_normalize_optional_string_list(
                data.get("allergens"),
                field_name="allergens",
            ),
            intolerances=_normalize_optional_string_list(
                data.get("intolerances"),
                field_name="intolerances",
            ),
        )
    except ValueError as err:
        raise HomeAssistantError(str(err)) from err


async def _execute(operation: Any) -> Any:
    """Execute one use case and translate known domain/application errors."""
    try:
        result = operation()
        if isawaitable(result):
            return await result
        return result
    except _TRANSLATABLE_ERRORS as err:
        raise HomeAssistantError(str(err)) from err


def _send_profile_signal(hass: HomeAssistant, signal: str, profile: dict[str, object]) -> None:
    """Emit one profile dispatcher signal."""
    async_dispatcher_send(hass, signal, {"profile": profile})


def _send_body_profile_signal(hass: HomeAssistant, profile_id: str) -> None:
    """Emit one body-profile dispatcher signal."""
    async_dispatcher_send(
        hass,
        SIGNAL_BODY_PROFILE_UPDATED,
        {"profile_id": profile_id},
    )


def _send_food_entry_signal(hass: HomeAssistant, profile_id: str) -> None:
    """Emit one food-entry dispatcher signal."""
    async_dispatcher_send(
        hass,
        SIGNAL_FOOD_ENTRY_CHANGED,
        {"profile_id": profile_id},
    )


def _send_food_catalog_signal(hass: HomeAssistant, food_id: str | None = None) -> None:
    """Emit one food-catalog dispatcher signal."""
    async_dispatcher_send(
        hass,
        SIGNAL_FOOD_CATALOG_CHANGED,
        {"food_id": food_id},
    )


def _register_service(
    hass: HomeAssistant,
    service_name: str,
    handler: Any,
    *,
    schema: vol.Schema | None = None,
) -> None:
    """Register one Brizel Health service if needed."""
    if hass.services.has_service(DOMAIN, service_name):
        return
    hass.services.async_register(
        DOMAIN,
        service_name,
        handler,
        schema=schema,
        supports_response=SupportsResponse.OPTIONAL,
    )


async def async_register_services(hass: HomeAssistant) -> None:
    """Register migrated services for Brizel Health."""

    async def resolve_profile_id_from_call(call: ServiceCall) -> str:
        """Resolve one profile ID from explicit input or the active HA user."""
        return await _execute(
            lambda: resolve_profile_id(
                repository=_data(hass)["user_repository"],
                profile_id=call.data.get("profile_id"),
                linked_ha_user_id=getattr(call.context, "user_id", None),
            )
        )

    async def handle_create_profile(call: ServiceCall) -> dict[str, object]:
        user = await _execute(
            lambda: create_user(
                repository=_data(hass)["user_repository"],
                display_name=call.data["display_name"],
                linked_ha_user_id=call.data.get("linked_ha_user_id"),
            )
        )
        profile = _serialize_profile(user)
        _data(hass)["profiles"][profile["profile_id"]] = profile
        _send_profile_signal(hass, SIGNAL_PROFILE_CREATED, profile)
        return {"profile": profile}

    async def handle_get_profile(call: ServiceCall) -> dict[str, object]:
        user = await _execute(
            lambda: get_user(
                repository=_data(hass)["user_repository"],
                user_id=call.data["profile_id"],
            )
        )
        return {"profile": _serialize_profile(user)}

    async def handle_get_profiles(call: ServiceCall) -> dict[str, object]:
        profiles = [
            _serialize_profile(user)
            for user in get_all_users(_data(hass)["user_repository"])
        ]
        return {"profiles": profiles}

    async def handle_update_profile(call: ServiceCall) -> dict[str, object]:
        user = await _execute(
            lambda: update_user(
                repository=_data(hass)["user_repository"],
                user_id=call.data["profile_id"],
                display_name=call.data["display_name"],
            )
        )
        profile = _serialize_profile(user)
        _data(hass)["profiles"][profile["profile_id"]] = profile
        _send_profile_signal(hass, SIGNAL_PROFILE_UPDATED, profile)
        return {"profile": profile}

    async def handle_delete_profile(call: ServiceCall) -> dict[str, object]:
        deleted_user = await _execute(
            lambda: delete_user(
                repository=_data(hass)["user_repository"],
                user_id=call.data["profile_id"],
            )
        )
        deleted_profile = _serialize_profile(deleted_user)
        _data(hass)["profiles"] = _data(hass)["storage"].data.get("profiles", {})
        _send_profile_signal(hass, SIGNAL_PROFILE_DELETED, deleted_profile)
        return {"deleted": True, "profile_id": call.data["profile_id"].strip()}

    async def handle_get_body_profile(call: ServiceCall) -> dict[str, object]:
        body_profile = await _execute(
            lambda: get_body_profile(
                repository=_data(hass)["body_profile_repository"],
                user_repository=_data(hass)["user_repository"],
                profile_id=call.data["profile_id"],
            )
        )
        return {"body_profile": _serialize_body_profile(body_profile)}

    async def handle_update_body_profile(call: ServiceCall) -> dict[str, object]:
        body_profile = await _execute(
            lambda: upsert_body_profile(
                repository=_data(hass)["body_profile_repository"],
                user_repository=_data(hass)["user_repository"],
                profile_id=call.data["profile_id"],
                age_years=call.data.get("age_years"),
                sex=call.data.get("sex"),
                height_cm=call.data.get("height_cm"),
                weight_kg=call.data.get("weight_kg"),
                activity_level=call.data.get("activity_level"),
            )
        )
        _send_body_profile_signal(hass, body_profile.profile_id)
        return {"body_profile": _serialize_body_profile(body_profile)}

    async def handle_get_body_targets(call: ServiceCall) -> dict[str, object]:
        body_targets = await _execute(
            lambda: get_body_targets(
                repository=_data(hass)["body_profile_repository"],
                user_repository=_data(hass)["user_repository"],
                profile_id=call.data["profile_id"],
            )
        )
        return {"targets": _serialize_body_targets(body_targets)}

    async def handle_create_food(call: ServiceCall) -> dict[str, object]:
        food = await _execute(
            lambda: create_food(
                repository=_data(hass)["nutrition_repository"],
                name=call.data["name"],
                brand=call.data.get("brand"),
                barcode=call.data.get("barcode"),
                kcal_per_100g=call.data["kcal_per_100g"],
                protein_per_100g=call.data["protein_per_100g"],
                carbs_per_100g=call.data["carbs_per_100g"],
                fat_per_100g=call.data["fat_per_100g"],
            )
        )
        _send_food_catalog_signal(hass, food.food_id)
        return {"food": _serialize_food(food)}

    async def handle_get_food(call: ServiceCall) -> dict[str, object]:
        food = await _execute(
            lambda: get_food(
                repository=_data(hass)["nutrition_repository"],
                food_id=call.data["food_id"],
            )
        )
        return {"food": _serialize_food(food)}

    async def handle_get_foods(call: ServiceCall) -> dict[str, object]:
        foods = [
            _serialize_food(food)
            for food in get_foods(_data(hass)["nutrition_repository"])
        ]
        return {"foods": foods}

    async def handle_update_food(call: ServiceCall) -> dict[str, object]:
        food = await _execute(
            lambda: update_food(
                repository=_data(hass)["nutrition_repository"],
                food_id=call.data["food_id"],
                name=call.data["name"],
                brand=call.data.get("brand"),
                barcode=call.data.get("barcode"),
                kcal_per_100g=call.data["kcal_per_100g"],
                protein_per_100g=call.data["protein_per_100g"],
                carbs_per_100g=call.data["carbs_per_100g"],
                fat_per_100g=call.data["fat_per_100g"],
            )
        )
        _send_food_catalog_signal(hass, food.food_id)
        return {"food": _serialize_food(food)}

    async def handle_delete_food(call: ServiceCall) -> dict[str, object]:
        food_id = call.data["food_id"].strip()
        await _execute(
            lambda: delete_food(
                repository=_data(hass)["nutrition_repository"],
                food_id=food_id,
            )
        )
        _send_food_catalog_signal(hass, food_id)
        return {"deleted": True, "food_id": food_id}

    async def handle_update_food_hydration_metadata(
        call: ServiceCall,
    ) -> dict[str, object]:
        food = await _execute(
            lambda: update_food_hydration_metadata(
                repository=_data(hass)["nutrition_repository"],
                food_id=call.data["food_id"],
                hydration_kind=call.data.get("hydration_kind"),
                hydration_ml_per_100g=call.data.get("hydration_ml_per_100g"),
                hydration_source=call.data.get(
                    "hydration_source",
                    HYDRATION_SOURCE_EXPLICIT,
                ),
            )
        )
        _send_food_catalog_signal(hass, food.food_id)
        return {"food": _serialize_food(food)}

    async def handle_clear_food_hydration_metadata(
        call: ServiceCall,
    ) -> dict[str, object]:
        food = await _execute(
            lambda: clear_food_hydration_metadata(
                repository=_data(hass)["nutrition_repository"],
                food_id=call.data["food_id"],
            )
        )
        _send_food_catalog_signal(hass, food.food_id)
        return {"food": _serialize_food(food)}

    async def handle_update_food_compatibility_metadata(
        call: ServiceCall,
    ) -> dict[str, object]:
        food = await _execute(
            lambda: update_food_compatibility_metadata(
                repository=_data(hass)["nutrition_repository"],
                food_id=call.data["food_id"],
                compatibility=_build_compatibility_metadata(call.data),
            )
        )
        _send_food_catalog_signal(hass, food.food_id)
        return {"food": _serialize_food(food)}

    async def handle_clear_food_compatibility_metadata(
        call: ServiceCall,
    ) -> dict[str, object]:
        food = await _execute(
            lambda: clear_food_compatibility_metadata(
                repository=_data(hass)["nutrition_repository"],
                food_id=call.data["food_id"],
            )
        )
        _send_food_catalog_signal(hass, food.food_id)
        return {"food": _serialize_food(food)}

    async def handle_create_food_entry(call: ServiceCall) -> dict[str, object]:
        profile_id = await resolve_profile_id_from_call(call)
        food_entry = await _execute(
            lambda: create_food_entry(
                repository=_data(hass)["food_entry_repository"],
                user_repository=_data(hass)["user_repository"],
                food_repository=_data(hass)["nutrition_repository"],
                recent_food_repository=_data(hass).get("recent_food_repository"),
                profile_id=profile_id,
                food_id=call.data["food_id"],
                grams=call.data["grams"],
                consumed_at=call.data.get("consumed_at"),
                meal_type=call.data.get("meal_type"),
                note=call.data.get("note"),
                source=call.data.get("source"),
            )
        )
        _send_food_entry_signal(hass, food_entry.profile_id)
        return {"food_entry": _serialize_food_entry(food_entry)}

    async def handle_get_food_entry(call: ServiceCall) -> dict[str, object]:
        food_entry = await _execute(
            lambda: get_food_entry(
                repository=_data(hass)["food_entry_repository"],
                food_entry_id=call.data["food_entry_id"],
            )
        )
        return {"food_entry": _serialize_food_entry(food_entry)}

    async def handle_get_food_entries(call: ServiceCall) -> dict[str, object]:
        return {
            "food_entries": [
                _serialize_food_entry(food_entry)
                for food_entry in get_food_entries(_data(hass)["food_entry_repository"])
            ]
        }

    async def handle_get_food_entries_for_profile(
        call: ServiceCall,
    ) -> dict[str, object]:
        food_entries = await _execute(
            lambda: get_food_entries_for_profile(
                repository=_data(hass)["food_entry_repository"],
                user_repository=_data(hass)["user_repository"],
                profile_id=call.data["profile_id"],
            )
        )
        return {
            "food_entries": [
                _serialize_food_entry(food_entry) for food_entry in food_entries
            ]
        }

    async def handle_get_food_entries_for_profile_date(
        call: ServiceCall,
    ) -> dict[str, object]:
        food_entries = await _execute(
            lambda: get_food_entries_for_profile_date(
                repository=_data(hass)["food_entry_repository"],
                user_repository=_data(hass)["user_repository"],
                profile_id=call.data["profile_id"],
                date=call.data["date"],
            )
        )
        return {
            "food_entries": [
                _serialize_food_entry(food_entry) for food_entry in food_entries
            ]
        }

    async def handle_delete_food_entry(call: ServiceCall) -> dict[str, object]:
        food_entry_id = call.data["food_entry_id"].strip()
        deleted_entry = await _execute(
            lambda: delete_food_entry(
                repository=_data(hass)["food_entry_repository"],
                food_entry_id=food_entry_id,
            )
        )
        _send_food_entry_signal(hass, deleted_entry.profile_id)
        return {"deleted": True, "food_entry_id": food_entry_id}

    async def handle_get_daily_summary(call: ServiceCall) -> dict[str, object]:
        summary = await _execute(
            lambda: get_daily_summary(
                repository=_data(hass)["food_entry_repository"],
                user_repository=_data(hass)["user_repository"],
                profile_id=call.data["profile_id"],
                date=call.data["date"],
            )
        )
        return {"summary": summary}

    async def handle_get_daily_overview(call: ServiceCall) -> dict[str, object]:
        profile_id = await resolve_profile_id_from_call(call)
        today = datetime.now(UTC).date().isoformat()
        overview = await _execute(
            lambda: get_daily_overview(
                food_entry_repository=_data(hass)["food_entry_repository"],
                body_profile_repository=_data(hass)["body_profile_repository"],
                user_repository=_data(hass)["user_repository"],
                profile_id=profile_id,
                date=today,
            )
        )
        return {
            "profile_id": profile_id,
            "date": today,
            "overview": overview,
        }

    async def handle_add_water(call: ServiceCall) -> dict[str, object]:
        food_entry = await _execute(
            lambda: add_water(
                food_repository=_data(hass)["nutrition_repository"],
                food_entry_repository=_data(hass)["food_entry_repository"],
                user_repository=_data(hass)["user_repository"],
                recent_food_repository=_data(hass).get("recent_food_repository"),
                profile_id=call.data["profile_id"],
                amount_ml=call.data.get("amount_ml", 250),
                consumed_at=call.data.get("consumed_at"),
            )
        )
        _send_food_entry_signal(hass, food_entry.profile_id)
        return {"food_entry": _serialize_food_entry(food_entry)}

    async def handle_get_daily_hydration_summary(
        call: ServiceCall,
    ) -> dict[str, object]:
        hydration = await _execute(
            lambda: get_daily_hydration_summary(
                food_entry_repository=_data(hass)["food_entry_repository"],
                food_repository=_data(hass)["nutrition_repository"],
                user_repository=_data(hass)["user_repository"],
                profile_id=call.data["profile_id"],
                date=call.data["date"],
            )
        )
        return {"hydration": hydration}

    async def handle_get_daily_hydration_breakdown(
        call: ServiceCall,
    ) -> dict[str, object]:
        breakdown = await _execute(
            lambda: get_daily_hydration_breakdown(
                food_entry_repository=_data(hass)["food_entry_repository"],
                food_repository=_data(hass)["nutrition_repository"],
                user_repository=_data(hass)["user_repository"],
                profile_id=call.data["profile_id"],
                date=call.data["date"],
            )
        )
        return {"breakdown": breakdown}

    async def handle_get_daily_hydration_report(
        call: ServiceCall,
    ) -> dict[str, object]:
        hydration = await _execute(
            lambda: get_daily_hydration_report(
                food_entry_repository=_data(hass)["food_entry_repository"],
                food_repository=_data(hass)["nutrition_repository"],
                user_repository=_data(hass)["user_repository"],
                profile_id=call.data["profile_id"],
                date=call.data["date"],
            )
        )
        return {"hydration": hydration}

    async def handle_get_food_compatibility(
        call: ServiceCall,
    ) -> dict[str, object]:
        compatibility = await _execute(
            lambda: get_food_compatibility(
                repository=_data(hass)["nutrition_repository"],
                food_id=call.data["food_id"],
                restrictions=_build_dietary_restrictions(call.data),
            )
        )
        return {"compatibility": compatibility}

    async def handle_get_recent_foods(call: ServiceCall) -> dict[str, object]:
        foods = await _execute(
            lambda: get_recent_foods(
                recent_food_repository=_data(hass)["recent_food_repository"],
                food_repository=_data(hass)["nutrition_repository"],
                profile_id=call.data["profile_id"],
                limit=call.data.get("limit", 10),
            )
        )
        return {"foods": [_serialize_food(food) for food in foods]}

    async def handle_search_external_foods(call: ServiceCall) -> dict[str, object]:
        requested_source_names = None
        if call.data.get("source_name") is not None:
            requested_source_names = [call.data["source_name"]]

        source_results = await _execute(
            lambda: search_foods_from_sources(
                registry=_data(hass)["source_registry"],
                query=call.data["query"],
                requested_source_names=requested_source_names,
                limit_per_source=call.data.get("limit", 10),
            )
        )
        return {
            "source_results": [source_result.to_dict() for source_result in source_results]
        }

    async def handle_import_external_food(call: ServiceCall) -> dict[str, object]:
        food = await _execute(
            lambda: import_food_from_registry(
                registry=_data(hass)["source_registry"],
                food_repository=_data(hass)["nutrition_repository"],
                cache_repository=_data(hass)["imported_food_cache_repository"],
                source_name=call.data["source_name"],
                source_id=call.data["source_id"],
            )
        )
        _send_food_catalog_signal(hass, food.food_id)
        return {
            "source_name": call.data["source_name"].strip().lower(),
            "source_id": call.data["source_id"].strip(),
            "food": _serialize_food(food),
        }

    _register_service(
        hass,
        SERVICE_CREATE_PROFILE,
        handle_create_profile,
        schema=_CREATE_PROFILE_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_GET_PROFILE,
        handle_get_profile,
        schema=_PROFILE_ID_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_GET_PROFILES,
        handle_get_profiles,
        schema=_EMPTY_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_UPDATE_PROFILE,
        handle_update_profile,
        schema=_UPDATE_PROFILE_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_DELETE_PROFILE,
        handle_delete_profile,
        schema=_PROFILE_ID_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_GET_BODY_PROFILE,
        handle_get_body_profile,
        schema=_PROFILE_ID_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_UPDATE_BODY_PROFILE,
        handle_update_body_profile,
        schema=_UPDATE_BODY_PROFILE_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_GET_BODY_TARGETS,
        handle_get_body_targets,
        schema=_PROFILE_ID_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_CREATE_FOOD,
        handle_create_food,
        schema=_CREATE_FOOD_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_GET_FOOD,
        handle_get_food,
        schema=_FOOD_ID_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_GET_FOODS,
        handle_get_foods,
        schema=_EMPTY_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_UPDATE_FOOD,
        handle_update_food,
        schema=_UPDATE_FOOD_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_DELETE_FOOD,
        handle_delete_food,
        schema=_FOOD_ID_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_UPDATE_FOOD_HYDRATION_METADATA,
        handle_update_food_hydration_metadata,
        schema=_UPDATE_FOOD_HYDRATION_METADATA_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_CLEAR_FOOD_HYDRATION_METADATA,
        handle_clear_food_hydration_metadata,
        schema=_FOOD_ID_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_UPDATE_FOOD_COMPATIBILITY_METADATA,
        handle_update_food_compatibility_metadata,
        schema=_UPDATE_FOOD_COMPATIBILITY_METADATA_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_CLEAR_FOOD_COMPATIBILITY_METADATA,
        handle_clear_food_compatibility_metadata,
        schema=_FOOD_ID_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_CREATE_FOOD_ENTRY,
        handle_create_food_entry,
        schema=_CREATE_FOOD_ENTRY_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_GET_FOOD_ENTRY,
        handle_get_food_entry,
        schema=_FOOD_ENTRY_ID_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_GET_FOOD_ENTRIES,
        handle_get_food_entries,
        schema=_EMPTY_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_GET_FOOD_ENTRIES_FOR_PROFILE,
        handle_get_food_entries_for_profile,
        schema=_PROFILE_ID_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_GET_FOOD_ENTRIES_FOR_PROFILE_DATE,
        handle_get_food_entries_for_profile_date,
        schema=_PROFILE_DATE_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_DELETE_FOOD_ENTRY,
        handle_delete_food_entry,
        schema=_FOOD_ENTRY_ID_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_GET_DAILY_SUMMARY,
        handle_get_daily_summary,
        schema=_PROFILE_DATE_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_GET_DAILY_OVERVIEW,
        handle_get_daily_overview,
        schema=_OPTIONAL_PROFILE_ID_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_ADD_WATER,
        handle_add_water,
        schema=_ADD_WATER_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_GET_DAILY_HYDRATION_SUMMARY,
        handle_get_daily_hydration_summary,
        schema=_PROFILE_DATE_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_GET_DAILY_HYDRATION_BREAKDOWN,
        handle_get_daily_hydration_breakdown,
        schema=_PROFILE_DATE_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_GET_DAILY_HYDRATION_REPORT,
        handle_get_daily_hydration_report,
        schema=_PROFILE_DATE_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_GET_FOOD_COMPATIBILITY,
        handle_get_food_compatibility,
        schema=_GET_FOOD_COMPATIBILITY_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_GET_RECENT_FOODS,
        handle_get_recent_foods,
        schema=_GET_RECENT_FOODS_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_SEARCH_EXTERNAL_FOODS,
        handle_search_external_foods,
        schema=_SEARCH_EXTERNAL_FOODS_SERVICE_SCHEMA,
    )
    _register_service(
        hass,
        SERVICE_IMPORT_EXTERNAL_FOOD,
        handle_import_external_food,
        schema=_IMPORT_EXTERNAL_FOOD_SERVICE_SCHEMA,
    )


async def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister all Brizel Health services."""
    for service_name in _REGISTERED_SERVICES:
        if hass.services.has_service(DOMAIN, service_name):
            hass.services.async_remove(DOMAIN, service_name)
