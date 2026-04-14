# Architecture

## Purpose

This document describes the current internal architecture of `brizel_health` from a developer perspective.

## Layer Structure

### Domain

- Location: `custom_components/brizel_health/domains/`
- Responsibility:
  - domain models
  - validation rules
  - pure calculations and classification logic
  - source-neutral import concepts
- Examples:
  - `domains/body/models/body_profile.py`
  - `domains/body/models/dietary_restrictions.py`
  - `domains/body/services/targets.py`
  - `domains/nutrition/models/food.py`
  - `domains/nutrition/models/food_entry.py`
  - `domains/nutrition/models/imported_food_data.py`
  - `domains/nutrition/services/water.py`
  - `domains/nutrition/services/hydration.py`
  - `domains/nutrition/services/food_compatibility.py`
  - `domains/nutrition/services/import_enrichment.py`

### Application

- Location: `custom_components/brizel_health/application/`
- Responsibility:
  - use cases
  - queries
  - orchestration across repositories, modules, and source adapters
  - source registry and source selection
- Examples:
  - `application/body/body_profile_use_cases.py`
  - `application/body/body_target_queries.py`
  - `application/users/user_use_cases.py`
  - `application/nutrition/food_use_cases.py`
  - `application/nutrition/food_entry_use_cases.py`
  - `application/nutrition/hydration_queries.py`
  - `application/queries/compatibility_queries.py`
  - `application/nutrition/food_import_use_cases.py`
  - `application/nutrition/source_registry.py`
  - `application/nutrition/import_orchestration.py`

### Infrastructure

- Location: `custom_components/brizel_health/infrastructure/`
- Responsibility:
  - repository implementations
  - persistence details
  - storage access
  - external-source adapter implementations
- Examples:
  - `infrastructure/repositories/ha_user_repository.py`
  - `infrastructure/repositories/ha_nutrition_repository.py`
  - `infrastructure/repositories/ha_imported_food_cache_repository.py`
  - `infrastructure/repositories/ha_recent_food_repository.py`
  - `infrastructure/storage/store_manager.py`
  - `infrastructure/external_food_sources/open_food_facts_adapter.py`
  - `infrastructure/external_food_sources/usda_adapter.py`

### Adapter

- Location: `custom_components/brizel_health/adapters/`
- Responsibility:
  - framework-specific integration
  - input/output translation
  - response shaping for the host environment
- Current state:
  - Home Assistant adapter exists under `adapters/homeassistant/`
  - config entry setup and unload are active
  - profile management is exposed through an options flow
  - body data management is exposed through the same options-flow surface
  - the service layer exposes stable nutrition, import, and profile flows
  - profile sensors, profile-scoped target-range sensors, target-status sensors, and profile-scoped water shortcut buttons are active
  - Home Assistant frontend custom cards live under `custom_components/brizel_health/frontend/`
  - the integration serves those packaged frontend files through `/api/brizel_health/frontend/`
  - the Hero, Nutrition, Macro, Hydration, and Food Logger cards consume stable Home Assistant services and selective entity overrides
  - Home Assistant still remains an adapter only; business logic stays outside it

## Role Of Core

### What Core Owns

- shared foundations
- central user identity
- cross-module interfaces
- basic shared helpers

### What Core Does Not Own

- no nutrition business rules
- no body-specific rules
- no module-to-module orchestration
- no central "everything service"

## Role Of Application

### Main Responsibility

- Application is the orchestration layer.
- It coordinates:
  - domain models
  - repositories
  - external food source adapters
  - cross-module flows

### Cross-Module Example

- Body owns `DietaryRestrictions`.
- Body also owns per-profile body data and target calculation inputs.
- Nutrition owns food compatibility metadata and evaluation logic.
- The cross-module flow lives in `application/queries/compatibility_queries.py`.
- This keeps Body and Nutrition separate while still allowing controlled collaboration.

## Body-Specific Architecture

### Body Data Stays Outside Core Users

- `BrizelUser` stays the central identity only.
- `BrizelUser` may optionally carry `linked_ha_user_id` for adapter-side profile resolution.
- `BodyProfile` references that identity through `profile_id`.
- This keeps user identity, body data, and nutrition data separate.

### Targets Are Derived, Not Stored Separately

- `BodyProfile` stores the captured input data.
- `BodyTargets` is a derived read model returned by the target domain service.
- Each target can expose:
  - `minimum`
  - `recommended`
  - `maximum`
- Home Assistant sensors and services read the derived targets instead of persisting a second target bucket.

### Conservative Calculation Rules

- current target logic is intentionally small and transparent
- missing data stays missing
- calorie targets are currently adult-only maintenance estimates with a small Brizel range around the calculated center
- protein and fat targets are simple Brizel heuristic ranges based on body weight and activity level
- no medical or pseudo-precise specialty logic is embedded into the adapter layer

## Nutrition-Specific Architecture

### Food And FoodEntry Stay Separate

- `Food` is the reusable catalog definition.
- `FoodEntry` is the historical consumption event.
- Hydration, water, imports, and recent-food handling build on top of this separation.

### Water Builds On Existing Models

