# Nutrition And Hydration

## Purpose

This document summarizes the current Nutrition, Water, Hydration, and Compatibility scope.

## Current Nutrition Scope

### Food Catalog

- create, read, update, and delete for foods
- uniqueness rules for:
  - name plus brand
  - barcode
- optional metadata on foods for:
  - hydration
  - compatibility
- persistent storage in `nutrition.foods`

### FoodEntry

- create, read, list, and delete food entries
- links one profile to one consumed food amount
- persistent storage in `nutrition.food_entries`

### Daily Summary

- aggregates nutrition totals per profile and date
- returns:
  - `kcal`
  - `protein`
  - `carbs`
  - `fat`

## Current Water Scope

### Internal Water Food

- implemented as a canonical internal `Food`
- reserved ID: `brizel_internal_water`
- nutrition values: all `0`
- hydration metadata:
  - `hydration_kind = "drink"`
  - `hydration_ml_per_100g = 100`
  - `hydration_source = "internal"`

### Water Shortcut

- implemented in `application/nutrition/add_water.py`
- creates a normal `FoodEntry`
- default amount is `250 ml`
- custom amounts are allowed

### Protection Rules

- the internal water food cannot be updated through normal catalog flows
- the internal water food cannot be deleted through normal catalog flows
- hydration and compatibility metadata cannot be changed directly on internal water
- import flows must not reuse or overwrite the canonical water food

## Current Hydration Scope

### Hydration Fields On Food

- `hydration_kind`
  - `drink`
  - `food`
- `hydration_ml_per_100g`
- `hydration_source`
  - `internal`
  - `explicit`
  - `imported`

### Hydration Summary

- implemented as a query over `Food` and `FoodEntry`
- returns:
  - `drank_ml`
  - `food_hydration_ml`
  - `total_hydration_ml`

### Hydration Breakdown

- implemented as a food-level report
- one item per contributing food
- each item contains:
  - `food_id`
  - `food_name`
  - `food_brand`
  - `hydration_kind`
  - `hydration_source`
  - `hydration_ml`
  - `entry_count`

### Hydration Source Semantics

- `internal`
  - defined by Brizel itself
  - example: canonical water
- `explicit`
  - intentionally set by trusted internal enrichment
- `imported`
  - imported from an external source and accepted as trusted hydration metadata

### Unknown Handling

- foods without trusted hydration metadata are treated as unknown
- unknown foods are excluded from hydration totals
- raw imported water measurements may exist in `ImportedFoodData` without being promoted into internal hydration metadata yet

## Hydration Concept

### Drink Versus Food

- `drink`
  - counts as directly consumed liquid
- `food`
  - counts as hydration coming from foods

### Conservative Rule

- Hydration is calculated only when the system has a reliable basis.
- The system does not guess hydration values or hydration classes for unknown foods.

## Current Compatibility Scope

### Compatibility Metadata

- foods can carry trusted compatibility metadata for:
  - ingredients
  - allergens
  - labels
- metadata can come from:
  - explicit internal enrichment
  - imported source data

### Compatibility Result

- compatibility returns:
  - `compatible`
  - `incompatible`
  - `unknown`
- results include structured reason objects for:
  - incompatible findings
  - unknown sections

### Advisory-Only Rule

- compatibility is informative only
- compatibility does not block:
  - food creation
  - food update
  - food entry creation
  - water tracking

### Body And Nutrition Boundary

- Body owns user restrictions such as:
  - dietary pattern
  - allergens
  - intolerances
- Nutrition owns:
  - food metadata
  - compatibility evaluation
  - compatibility result shaping
- the cross-module orchestration lives in `application/queries/compatibility_queries.py`

## Key Design Decisions

### No Separate Hydration System

- hydration is not a parallel domain model with its own storage
- hydration extends the existing food catalog and food entry flows

### No Separate Compatibility System

- compatibility does not create its own persistence model
- compatibility extends the food catalog through metadata plus read-time evaluation

### Water Uses Existing Nutrition Structures

- water is a normal food definition
- water intake is a normal food entry
- the shortcut improves ergonomics only

### Conservative Handling Of Uncertain Data

- missing data stays unknown
- the system does not guess compatibility or hydration
- imported data may remain partially unknown

## What Is Intentionally Not Implemented

### Automatic Classification

- no heuristic drink detection
- no heuristic compatibility inference
- no attempt to infer hydration from unknown foods automatically

### External Runtime Integration

- no live external food API calls
- no source merge across multiple external providers
- no adapter or UI logic that assumes source availability at runtime

### Home Assistant Integration Work

- no active work on sensors
- no active work on buttons
- no active work on platform forwarding
- no active Home Assistant entity work for hydration or compatibility

## Current Readiness

### Stable Today

- local testing of food and food-entry flows
- local testing of water shortcut behavior
- local testing of hydration summary and breakdown
- local testing of advisory-only compatibility evaluation
- local testing of imported compatibility and hydration metadata handling

### Deferred To Later Phases

- UI presentation of warnings, badges, or hydration views
- live source synchronization
- goals, coaching, or time-series trend features
- more advanced imported-food enrichment rules
