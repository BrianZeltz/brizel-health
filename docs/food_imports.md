# Food Imports

## Purpose

This document describes the current architecture for external food sources, source-neutral import data, enrichment, cache handling, recent foods, and source orchestration.

## Scope

### Covered Here

- external food source adapters
- source-neutral imported-food model
- enrichment behavior
- import cache
- recent foods per profile
- source registry and source orchestration

### Explicitly Not Covered Here

- Home Assistant configuration or UI
- multi-source merge into one canonical food
- automatic classification of unknown foods

## External Source Adapters

### General Rule

- every external source has its own adapter
- each adapter knows only its own payload format
- adapters return `ImportedFoodData`
- adapters do not return final internal `Food` objects

### Current Sources

- `open_food_facts`
- `usda`

### Current Live State

- `usda`
  - live search
  - live detail lookup
  - API key required
- `open_food_facts`
  - live lookup by barcode/source ID
  - live search intentionally not enabled yet

## Source Differences

### Open Food Facts

### Main Strengths

- ingredients
- allergens
- labels
- packaged product identity

### Typical Weaknesses

- source data may be incomplete
- sections may be present or missing independently
- hydration is not trusted by default

### Current Mapping Notes

- OFF is the primary source for:
  - ingredients
  - allergens
  - labels
- `ingredients[].text` is preferred
- `ingredients_text` is used as fallback
- `allergens_tags` and `labels_tags` have the language prefix removed

### USDA FoodData Central

### Main Strengths

- energy values
- water values
- strong nutrient structure

### Typical Weaknesses

- no ingredients
- no allergens
- no labels
- no reliable drink-vs-food classification for hydration

### Current Mapping Notes

- USDA is the primary source for:
  - `kcal_per_100g`
  - raw water values as `hydration_ml_per_100g`
- raw water values stay in the import model until a trusted hydration classification exists
- the first live Brizel search/import rollout is USDA-first

## ImportedFoodData

### Role

- neutral handoff model between source adapters and Brizel

### Important Fields

- source identity:
  - `source_name`
  - `source_id`
- timestamps:
  - `fetched_at`
  - `source_updated_at`
- basic identity:
  - `name`
  - `brand`
  - `barcode`
- nutrition:
  - `kcal_per_100g`
  - `protein_per_100g`
  - `carbs_per_100g`
  - `fat_per_100g`
- compatibility-relevant metadata:
  - `ingredients`
  - `ingredients_known`
  - `allergens`
  - `allergens_known`
  - `labels`
  - `labels_known`
- hydration signals:
  - `hydration_kind`
  - `hydration_ml_per_100g`
- market context:
  - `market_country_codes`
  - `market_region_codes`

### Unknown Handling

- missing source sections remain unknown
- unknown is represented through:
  - `None`
  - empty tuples
  - `*_known = False`

## Enrichment

### Role

- enrichment converts source-neutral import data into Brizel-internal metadata candidates

### Current Enrichment Areas

- hydration
- compatibility

### Hydration Rule

- hydration metadata is only promoted into internal `Food` when the basis is trusted
- a raw water amount alone is not enough
- this prevents false confidence for imported foods

### Compatibility Rule

- known ingredients/allergens/labels can become `FoodCompatibilityMetadata`
- missing sections remain unknown
- compatibility remains advisory-only after import as well

## Import Cache

### Role

- stores imported source snapshots separately from the internal food catalog

### Current Structure

- bucket: `nutrition.imported_food_cache`
- hierarchy:
  - `source_name`
  - `source_id`

### Stored Data

- source identity
- linked `food_id`
- imported-food snapshot
- `last_synced_at`

### Design Decision

- external snapshots stay separate from the final internal food entity
- this keeps source data, normalization, and internal model concerns separated

## Recent Foods

### Role

- stores per-profile references to recently used foods

### Current Structure

- bucket: `nutrition.recent_foods_by_profile`

### Stored Data

- `food_id`
- `last_used_at`

### Design Decision

- recent foods are profile-scoped
- only references are stored
- food data is not duplicated
- current write attachment points are:
  - normal food-entry creation
  - water shortcut entry creation

## Source Registry

### Role

- central application-level registry of available external sources

### Main Elements

- `FoodSourceDefinition`
- `FoodSourceRegistry`

### Current Source Definition Fields

- `name`
- `adapter`
- `priority`
- `enabled`

### Why It Exists

- keeps source availability and selection out of adapters
- prepares later runtime configuration without adding framework dependencies now

### Current Home Assistant Preparation

- the Home Assistant adapter now builds a runtime source registry during entry setup
- current runtime settings support:
  - `enabled`
  - `priority`
  - source-specific credentials such as the USDA API key
- these values are read from config-entry options when present
- the current source-management UI is intentionally still small

## Live Search

### Current Flow

1. The caller provides a query and one or more requested sources.
2. `application/nutrition/food_search_queries.py` selects enabled sources.
3. Each adapter returns `ExternalFoodSearchResult` items instead of directly importing data.
4. Results stay grouped per source with isolated source errors.

### Result Data

- `source_name`
- `source_id`
- `name`
- `brand`
- `barcode`
- optional nutrition hints
- optional hydration hint when already present in source data

### Design Decision

- search does not mutate the internal food catalog
- explicit import is still a separate step

## Source Selection

### Current Strategy

- all enabled requested sources are selected
- sources are returned in priority order

### Why This Is Intentionally Simple

- selection is centralized already
- more advanced strategies can be added later without changing adapter contracts

## Import Orchestration

### Current Flow

1. Build one or more source requests.
2. Ask the registry for selected sources.
3. For each selected source:
   - call the source adapter
   - get `ImportedFoodData`
   - run the existing single-source import flow
4. Return one result per source.

### Result Shape

- `source_name`
- `source_id`
- `status`
- `food_id`
- `error`

### Failure Behavior

- one source failing does not block the others
- results stay per source
- there is no cross-source merge in this phase

## Current Stable Decisions

- one adapter per source
- one neutral import model
- one separate neutral search-result model
- explicit enrichment step
- separate import cache
- profile-scoped recent foods
- central source registry
- simple source selection
- per-source orchestration results
- live USDA search/detail support with API-key configuration through Home Assistant options
- live Open Food Facts lookup-only support by barcode/source ID

## Deliberately Deferred

- broader end-user source management beyond the current small options-flow surface
- cross-source merge into one final food
- automatic compatibility inference
- automatic hydration classification of unknown imported foods
- live Open Food Facts search