- Water is a canonical internal `Food`.
- Water intake is a normal `FoodEntry`.
- Water removal uses the normal `FoodEntry` delete path for the newest matching shortcut-sized entry.
- There is no parallel water persistence model.

### Compatibility Is Advisory Only

- Compatibility evaluates foods against body-owned restrictions.
- Compatibility never blocks food creation or food entry creation.
- The backend returns structured assessment data for future UI use.

## Import Architecture

### Source Adapter Per External Source

- Each external source has its own adapter.
- Adapters know source-specific payload structure only.
- Adapters do not construct the final internal `Food` directly.

### Source-Neutral Import Model

- Adapters return `ImportedFoodData`.
- `ImportedFoodData` is the handoff point between source-specific parsing and Brizel-internal logic.
- It carries:
  - source identity
  - fetched/source timestamps
  - optional nutrition values
  - optional ingredients/allergens/labels
  - optional raw hydration signals
  - market/country information

### Enrichment Layer

- Enrichment runs on `ImportedFoodData`.
- It prepares internal metadata for:
  - hydration
  - compatibility
- It does not guess unknown data.
- It does not blindly override trusted internal metadata.

### Import Orchestration

- Source definitions are managed centrally in `application/nutrition/source_registry.py`.
- Source selection lives in `application/nutrition/import_selection.py`.
- Multi-source orchestration lives in `application/nutrition/import_orchestration.py`.
- Existing single-source import behavior remains in `application/nutrition/food_import_use_cases.py`.
- Search orchestration lives in `application/nutrition/food_search_queries.py`.

### Cache And Recent Foods

- imported source snapshots are cached separately from the internal food catalog
- profile-specific recent foods store only `food_id` references
- recent foods are now updated automatically from the normal food-entry flow when a recent-food repository is available
- neither feature introduces a parallel nutrition domain model

### Runtime Source Configuration Preparation

- the Home Assistant adapter builds a runtime `FoodSourceRegistry`
- the registry currently reads:
  - `enabled`
  - `priority`
  - source-specific API credentials such as the USDA API key
  from config-entry options when present
- this prepares later source configuration without moving source logic into the domain layer
- the current UI remains intentionally small and focused on stable source settings only

## Persistent Data Shape

### Current Store Buckets

- `profiles`
- `body.profiles`
- `nutrition.foods`
- `nutrition.food_entries`
- `nutrition.imported_food_cache`
- `nutrition.recent_foods_by_profile`

### Architectural Meaning

- `profiles` stores central user identity
- `body.profiles` stores optional per-profile body input data
- `nutrition.foods` stores the reusable food catalog
- `nutrition.food_entries` stores historical consumption events
- `nutrition.imported_food_cache` stores source snapshots plus source-to-food linkage
- `nutrition.recent_foods_by_profile` stores per-profile recent-food references only

## Design Principles

### Small Safe Slices

- changes are introduced incrementally
- behavior is preserved when possible
- new structures are added in narrow, testable steps

### No Quick Hacks

- shortcuts must still respect layer boundaries
- temporary logic should not be hidden inside adapters or repositories

### No Direct Storage Manipulation Outside Repositories

- storage shape is controlled in infrastructure
- domain and application code must not mutate storage buckets directly

### Unknown Is A Legitimate State

- missing source data stays unknown
- compatibility may return `unknown`
- hydration stays unset unless the system has a reliable basis

### Extend Existing Models Before Adding Parallel Systems

- water extends `Food` and `FoodEntry`
- hydration extends `Food`
- compatibility extends `Food`
- imported source data is cached separately, but final behavior still flows into existing nutrition models

### Domain Stays Free Of Source And Framework Logic

- no Home Assistant imports in domain
- no external source payload parsing in domain
- no adapter-specific response shaping in domain or application

## Current Stable Areas

- user/profile management
- Home Assistant config entry lifecycle
- Home Assistant options-flow profile management
- Home Assistant options-flow HA-user-to-profile linking
- Home Assistant options-flow body-data management
- Home Assistant service layer for stable profile and nutrition flows
- Home Assistant food-entry creation with optional profile auto-resolution from `call.context.user_id`
- Home Assistant per-profile nutrition and target sensors
- Home Assistant per-profile add/remove water buttons
- Home Assistant food logger card and service-backed dialog flow
- body profile persistence
- conservative body target-range calculation
- food catalog
- food entries
- daily nutrition summary
- water shortcut
- hydration summary and breakdown
- advisory-only compatibility evaluation
- source-neutral import model
- source adapters for OFF, USDA, and BLS
- source adapter for BLS backed by a bundled local snapshot
- live USDA search and detail lookup through infrastructure HTTP clients
- live Open Food Facts search and detail lookup
- multi-source search orchestration with locale-aware ranking and recent-food boosts
- import cache
- recent foods per profile
- source registry and multi-source import orchestration
- packaged Lovelace card resources and automatic storage-mode resource registration
- small frontend regression tests through Vitest/jsdom

## Currently Deferred

- richer Home Assistant source configuration UI
- multi-source merge into one food record
- automatic classification of unknown foods
