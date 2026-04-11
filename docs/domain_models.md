# Domain Models

## Purpose

This document describes the main domain and closely related application-level models used by the current architecture.

## BrizelUser

### Role

- central user identity shared across modules
- stable reference target for user-scoped and profile-scoped data

### Location

- `core/users/brizel_user.py`

### Important Fields

- `user_id`
- `display_name`
- `linked_ha_user_id`
- `created_at`

### Relationships

- referenced by `FoodEntry.profile_id`
- used by profile-scoped queries and recent-food tracking
- can optionally link one Home Assistant user through `linked_ha_user_id`
- does not own nutrition, hydration, or compatibility business data

### Design Decision

- user identity stays in `core/`
- the optional Home Assistant user link stays with profile identity, not with nutrition data
- body and nutrition data are layered on top of that identity instead of being embedded into the user model

## Food

### Role

- reusable food catalog definition
- source of nutrition values for new food entries
- carrier of optional hydration and compatibility metadata

### Location

- `domains/nutrition/models/food.py`

### Important Fields

- `food_id`
- `name`
- `brand`
- `barcode`
- `kcal_per_100g`
- `protein_per_100g`
- `carbs_per_100g`
- `fat_per_100g`
- `created_at`

### Hydration Fields

- `hydration_kind`
  - `drink`
  - `food`
- `hydration_ml_per_100g`
- `hydration_source`
  - `internal`
  - `explicit`
  - `imported`

### Compatibility Field

- `compatibility`
  - optional `FoodCompatibilityMetadata`

### Relationships

- referenced by `FoodEntry.food_id`
- resolved during hydration and compatibility queries
- linked from imported-food cache entries through `food_id`

### Design Decision

- `Food` remains the single catalog entity for nutrition-related product features
- hydration and compatibility extend `Food` instead of introducing parallel nutrition entities

## FoodEntry

### Role

- historical record of consumption
- immutable nutrition snapshot derived from one food at one time

### Location

- `domains/nutrition/models/food_entry.py`

### Important Fields

- `food_entry_id`
- `profile_id`
- `food_id`
- `food_name`
- `food_brand`
- `grams`
- `meal_type`
- `note`
- `source`
- `consumed_at`
- `kcal`
- `protein`
- `carbs`
- `fat`
- `created_at`

### Relationships

- belongs to one profile through `profile_id`
- references one food catalog entry through `food_id`
- is the source input for daily summary and hydration queries

### Design Decision

- `FoodEntry` stores calculated nutrition values at creation time
- hydration and compatibility are read from the current `Food` state, not duplicated onto the entry

## Internal Water Food

### Role

- canonical internal food for the water shortcut
- prevents a parallel water tracking model

### Location

- `domains/nutrition/services/water.py`

### Canonical Fields

- `food_id = "brizel_internal_water"`
- `name = "Water"`
- `brand = None`
- `barcode = None`
- macros all `0`
- `hydration_kind = "drink"`
- `hydration_ml_per_100g = 100`
- `hydration_source = "internal"`

### Relationships

- created or normalized by `application/nutrition/add_water.py`
- consumed through normal `FoodEntry` creation
- removed through the same application module by deleting the newest exact matching water entry
- protected from normal catalog update/delete and direct metadata edits

### Design Decision

- water is modeled as a protected `Food`, not as a separate product subsystem

## Hydration Metadata

### Role

- trusted hydration layer on top of the food catalog

### Location

- fields on `Food`
- calculations in `domains/nutrition/services/hydration.py`

### Important Fields

- `hydration_kind`
- `hydration_ml_per_100g`
- `hydration_source`

### Relationships

- consumed by hydration summary and hydration breakdown queries
- can come from:
  - internal definitions
  - explicit internal enrichment
  - imported metadata

### Design Decision

- missing hydration metadata is treated as unknown
- raw imported water values are not automatically promoted into trusted internal hydration without classification

## DietaryRestrictions

### Role

- body-owned user restrictions used for food evaluation

### Location

- `domains/body/models/dietary_restrictions.py`

### Important Fields

- `dietary_pattern`
  - currently `vegan` or `vegetarian`
- `allergens`
- `intolerances`

### Relationships

- owned by Body
- passed into Nutrition compatibility evaluation through the application layer

### Design Decision

- restrictions belong to Body, not Nutrition
- Nutrition evaluates foods against these rules but does not own them

## BodyProfile

### Role

- optional per-profile body input data owned by Body
- source model for current target calculation

### Location

- `domains/body/models/body_profile.py`

### Important Fields

- `profile_id`
- `age_years`
- `sex`
- `height_cm`
- `weight_kg`
- `activity_level`

### Relationships

- linked to one `BrizelUser` through `profile_id`
- consumed by body target queries
- stored separately from user identity in `body.profiles`

