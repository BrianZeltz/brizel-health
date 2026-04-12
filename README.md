# Brizel Health


## Not Ready for Public Use

Brizel Health is currently in active alpha development and is not yet released for general installation, public use, or production environments.

This public repository exists primarily for transparency, iteration, and development progress. Breaking changes, incomplete features, missing documentation, and unstable behavior should be expected until an official release is announced.

Please wait for an official release announcement before treating this project as installable or supported.

For licensing, commercial, partnership, or permission inquiries, contact [brian@brizel.de](mailto:brian@brizel.de).

---

Brizel Health is a privacy-first, local-first health platform built on Home Assistant.

Its current foundation focuses on profile-based nutrition, hydration, food imports, and target-aware health dashboards. Over time, the platform is intended to expand into broader body data, wearable integrations, and additional health modules while keeping user data local and under the user's control.

This repository is being prepared for:

- GitHub-hosted source control
- future HACS custom repository distribution
- integration-packaged Lovelace cards
- stable tagged GitHub releases

It is not yet announced as a supported installation target and is not yet optimized for submission to the official default HACS catalog.

## Project Status

Brizel Health is currently **alpha software** and under **active development**.

- not production ready
- interfaces and data models may still change
- intended today for careful self-hosted evaluation, testing, and iteration

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

For commercial licensing, partnership, or permission requests, contact:

- [brian@brizel.de](mailto:brian@brizel.de)

See:

- [LICENSE.md](LICENSE.md)
- [LICENSING.md](LICENSING.md)
- [COMMERCIAL_USE.md](COMMERCIAL_USE.md)

## Data Sources

Brizel Health can integrate with external food databases, currently centered on:

- USDA FoodData Central
- Open Food Facts

Brizel Health is **not affiliated with, endorsed by, or sponsored by** USDA FoodData Central or Open Food Facts.

Brizel Health does not claim ownership over third-party food database content retrieved from those services.

See:

- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)

## Repository Layout

- integration code: `custom_components/brizel_health/`
- frontend cards packaged with the integration: `custom_components/brizel_health/frontend/`
- developer documentation: `docs/`
- HACS metadata: `hacs.json`

## Planned Distribution Path

The repository structure is being prepared for future GitHub Releases and future HACS custom repository distribution.

Once Brizel Health is officially released for broader installation, the intended path is:

1. GitHub Releases for stable tagged versions
2. HACS custom repository distribution for supported Home Assistant installs

Until then, this repository should be treated as an in-progress public development repo rather than a general installation target.

## Frontend Packaging

The custom cards are now served by the integration itself and no longer need loose files under `/config/www`.
For standard storage-managed Lovelace resources, Brizel Health is already structured to register the card resources automatically during config-entry setup.

Current resource URLs:

- `/api/brizel_health/frontend/brizel-health-hero-card.js`
- `/api/brizel_health/frontend/brizel-nutrition-card.js`
- `/api/brizel_health/frontend/brizel-macro-card.js`
- `/api/brizel_health/frontend/brizel-hydration-card.js`

The main current limitation is Lovelace resources managed in YAML mode: those remain user-managed by Home Assistant, so Brizel Health will log that automatic registration was skipped.

## Card Types

- `custom:brizel-health-hero-card`
- `custom:brizel-nutrition-card`
- `custom:brizel-macro-card`
- `custom:brizel-hydration-card`

## Release Model

- keep `main` stable
- do feature work on branches
- bump `custom_components/brizel_health/manifest.json` before each release
- create a Git tag such as `v0.1.0`
- publish a GitHub Release from that tag
- future HACS custom repository users can then update to the released version through HACS

More release details are documented in [docs/releasing.md](docs/releasing.md).

## Canonical Repository

- [https://github.com/BrianZeltz/brizel-health](https://github.com/BrianZeltz/brizel-health)
