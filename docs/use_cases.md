# Use Cases And Queries

## Purpose

This document gives a structured overview of the main application entry points.

## User / Profile

### Location

- `application/users/user_use_cases.py`

### Main Entry Points

- `create_user`
- `get_user`
- `get_user_by_linked_ha_user_id`
- `get_all_users`
- `resolve_profile_id`
- `update_user`
- `update_user_linked_ha_user_id`
- `delete_user`

### Responsibility

- central user identity management
- profile-name uniqueness
- uniqueness of optional HA-user links
- resolution of one Brizel profile from one linked Home Assistant user
- orchestration between the user model and user repository

## Body Profile

### Location

- `application/body/body_profile_use_cases.py`

### Main Entry Points

- `get_body_profile`
- `upsert_body_profile`

### Responsibility

- validate that the related profile exists
- load or replace the current per-profile body data
- keep body data separate from core user identity

## Body Targets

### Location

- `application/body/body_target_queries.py`
- `application/body/body_target_status_queries.py`

### Main Entry Point

- `get_body_targets`
- `get_kcal_target_status`
- `get_protein_target_status`
- `get_fat_target_status`

### Responsibility

- load the current body profile for one user/profile
- delegate target calculation to the body domain service
- return a derived read model with:
  - target-specific missing fields
  - target-specific unsupported reasons
  - range metadata for kcal, protein, and fat
- provide the single source of truth that the Home Assistant adapter can fan out into `Low`, `Recommended`, and `High` target sensors
- provide interpreted daily status values by combining consumed daily totals with target ranges
- return UX-facing status data for:
  - `under`
  - `within`
  - `over`
  - `unknown`

## Daily Overview

### Location

- `application/queries/daily_overview_queries.py`

### Main Entry Point

- `get_daily_overview`

### Responsibility

- combine kcal, protein, and fat target-status queries into one frontend-friendly overview payload
- keep the Hero-card-specific aggregation in the application layer instead of the frontend
- provide one stable read shape for Home Assistant dashboards and future UI surfaces

## Food Catalog

### Location

- `application/nutrition/food_use_cases.py`
- `application/nutrition/food_queries.py`

### Main Entry Points

- `create_food`
- `update_food`
- `delete_food`
- `get_food`
- `get_foods`

### Metadata Enrichment Entry Points

- `update_food_hydration_metadata`
- `clear_food_hydration_metadata`
- `update_food_compatibility_metadata`
- `clear_food_compatibility_metadata`

### Responsibility

- food catalog write and read orchestration
- uniqueness checks
- protection of the internal water food
- controlled metadata enrichment without changing the surrounding architecture

## FoodEntry

### Location

- `application/nutrition/food_entry_use_cases.py`
- `application/nutrition/food_entry_queries.py`

### Main Entry Points

- `create_food_entry`
- `delete_food_entry`
- `get_food_entry`
- `get_food_entries`
- `get_food_entries_for_profile`
- `get_food_entries_for_profile_date`

### Responsibility

- profile validation through the user repository
- optional profile resolution from a linked Home Assistant user in adapter-driven flows
- food lookup through the food repository
- delegation of nutrition calculation to the domain model
- entry filtering by profile and date
- optional recent-food updates after a successful write

## Daily Summary

### Location

- `application/nutrition/daily_summary_queries.py`

### Main Entry Point

- `get_daily_summary`

### Responsibility

- orchestrates daily nutrition aggregation
- delegates entry filtering to food-entry queries
- delegates math to the daily summary domain service

## Water

### Location

- `application/nutrition/add_water.py`

### Main Entry Point

- `add_water`
- `remove_water`

### Responsibility

- ensures the canonical internal water food exists
- normalizes the internal water food if needed
- delegates final persistence to the normal food-entry flow
- can update the profile recent-food list through that same flow
- removes water conservatively by deleting only the newest exact matching shortcut-sized entry

## Hydration

### Location

- `application/nutrition/hydration_queries.py`

### Main Entry Points

- `get_daily_hydration_summary`
- `get_daily_hydration_report`
- `get_daily_hydration_breakdown`

### Responsibility

- loads daily food-entry context
- loads current food catalog data
- delegates hydration aggregation and breakdown to the domain service

## Compatibility

### Location

- `application/queries/compatibility_queries.py`
- `application/nutrition/compatibility_queries.py`

