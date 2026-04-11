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
- reads stable HA sensor state through `hass.states[...]`
- supports explicit entity overrides per macro

### `brizel-macro-card.js`

- detailed view for one macro target status
- reads one stable target-status sensor through `hass.states[...]`
- supports explicit entity override

### `brizel-hydration-card.js`

- hydration summary card
- reads hydration-related sensors through `hass.states[...]`
- supports explicit entity overrides and an optional target entity

## Resource Paths

- `/api/brizel_health/frontend/brizel-health-hero-card.js`
- `/api/brizel_health/frontend/brizel-nutrition-card.js`
- `/api/brizel_health/frontend/brizel-macro-card.js`
- `/api/brizel_health/frontend/brizel-hydration-card.js`

## Card Types

- `custom:brizel-health-hero-card`
- `custom:brizel-nutrition-card`
- `custom:brizel-macro-card`
- `custom:brizel-hydration-card`

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

### Sensor-Backed

- nutrition and macro cards:
  - profile-scoped target-status sensors
- hydration card:
  - profile-scoped hydration summary sensors

## Configuration Philosophy

- explicit configuration stays small
- defaults are convenient, but entity overrides remain available
- no frontend naming convention should be treated as domain truth
- the Hero card is the only card that currently resolves profile context through a backend service

## Extension Guidance

- prefer adding small cards over overloading one card with every feature
- keep display text user-facing and concise
- keep calculation logic in Python application/domain layers
- only extend the card layer after the related backend read model is already stable
