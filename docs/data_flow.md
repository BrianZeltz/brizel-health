# Data Flow

## Purpose

This document summarizes the main internal flows in the current architecture.

## User / Profile Flow

### Description

- Central user identity is managed independently from nutrition data.

### Involved Layers

- Core
- Application
- Infrastructure
- Adapter when called from Home Assistant

### Flow

1. A caller invokes a user/profile use case.
2. `application/users/user_use_cases.py` validates input and coordinates the flow.
3. `core/users/brizel_user.py` provides the central user model and validation.
4. Optional `linked_ha_user_id` can associate one Home Assistant user with one Brizel profile.
5. The user repository persists or loads the user.
6. Infrastructure stores the user in `profiles`.

## Home Assistant Profile Management Flow

### Description

- Home Assistant profile management is handled through the options flow, not through entities or buttons.

### Involved Layers

- Adapter
- Application
- Core
- Infrastructure

### Flow

1. A Home Assistant user opens the Brizel Health integration options.
2. The options flow offers profile actions:
   - add
   - edit
   - delete
   - link Home Assistant user
3. The flow loads profile choices through the existing user use cases.
4. The selected application use case is executed.
5. Dispatcher signals refresh profile-backed entities after the change.

## Body Profile Flow

### Description

- Body data is stored per profile and stays separate from nutrition data.

### Involved Layers

- Domain
- Application
- Infrastructure
- Adapter when edited from Home Assistant

### Flow

1. A caller requests body data for one profile or replaces the stored body data.
2. `application/body/body_profile_use_cases.py` validates the profile through the existing user repository.
3. `domains/body/models/body_profile.py` validates the body inputs.
4. The body profile repository stores or loads the body profile in `body.profiles`.

## Body Target Flow

### Description

- Daily target ranges are derived from the current body profile, not stored in a separate target bucket.

### Involved Layers

- Domain
- Application
- Infrastructure
- Adapter when exposed through Home Assistant services or sensors

### Flow

1. A caller requests targets for one profile.
2. `application/body/body_target_queries.py` validates the profile and loads the current `BodyProfile`.
3. `domains/body/services/targets.py` calculates conservative targets.
4. Each target is evaluated independently and can expose:
   - `minimum`
   - `recommended`
   - `maximum`
5. Missing inputs stay target-specific and unsupported cases remain explicit.
6. The resulting `BodyTargets` read model is returned to the caller.

## Food Catalog Flow

### Description

- The food catalog stores reusable foods plus optional hydration and compatibility metadata.

### Involved Layers

- Domain
- Application
- Infrastructure
- Adapter when externally triggered

### Flow

1. A caller requests create, read, update, delete, or metadata enrichment for a food.
2. `application/nutrition/food_use_cases.py` or `food_queries.py` handles orchestration.
3. `domains/nutrition/models/food.py` validates names, macros, hydration metadata, and compatibility metadata.
4. The food repository persists the serialized food into `nutrition.foods`.

## FoodEntry Flow

### Description

- A `FoodEntry` records that a profile consumed a specific amount of a specific food.

### Involved Layers

- Domain
- Application
- Infrastructure
- Adapter when externally triggered

### Flow

1. The caller provides `food_id`, consumed amount, and either:
   - an explicit `profile_id`
   - or an active linked Home Assistant user context
2. The Home Assistant adapter can resolve the profile from `call.context.user_id` through the existing user application flow.
3. `application/nutrition/food_entry_use_cases.py` validates IDs and repository access.
4. The user repository confirms the resolved profile exists.
5. The food repository loads the catalog food.
6. `domains/nutrition/models/food_entry.py` creates the entry and calculates nutrition values from the catalog food.
7. The food entry repository stores the entry in `nutrition.food_entries`.
8. If a recent-food repository is available, the application flow updates the per-profile recent-food list.

## Daily Summary Flow

### Description

- Daily summary aggregates nutrition totals per profile and date.

### Involved Layers

- Application
- Domain
- Infrastructure

### Flow

1. `application/nutrition/daily_summary_queries.py` requests entries for one profile and one date.
2. `application/nutrition/food_entry_queries.py` validates and filters the entry list.
3. `domains/nutrition/services/daily_summary.py` aggregates `kcal`, `protein`, `carbs`, and `fat`.
4. The query returns a summary read model.

## Water Shortcut Flow

### Description

- Water is tracked as a normal food and a normal food entry.

### Involved Layers

- Domain
- Application
- Infrastructure

### Flow

