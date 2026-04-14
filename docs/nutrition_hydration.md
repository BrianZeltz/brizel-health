# Nutrition And Hydration

## Purpose

This document summarizes the current Nutrition, Water, Hydration, Compatibility, and food-logging scope.

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

### Food Logging Flow

- the current Lovelace food logger uses:
  - external food search
  - external food detail lookup
  - import-if-needed
  - final `FoodEntry` creation
- profile resolution can follow the existing Home Assistant user to Brizel profile link
- the current UI keeps logging conservative and gram-based for external foods

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

### Conservative Rule

- hydration is calculated only when the system has a reliable basis
- the system does not guess hydration values or hydration classes for unknown foods
- imported raw water data can remain unpromoted when the trust basis is too weak

## Current Compatibility Scope

### Compatibility Metadata

- foods can carry trusted compatibility metadata for:
  - ingredients
  - allergens
  - labels
- metadata can come from:
  - explicit internal enrichment
  - imported source data

### Advisory-Only Rule

- compatibility is informative only
- compatibility does not block:
  - food creation
  - food update
  - food entry creation
  - water tracking

## Runtime Source Scope

### Current External Food Sources

- Open Food Facts
- USDA FoodData Central
- BLS

### Current Runtime Behavior

- search is live and multi-source
- search is profile-aware and locale-aware
- search uses recent-food and regional ranking hints where available
- import remains a separate step from search
- save still writes normal internal `FoodEntry` records

## Home Assistant Scope

### Active Integration Surfaces

- profile-aware dashboard cards
- packaged frontend resources served by the integration
- automatic Lovelace resource registration for storage-mode dashboards
- food logger card with dialog-based search and save flow
- nutrition, target, and hydration services
- target sensors and water shortcut buttons

### Current UI Posture

- the card layer stays UI-focused
- business logic remains in Python application/domain code
- the current logger UI intentionally stays small:
  - search
  - detail
  - amount
  - optional time override
  - save

## Key Design Decisions

### No Separate Hydration System

- hydration is not a parallel domain model with its own storage
- hydration extends the existing food catalog and food entry flows

### Water Uses Existing Nutrition Structures

- water is a normal food definition
- water intake is a normal food entry
- the shortcut improves ergonomics only

### Search Does Not Bypass The Core Nutrition Flow

- external search does not create hidden diary entries
- import and final logging still pass through the existing nutrition write path
- recent foods are updated through the normal write flow

### Conservative Handling Of Uncertain Data

- missing data stays unknown
- the system does not guess compatibility or hydration
- imported data may remain partially unknown

## What Is Intentionally Not Implemented

### Search / Logger Scope Not Yet Included

- barcode camera scanning
- meal types
- favorites system
- complex serving or milliliter logging for external foods
- automatic cross-source merge into one canonical imported food

### Hydration / Compatibility Scope Not Yet Included

- heuristic drink detection
- heuristic compatibility inference
- automatic hydration inference for uncertain imported foods
- coaching or trend features

## Current Readiness

### Stable Today

- local nutrition and food-entry flows
- water shortcut behavior
- hydration summary and breakdown
- advisory-only compatibility evaluation
- multi-source food search across OFF, USDA, and BLS
- locale-aware search ranking
- food logger UI flow with profile-aware save behavior
- backend tests and small frontend regression tests

### Deferred To Later Phases

- broader food-logging unit support
- richer import merging
- more advanced hydration classification
- broader end-user guidance and coaching layers
