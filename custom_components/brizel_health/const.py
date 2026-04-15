"""Constants for the Brizel Health integration."""

DOMAIN = "brizel_health"
NAME = "Brizel Health"

DATA_BRIZEL = DOMAIN
FRONTEND_DIRECTORY = "frontend"
FRONTEND_RESOURCE_BASE_URL = "/api/brizel_health/frontend"
FRONTEND_CARD_FILES = (
    "brizel-health-app-card.js",
    "brizel-health-hero-card.js",
    "brizel-nutrition-card.js",
    "brizel-macro-card.js",
    "brizel-hydration-card.js",
    "brizel-food-logger-card.js",
)
FRONTEND_RESOURCE_URLS = tuple(
    f"{FRONTEND_RESOURCE_BASE_URL}/{filename}" for filename in FRONTEND_CARD_FILES
)

STORAGE_VERSION = 1
STORAGE_KEY = "brizel_health.storage"

SERVICE_CREATE_PROFILE = "create_profile"
SERVICE_GET_PROFILE = "get_profile"
SERVICE_GET_PROFILES = "get_profiles"
SERVICE_UPDATE_PROFILE = "update_profile"
SERVICE_DELETE_PROFILE = "delete_profile"

SERVICE_CREATE_FOOD = "create_food"
SERVICE_GET_FOOD = "get_food"
SERVICE_GET_FOODS = "get_foods"
SERVICE_UPDATE_FOOD = "update_food"
SERVICE_DELETE_FOOD = "delete_food"
SERVICE_UPDATE_FOOD_HYDRATION_METADATA = "update_food_hydration_metadata"
SERVICE_CLEAR_FOOD_HYDRATION_METADATA = "clear_food_hydration_metadata"
SERVICE_UPDATE_FOOD_COMPATIBILITY_METADATA = "update_food_compatibility_metadata"
SERVICE_CLEAR_FOOD_COMPATIBILITY_METADATA = "clear_food_compatibility_metadata"

SERVICE_CREATE_FOOD_ENTRY = "create_food_entry"
SERVICE_GET_FOOD_ENTRY = "get_food_entry"
SERVICE_GET_FOOD_ENTRIES = "get_food_entries"
SERVICE_GET_FOOD_ENTRIES_FOR_PROFILE = "get_food_entries_for_profile"
SERVICE_GET_FOOD_ENTRIES_FOR_PROFILE_DATE = "get_food_entries_for_profile_date"
SERVICE_DELETE_FOOD_ENTRY = "delete_food_entry"
SERVICE_GET_DAILY_SUMMARY = "get_daily_summary"
SERVICE_GET_DAILY_OVERVIEW = "get_daily_overview"
SERVICE_ADD_WATER = "add_water"
SERVICE_REMOVE_WATER = "remove_water"
SERVICE_GET_DAILY_HYDRATION_SUMMARY = "get_daily_hydration_summary"
SERVICE_GET_DAILY_HYDRATION_BREAKDOWN = "get_daily_hydration_breakdown"
SERVICE_GET_DAILY_HYDRATION_REPORT = "get_daily_hydration_report"
SERVICE_GET_FOOD_COMPATIBILITY = "get_food_compatibility"
SERVICE_GET_RECENT_FOODS = "get_recent_foods"
SERVICE_SEARCH_EXTERNAL_FOODS = "search_external_foods"
SERVICE_LOOKUP_EXTERNAL_FOOD_BY_BARCODE = "lookup_external_food_by_barcode"
SERVICE_GET_EXTERNAL_FOOD_DETAIL = "get_external_food_detail"
SERVICE_IMPORT_EXTERNAL_FOOD = "import_external_food"
SERVICE_LOG_EXTERNAL_FOOD_ENTRY = "log_external_food_entry"
SERVICE_GET_BODY_PROFILE = "get_body_profile"
SERVICE_UPDATE_BODY_PROFILE = "update_body_profile"
SERVICE_GET_BODY_TARGETS = "get_body_targets"

SIGNAL_PROFILE_CREATED = "brizel_health_profile_created"
SIGNAL_PROFILE_UPDATED = "brizel_health_profile_updated"
SIGNAL_PROFILE_DELETED = "brizel_health_profile_deleted"
SIGNAL_BODY_PROFILE_UPDATED = "brizel_health_body_profile_updated"
SIGNAL_FOOD_ENTRY_CHANGED = "brizel_health_food_entry_changed"
SIGNAL_FOOD_CATALOG_CHANGED = "brizel_health_food_catalog_changed"
SIGNAL_PROFILE_RESYNC = "brizel_health_profile_resync"

PLATFORMS = ["sensor", "button"]