### Design Decision

- body data is not embedded into `BrizelUser`
- all fields are optional so incomplete data can remain honestly incomplete
- `weight_kg` is included because it is required for the current conservative target logic

## BodyTargets

### Role

- derived read model for daily target ranges and their recommended sensor values

### Location

- `domains/body/models/body_targets.py`

### Important Fields

- `profile_id`
- `target_daily_kcal`
- `target_daily_protein`
- `target_daily_fat`
- `missing_fields`
- `unsupported_reasons`
- `target_ranges`

### Target Range Shape

- `minimum`
- `recommended`
- `maximum`
- `method`
- `formula`
- `required_fields`
- `missing_fields`
- `unsupported_reasons`
- `inputs`

### Relationships

- derived from one `BodyProfile`
- returned by body target queries
- exposed through Home Assistant services and target sensors
- combined with daily summary data by target-status queries for frontend-facing `under` / `within` / `over` states

### Design Decision

- targets are computed on demand instead of being persisted
- the top-level target fields remain the recommended center value for service and sensor compatibility
- the richer `target_ranges` structure carries the visible range and transparency metadata
- the Home Assistant adapter can render each range as separate `Low`, `Recommended`, and `High` sensors without moving target logic into the adapter
- interpreted status sensors are intentionally derived in a separate query layer instead of being embedded into this model
- missing or unsupported values stay explicit instead of being guessed

## FoodCompatibilityMetadata

### Role

- trusted food metadata relevant for compatibility evaluation

### Location

- `domains/nutrition/models/food_compatibility.py`

### Important Fields

- `ingredients`
- `ingredients_known`
- `allergens`
- `allergens_known`
- `labels`
- `labels_known`
- `source`
  - `explicit`
  - `imported`

### Relationships

- stored on `Food`
- consumed by compatibility evaluation

### Design Decision

- compatibility metadata is advisory only
- unknown sections stay unknown instead of being guessed

## FoodCompatibilityAssessment

### Role

- structured read model returned by compatibility evaluation

### Location

- `domains/nutrition/services/food_compatibility.py`

### Important Fields

- `food_id`
- `food_name`
- `food_brand`
- `status`
  - `compatible`
  - `incompatible`
  - `unknown`
- `compatibility_source`
- `incompatible_reasons`
- `unknown_reasons`

### Relationships

- derived from one `Food` plus body-owned restriction inputs
- not persisted as its own entity

### Design Decision

- reason objects are structured for future UI use
- the result informs but never blocks nutrition write flows

## ImportedFoodData

### Role

- source-neutral handoff model between external source adapters and Brizel-internal import logic

### Location

- `domains/nutrition/models/imported_food_data.py`

### Important Fields

- `source_name`
- `source_id`
- `name`
- `brand`
- `barcode`
- `kcal_per_100g`
- `protein_per_100g`
- `carbs_per_100g`
- `fat_per_100g`
- `ingredients`
- `ingredients_known`
- `allergens`
- `allergens_known`
- `labels`
- `labels_known`
- `hydration_kind`
- `hydration_ml_per_100g`
- `market_country_codes`
- `market_region_codes`
- `fetched_at`
- `source_updated_at`

### Relationships

- returned by source adapters
- consumed by import use cases and enrichment
- stored inside imported-food cache entries

### Design Decision

- this is not the final internal `Food`
- it preserves unknowns explicitly
- it allows raw hydration measurements without forcing a trusted hydration classification

## ImportedFoodCacheEntry

### Role

- cached snapshot of imported source data linked to one internal food

### Location

- `domains/nutrition/models/imported_food_cache_entry.py`

### Important Fields

- `source_name`
- `source_id`
- `food_id`
- `imported_food`
- `last_synced_at`

### Relationships

- links one source reference to one internal `Food`
- stored in `nutrition.imported_food_cache`

### Design Decision

- imported source snapshots stay separate from the food catalog
- this avoids mixing raw external payload snapshots with the final internal catalog model

## RecentFoodReference

### Role

- profile-scoped reference to recently used foods

### Location

- `domains/nutrition/models/recent_food_reference.py`

### Important Fields

- `food_id`
- `last_used_at`

### Relationships

- grouped per profile in `nutrition.recent_foods_by_profile`
- resolved back into `Food` objects by recent-food queries

### Design Decision

- only references are stored
- no food data is duplicated in the recent-food feature

## FoodSourceDefinition

### Role

- application-level definition of an available external food source

### Location

- `application/nutrition/source_registry.py`

### Important Fields

- `name`
- `adapter`
- `priority`
- `enabled`

### Relationships

- stored in `FoodSourceRegistry`
- consumed by source selection and import orchestration

### Design Decision

- this is not a domain entity
- it is documented here because it is part of the stable import architecture surface for developers