1. The caller invokes `application/nutrition/add_water.py`.
2. The use case ensures the canonical internal water food exists.
3. Missing or inconsistent internal water is created or normalized.
4. The use case delegates to the normal food-entry creation flow.
5. Water intake is stored as a normal `FoodEntry`.
6. The same recent-food update path can run for the internal water food.

## Water Removal Flow

### Description

- The reverse water shortcut removes the newest matching shortcut-sized water entry without manipulating summaries directly.

### Involved Layers

- Domain
- Application
- Infrastructure

### Flow

1. The caller invokes `application/nutrition/add_water.py` through `remove_water`.
2. The use case resolves the canonical internal water food.
3. Existing food entries for the profile are filtered to exact water matches for the requested amount.
4. The newest matching entry is deleted through the normal food-entry delete use case.
5. If no exact matching entry exists, the flow returns a clean error instead of guessing or partially subtracting water.

## Home Assistant Body Management Flow

### Description

- Home Assistant uses the existing options flow to manage body data per profile.

### Involved Layers

- Adapter
- Application
- Domain
- Infrastructure

### Flow

1. A Home Assistant user opens `Options` for the Brizel Health integration.
2. The options flow offers a body-data action in addition to profile actions.
3. The user selects a profile.
4. The flow loads current body data through the body-profile use case.
5. The flow submits the edited values back through the body-profile upsert use case.
6. A body-profile dispatcher signal refreshes the related target sensors.

## Home Assistant Target Sensor Flow

### Description

- Target sensors expose both derived range points and interpreted daily status per profile next to the existing daily nutrition sensors.
- Each supported target keeps:
  - three range-point sensors:
    - `Low`
    - `Recommended`
    - `High`
  - one interpreted status sensor:
    - `under`
    - `within`
    - `over`
    - `unknown`

### Involved Layers

- Adapter
- Application
- Domain
- Infrastructure

### Flow

1. The Home Assistant sensor platform creates profile-scoped sensors.
2. Each target-range sensor calls the existing body target query for its profile.
3. Each target-status sensor calls the existing target-status query for its profile and current date.
4. The adapter builds three profile-scoped sensors per target range:
   - low
   - recommended
   - high
5. Each of those sensors reads the already calculated range point from `BodyTargets`.
6. Status sensors expose:
  - `consumed`
  - `target_min`
  - `target_recommended`
  - `target_max`
  - `remaining_to_min`
  - `remaining_to_max`
  - `over_amount`
  - `display_text`
7. Range sensors also expose:
  - `target_min`
  - `target_recommended`
  - `target_max`
  - `target_range_text`
8. Missing fields, formulas, inputs, and unsupported reasons are exposed as sensor attributes.
9. When body data or food entries change, dispatcher signals refresh only the affected profile sensors.

## Home Assistant Frontend Card Flow

### Description

- Custom Lovelace cards live in `custom_components/brizel_health/frontend/`.
- The cards remain frontend-only consumers of stable Home Assistant services or sensor state.

### Involved Layers

- Adapter frontend
- Adapter backend
- Application

### Flow

1. Home Assistant loads the Brizel Health card resources from `/api/brizel_health/frontend/`.
2. `brizel-health-hero-card` resolves either:
   - an explicit `profile_id`
   - or the active Home Assistant user through the stable overview service
3. The Hero card calls the existing `get_daily_overview` service and renders the returned kcal, protein, and fat status data.
4. `brizel-nutrition-card`, `brizel-macro-card`, and `brizel-hydration-card` read stable HA sensor state through `hass.states[...]`.
5. No business logic is moved into the cards; they only visualize already derived backend data.

## Hydration Summary And Breakdown Flow

### Description

- Hydration is calculated from stored foods and food entries.

### Involved Layers

- Domain
- Application
- Infrastructure

### Flow

1. A hydration query requests one profile and one date.
2. `application/nutrition/hydration_queries.py` loads:
   - matching food entries
   - current food catalog entries
3. `domains/nutrition/services/hydration.py` resolves the relevant food for each entry.
4. Foods without trusted hydration metadata are skipped.
5. Contributions are split into:
   - `drank_ml`
   - `food_hydration_ml`
   - `total_hydration_ml`
6. Optional breakdown items are returned per contributing food.

## Compatibility Evaluation Flow

### Description

- Compatibility evaluates foods against body-owned dietary restrictions, but does not block documentation.

### Involved Layers

- Domain
- Application
- Core and Body for shared user/restriction concepts

