# Frontend Cards

## Purpose

This document describes the current Home Assistant frontend card layer for `brizel_health`.

## Location

- frontend files live in `custom_components/brizel_health/frontend/`
- they are plain JavaScript custom elements
- they are packaged with the integration itself

## Design Boundaries

- cards stay frontend-only
- cards do not contain nutrition, hydration, target, or import business logic
- cards only consume:
  - stable Home Assistant sensor state
  - stable Brizel Health Home Assistant services
- cards do not talk to repositories or domain code directly
- cards do not depend on unstable internal Home Assistant frontend components

## Current Card Files

### `brizel-health-hero-card.js`

- primary user-facing overview card
- focuses on today's kcal guidance first
- uses the stable `brizel_health.get_daily_overview` service
- can resolve the active Home Assistant user automatically through that service path
- supports explicit `profile_id` override

### `brizel-nutrition-card.js`

- overview card for kcal, protein, and fat target status
- can resolve the active Home Assistant user through Brizel Health backend services
- can also use explicit entity overrides per macro

### `brizel-macro-card.js`

- detailed view for one macro target status
- can resolve the active Home Assistant user through Brizel Health backend services
- can also use one explicit target-status entity override

### `brizel-hydration-card.js`

- hydration summary card
- can resolve the active Home Assistant user through Brizel Health backend services
- can also read hydration-related sensors through explicit entity overrides
- supports explicit entity overrides and an optional external target entity reference
- does not currently rely on a built-in Brizel Health hydration-goal model

### `brizel-food-logger-card.js`

- v1 food logging entry card
- opens a small multi-step dialog flow for search, confirmation, and save
- uses the stable Brizel Health services for:
  - `search_external_foods`
  - `get_external_food_detail`
  - `get_recent_foods`
  - `log_external_food_entry`
- keeps profile resolution in the existing Home Assistant user -> Brizel profile service path
- currently stays conservative and only exposes gram-based logging for external search results
- empty-search state can show profile-scoped recent foods
- no-results state now distinguishes true empty results from weak off-topic source noise

## Resource Paths

- `/api/brizel_health/frontend/brizel-health-hero-card.js`
- `/api/brizel_health/frontend/brizel-nutrition-card.js`
- `/api/brizel_health/frontend/brizel-macro-card.js`
- `/api/brizel_health/frontend/brizel-hydration-card.js`
- `/api/brizel_health/frontend/brizel-food-logger-card.js`

## Resource Registration

- for Lovelace resources managed in storage mode, the integration now registers these frontend resources automatically during config-entry setup
- resource creation is idempotent and existing matching resources are reused
- if an existing Brizel Health resource has the wrong type, it is updated to `module`
- YAML-managed Lovelace resources remain user-managed by Home Assistant and are therefore not rewritten automatically

## Card Types

- `custom:brizel-health-hero-card`
- `custom:brizel-nutrition-card`
- `custom:brizel-macro-card`
- `custom:brizel-hydration-card`
- `custom:brizel-food-logger-card`

## Home Assistant Frontend Patterns

- each card registers itself through `customElements.define(...)`
- each card announces itself through `window.customCards`
- each card exposes `getStubConfig()`
- each card exposes `getCardSize()`
- each card now also exposes `getGridOptions()` for Home Assistant sections-view sizing
- Home Assistant serves the packaged files through one static integration path registered in `async_setup`

## Data Sources

### Service-Backed

- `brizel-health-hero-card`:
  - `brizel_health.get_daily_overview`
- `brizel-nutrition-card`:
  - `brizel_health.get_daily_overview`
- `brizel-macro-card`:
  - `brizel_health.get_daily_overview`
- `brizel-hydration-card`:
  - `brizel_health.get_daily_hydration_report`
- `brizel-food-logger-card`:
  - `brizel_health.search_external_foods`
  - `brizel_health.get_external_food_detail`
  - `brizel_health.get_recent_foods`
  - `brizel_health.log_external_food_entry`

### Sensor-Backed

- nutrition and macro cards:
  - explicit target-status entity overrides
- hydration card:
  - explicit hydration entity overrides

## Configuration Philosophy

- explicit configuration stays small
- defaults are convenient, but entity overrides remain available
- no frontend naming convention should be treated as domain truth
- profile-aware cards can resolve profile context through Brizel Health backend services
- hydration target comparison is currently only available through an explicitly configured Home Assistant target entity

## Extension Guidance

- prefer adding small cards over overloading one card with every feature
- keep display text user-facing and concise
- keep calculation logic in Python application/domain layers
- only extend the card layer after the related backend read model is already stable

## Frontend Test Setup

- frontend regression tests currently live under `tests/frontend/`
- the current setup uses:
  - `Vitest`
  - `jsdom`
- current focus:
  - card utilities
  - food-logger dialog behavior
  - empty, no-results, and recent-food states
- local commands:
  - `npm install`
  - `npm test`
