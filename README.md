# Brizel Health

## Not Ready for Public Use

Brizel Health is currently in active alpha development and is not yet released for general installation, public use, or production environments.

This public repository exists primarily for transparency, iteration, and development progress. Breaking changes, incomplete features, unstable behavior, and documentation gaps should still be expected until an official release is announced.

Please wait for an official release announcement before treating this project as installable, supported, or production-ready.

For licensing, commercial, partnership, or permission inquiries, contact [brian@brizel.de](mailto:brian@brizel.de).

---

Brizel Health is a privacy-first, local-first health platform built on Home Assistant.

Today it focuses on profile-based nutrition tracking, hydration tracking, external food search, and Lovelace-first health dashboards. Over time, the platform is intended to grow into broader body data, wearable integrations, and additional health modules while keeping user data local and under the user's control.

## Current Capabilities

- profile-based nutrition tracking with Home Assistant user to Brizel profile linking
- hydration tracking, including water shortcut flows and hydration reporting
- body-data-backed kcal, protein, and fat target calculation with target-status logic
- custom Lovelace cards for Hero, Nutrition, Macro, Hydration, and Food Logging flows
- external food search across:
  - USDA FoodData Central
  - Open Food Facts
  - BLS
- locale-aware and region-aware search ranking for Germany/EU/USA-oriented contexts
- recent-food support and improved empty/no-results search states in the Food Logger
- integration-packaged frontend resources with automatic Lovelace resource registration for storage-managed dashboards
- backend tests with `pytest`
- frontend tests with `npm test` and Vitest/jsdom

## Development Status

Brizel Health is currently **alpha software** and under **active development**.

- not production ready
- interfaces, data models, and ranking behavior may still change
- intended today for careful self-hosted development, testing, and iteration

## Repository Layout

- integration code: `custom_components/brizel_health/`
- packaged frontend cards: `custom_components/brizel_health/frontend/`
- developer documentation: `docs/`
- frontend test setup: `tests/frontend/`
- HACS metadata: `hacs.json`

## Development And Testing

Python checks:

```bash
pytest
```

Frontend checks:

```bash
npm install
npm test
```

The current frontend test setup is intentionally small and focused on the custom-card layer and related utilities. It helps catch interaction regressions early, but it does not replace real Home Assistant live-testing.

## Data Sources

Brizel Health currently integrates with multiple food-data sources:

- USDA FoodData Central
- Open Food Facts
- BLS

These sources currently serve different strengths:

- Open Food Facts is important for branded and packaged products
- BLS is strong for many generic German foods
- USDA remains useful especially for generic foods in more US-oriented contexts

Brizel Health is **not affiliated with, endorsed by, or sponsored by** USDA FoodData Central, Open Food Facts, or BLS.

Brizel Health does not claim ownership over third-party food database content retrieved from those sources.

See:

- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)

## Frontend Packaging

The custom cards are served by the integration itself and no longer require loose files under `/config/www`.

For storage-managed Lovelace resources, Brizel Health can register its frontend resources automatically during config-entry setup.

Current resource URLs:

- `/api/brizel_health/frontend/brizel-health-hero-card.js`
- `/api/brizel_health/frontend/brizel-nutrition-card.js`
- `/api/brizel_health/frontend/brizel-macro-card.js`
- `/api/brizel_health/frontend/brizel-hydration-card.js`
- `/api/brizel_health/frontend/brizel-food-logger-card.js`

Current card types:

- `custom:brizel-health-hero-card`
- `custom:brizel-nutrition-card`
- `custom:brizel-macro-card`
- `custom:brizel-hydration-card`
- `custom:brizel-food-logger-card`

The main current limitation is YAML-managed Lovelace resources: those remain user-managed by Home Assistant and are therefore not rewritten automatically.

## Distribution Status

This repository is being prepared for:

- GitHub-hosted source control
- tagged GitHub releases
- future HACS custom repository distribution

It is not yet announced as a supported installation target and is not yet positioned as a public production-ready install path.

## License

Brizel Health is **source-available**, not a permissive open-source project.

This repository is licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE.md).

In practical terms:

- private use is allowed
- self-hosted Home Assistant use is allowed
- local installation and private modification are allowed
- community testing and noncommercial sharing are allowed under the license terms
- commercial use is **not** freely granted

Commercial scenarios such as paid apps, SaaS or hosting, resale, white-label use, or bundling into commercial products require separate permission.

See:

- [LICENSE.md](LICENSE.md)
- [LICENSING.md](LICENSING.md)
- [COMMERCIAL_USE.md](COMMERCIAL_USE.md)

Commercial licensing, partnership, or permission requests:

- [brian@brizel.de](mailto:brian@brizel.de)

## Release Model

- keep `main` stable
- do feature work on branches
- bump `custom_components/brizel_health/manifest.json` before each release
- create a Git tag such as `v0.1.0`
- publish a GitHub Release from that tag
- later support future HACS custom repository updates from tagged releases

More release details are documented in [docs/releasing.md](docs/releasing.md).

## Canonical Repository

- [https://github.com/BrianZeltz/brizel-health](https://github.com/BrianZeltz/brizel-health)