### Flow

1. A caller provides a `food_id` and body-owned `DietaryRestrictions`.
2. `application/queries/compatibility_queries.py` loads the food from Nutrition.
3. The same query passes normalized restriction values into Nutrition compatibility evaluation.
4. `domains/nutrition/services/food_compatibility.py` returns:
   - `compatible`
   - `incompatible`
   - `unknown`
5. Structured reason objects are returned for later UI use.
6. No write path is blocked by this result.

## Imported Food Single-Source Flow

### Description

- A single source adapter can import one source item into the internal food catalog.

### Involved Layers

- Infrastructure
- Application
- Domain

### Flow

1. A source adapter fetches one source-specific payload.
2. The adapter maps it into `ImportedFoodData`.
3. `application/nutrition/food_import_use_cases.py` calls domain enrichment.
4. `domains/nutrition/services/import_enrichment.py` prepares hydration and compatibility metadata conservatively.
5. The use case either:
   - creates a new internal `Food`
   - or updates an existing `Food`
6. The import cache stores the source snapshot and the linked `food_id`.

## External Food Search Flow

### Description

- Search is separate from import.
- Search returns source-neutral search results without mutating the internal food catalog.

### Involved Layers

- Application
- Infrastructure

### Flow

1. A caller provides a text query and one or more requested sources.
2. `application/nutrition/food_search_queries.py` builds a small search-intelligence layer around the raw query.
3. Optional profile and Home Assistant hints can be turned into a locale-aware search context.
4. The query layer selects enabled sources from the registry.
5. Each selected source adapter runs its own search implementation.
6. Each adapter returns `ExternalFoodSearchResult` items with:
   - `source_name`
   - `source_id`
   - `name`
   - optional brand and nutrition hints
7. Search failures are isolated per source instead of blocking the whole search run.
8. Results are plausibility-filtered, deduplicated, and ranked into one merged list.

## Multi-Source Import Flow

### Description

- Multiple external sources can be orchestrated in one application-level import run.

### Involved Layers

- Application
- Infrastructure
- Domain through the existing import flow

### Flow

1. The caller builds one or more `FoodSourceImportRequest` values.
2. `application/nutrition/import_orchestration.py` asks the registry for selected sources.
3. `application/nutrition/import_selection.py` currently returns all enabled requested sources in priority order.
4. For each selected source:
   - the source adapter is invoked
   - the existing single-source import flow is used
   - a per-source result is collected
5. If one source fails, the other sources continue.
6. Results are returned per source without multi-source merge.

## Import Cache Flow

### Description

- Imported source snapshots are cached separately from the internal food catalog.

### Involved Layers

- Domain
- Application
- Infrastructure

### Flow

1. A source adapter produces `ImportedFoodData`.
2. The application import flow resolves or creates the linked internal `Food`.
3. `ImportedFoodCacheEntry` is created with:
   - source identity
   - linked `food_id`
   - imported payload snapshot
   - sync timestamp
4. The cache repository stores the entry in `nutrition.imported_food_cache`.

## Recent Foods Flow

### Description

- Recent foods track profile-specific food references without duplicating food data.

### Involved Layers

- Domain
- Application
- Infrastructure

### Flow

1. A caller invokes `remember_recent_food`.
2. The application layer validates the profile and food reference.
3. The recent-food repository updates the profile-scoped list.
4. Only `food_id` references plus timestamps are stored.
5. `get_recent_foods` resolves those references back into current food catalog entries.
6. Current write attachment points are:
   - normal food-entry creation
   - water shortcut creation

## Source Registry Flow

### Description

- Source registry centralizes available external food sources and prepares later runtime configuration.

### Involved Layers

- Application

### Flow

1. The application registers one or more `FoodSourceDefinition` values.
2. Each definition provides:
   - source name
   - adapter instance
   - priority
   - enabled flag
3. Import selection reads the enabled sources.
4. Import orchestration uses the registry instead of hard-coding source adapters.

## Home Assistant Runtime Source Preparation Flow

### Description

- Home Assistant currently prepares source runtime configuration without exposing a full source-management UI.

### Involved Layers

- Adapter
- Application

### Flow

1. A config entry is set up or reloaded.
2. The Home Assistant bootstrap reads config-entry options.
3. The adapter builds a runtime `FoodSourceRegistry`.
4. Known sources are registered with:
   - enabled flag
   - priority
   - source-specific configuration such as the USDA API key
5. Application search and import flows can then consume the prepared registry.