### Main Entry Point

- `get_food_compatibility`

### Responsibility

- cross-module orchestration between:
  - Body restrictions
  - Nutrition food metadata
  - Nutrition compatibility evaluation
- returns advisory-only results for later UI or adapter consumption

## Imported Food Single-Source Flow

### Location

- `application/nutrition/food_import_use_cases.py`

### Main Entry Points

- `fetch_imported_food`
- `import_food_from_source`
- `import_food_from_registry`
- `get_cached_imported_food`

### Responsibility

- call one source adapter
- receive `ImportedFoodData`
- run domain enrichment
- create or update one internal `Food`
- persist source snapshots in the import cache

## Food Logging UI Flow

### Location

- `application/nutrition/food_logging_queries.py`
- `application/nutrition/food_logging_use_cases.py`

### Main Entry Points

- `get_external_food_detail_from_registry`
- `get_supported_logging_units`
- `get_default_logging_unit`
- `log_external_food_entry_from_registry`

### Responsibility

- load one source-specific external food detail payload through the registry
- keep the logger UI on stable, source-neutral detail data
- validate conservative v1 logging input
- import the selected source item if needed
- create the final `FoodEntry` through the normal nutrition write path
- preserve profile-aware recent-food updates through that same flow

## External Food Search

### Location

- `application/nutrition/food_search_queries.py`
- `application/nutrition/search_context.py`
- `application/nutrition/search_intelligence.py`

### Main Entry Points

- `FoodSourceSearchResult`
- `search_foods_from_sources`

### Responsibility

- search one or more enabled sources through the registry
- keep search separate from import
- return source-neutral search results plus per-source errors when needed
- build locale-aware search context from profile and Home Assistant hints when available
- apply controlled query normalization and expansion for German/English search quality
- merge, plausibility-filter, deduplicate, and rank one combined result list

## Source Registry And Selection

### Location

- `application/nutrition/source_registry.py`
- `application/nutrition/import_selection.py`

### Main Entry Points

- `FoodSourceRegistry.register_source`
- `FoodSourceRegistry.get_source`
- `FoodSourceRegistry.list_sources`
- `FoodSourceRegistry.get_enabled_sources`
- `select_import_sources`

### Responsibility

- central registry of available source adapters
- stable place for source enable/disable, priority handling, and source-scoped configuration
- keeps source selection out of adapter code and out of domain code
- supports dynamic ranking with bounded manual priority override

## Import Orchestration

### Location

- `application/nutrition/import_orchestration.py`

### Main Entry Points

- `FoodSourceImportRequest`
- `FoodSourceImportResult`
- `import_food_from_sources`

### Responsibility

- orchestrates imports across multiple registered sources
- isolates failures per source
- returns per-source result objects
- intentionally does not merge multiple source results into one food in this phase

## Recent Foods

### Location

- `application/nutrition/recent_food_use_cases.py`

### Main Entry Points

- `remember_recent_food`
- `get_recent_foods`

### Responsibility

- stores per-profile recent-food references
- resolves recent references back into food catalog entries
- avoids duplicating food data
- now acts as a write-side follow-up to normal food-entry creation when configured

## Repository Touchpoints

### User Repository

- used by:
  - user use cases
  - food-entry creation
  - profile-scoped queries
  - daily summary and hydration queries

### Food Repository

- used by:
  - food catalog use cases and queries
  - food-entry creation
  - water shortcut
  - hydration queries
  - compatibility evaluation
  - import flows
  - recent-food resolution

### FoodEntry Repository

- used by:
  - food-entry use cases and queries
  - daily summary
  - hydration queries

### Imported Food Cache Repository

- used by:
  - single-source import flows
  - multi-source import orchestration through the existing single-source flow
  - cached imported-food reads

### Recent Food Repository

- used by:
  - recent-food write flow
  - recent-food read flow

## Notes For Future Adapter Work

- adapters should call these use cases and queries directly
- adapters should not reimplement compatibility, hydration, or import orchestration logic
- adapters should not calculate body targets directly; they should call the body target query
- source enable/disable and priority settings are already shaped to be configurable later
- the current Home Assistant adapter already prepares runtime source definitions from config-entry options, including the USDA API key
- the current Home Assistant adapter also passes profile-aware search context and recent-food hints into the search layer
