# Food Imports

## Purpose

This document describes the current architecture for external food sources, source-neutral import data, recent foods, search orchestration, and source-aware ranking.

## Scope

### Covered Here

- external food source adapters
- source-neutral imported-food model
- import cache
- recent foods per profile
- source registry and runtime source configuration
- multi-source search and source-aware ranking

### Explicitly Not Covered Here

- Home Assistant card layout details
- cross-source merge into one canonical food
- meal types, favorites, or barcode camera UX

## External Source Adapters

### General Rule

- every external source has its own adapter
- each adapter knows only its own payload format
- adapters return source-neutral models
- adapters do not return final internal `Food` objects directly

### Current Sources

- `open_food_facts`
- `usda`
- `bls`

### Current Runtime State

- `open_food_facts`
  - live search
  - live detail lookup by source ID / barcode
  - especially useful for branded and packaged products
- `usda`
  - live search
  - live detail lookup
  - API key required
  - especially useful for generic foods in more US-oriented contexts
- `bls`
  - bundled local snapshot search
  - bundled local snapshot detail lookup
  - especially useful for many generic German foods

## Source Differences

### Open Food Facts

#### Main Strengths

- branded and packaged product identity
- ingredients
- allergens
- labels
- market and retailer hints

#### Typical Weaknesses

- source data may be incomplete
- sections may be present or missing independently
- hydration is not trusted by default

#### Current Mapping Notes

- OFF is a key source for:
  - branded products
  - packaged products
  - market-aware product ranking
- `ingredients[].text` is preferred
- `ingredients_text` is used as fallback
- language, countries, categories, and store tags can contribute to locale-aware ranking

### USDA FoodData Central

#### Main Strengths

- structured nutrient data
- energy values
- useful generic food coverage
- raw water values

#### Typical Weaknesses

- weak packaged-product identity compared with OFF
- no ingredients
- no allergens
- no labels
- often less regionally appropriate for German grocery searches

#### Current Mapping Notes

- USDA is important for:
  - generic food search
  - strong nutrient coverage
  - US-oriented search contexts
- raw water values stay in the import model until a trusted hydration classification exists

### BLS

#### Main Strengths

- strong coverage for many generic German foods
- local bundled snapshot avoids runtime API dependency
- good fit for Germany-first generic food ranking

#### Typical Weaknesses

- not a packaged-product source
- brand and barcode identity are generally absent
- coverage is intentionally snapshot-based, not live-search against a remote API

#### Current Mapping Notes

- BLS is an important source for:
  - generic German foods
  - Germany-first search ranking
- BLS records are bundled as a compact local snapshot under `custom_components/brizel_health/data/`

## ImportedFoodData

### Role

- neutral handoff model between source adapters and Brizel-internal import logic

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
  - `allergens`
  - `labels`
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

## Import Cache

### Role

- stores imported source snapshots separately from the internal food catalog

### Current Structure

- bucket: `nutrition.imported_food_cache`
- hierarchy:
  - `source_name`
  - `source_id`

### Design Decision

- external snapshots stay separate from the final internal food entity
- this keeps source data, normalization, and internal model concerns separated

## Recent Foods

### Role

- stores per-profile references to recently used foods

### Current Structure

- bucket: `nutrition.recent_foods_by_profile`

### Design Decision

- recent foods are profile-scoped
- only references are stored
- food data is not duplicated
- recent foods are updated from the normal food-entry flow when the recent-food repository is available

## Source Registry

### Role

- central application-level registry of available external sources

### Current Source Definition Fields

- `name`
- `adapter`
- `priority`
- `enabled`

### Runtime Configuration

- the Home Assistant adapter builds a runtime registry during entry setup
- current runtime settings support:
  - `enabled`
  - `priority`
  - source-specific credentials such as the USDA API key

### Priority Model

- equal or legacy-neutral source priorities are treated as the baseline dynamic ranking mode
- intentionally different source priorities act as a bounded manual override
- this avoids the old conflict between fixed source numbers and the newer search-quality ranking logic

## Live Search

### Current Flow

1. The caller provides a query and optional source constraints.
2. Search intelligence normalizes the query and generates a small set of controlled variants.
3. The registry selects enabled sources.
4. Each source runs its own search implementation.
5. Per-source failures stay isolated instead of breaking the whole search.
6. Results are merged, plausibility-filtered, deduplicated, and ranked into one user-facing list.

### Result Data

- `source_name`
- `source_id`
- `name`
- `brand`
- `barcode`
- optional nutrition hints
- optional locale or market hints where available

### Current Search Quality Layer

- query normalization for German and English search terms
- locale-aware ranking through profile and Home Assistant hints
- region-aware source weighting
- recent-food boosts
- no-results protection against clearly implausible matches

## Source Strategy

### Generic Foods

- Germany-first contexts tend to favor:
  - `bls`
  - then suitable `open_food_facts`
  - then `usda`
- USA-oriented contexts tend to favor:
  - `usda`
  - then suitable `open_food_facts`
  - with `bls` staying supplementary

### Branded Products

- `open_food_facts` stays an important global product source
- branded and packaged-product queries should not be treated like pure generic food queries

## Import Orchestration

### Current Flow

1. Search returns source-neutral results without mutating the internal catalog.
2. The UI selects one source result.
3. Detail lookup loads one source-neutral imported-food payload.
4. Import creates or reuses one internal `Food`.
5. Logging creates the final `FoodEntry` for one Brizel profile.

### Failure Behavior

- one source failing does not block the others
- search and import remain separate
- there is still no automatic cross-source merge into one final food

## Current Stable Decisions

- one adapter per source
- one neutral import model
- one neutral search-result model
- separate import cache
- profile-scoped recent foods
- central source registry
- multi-source search with locale-aware ranking
- live OFF search/detail support
- live USDA search/detail support
- bundled BLS snapshot search/detail support

## Deliberately Deferred

- cross-source merge into one final food
- automatic hydration classification of uncertain imported foods
- large end-user source-management UI
- barcode camera UX
