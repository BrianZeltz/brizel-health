# Brizel Health


## 🚧 Not Ready for Public Use

Brizel Health is currently under active development and is not ready for installation, public use, or production environments.

This repository is published for transparency and development progress only. Breaking changes, incomplete features, missing documentation, and unstable behavior should be expected.

Please wait for an official release announcement before using this project.

For licensing or commercial inquiries: brian@brizel.de

---

Brizel Health is a custom Home Assistant integration for profile-based nutrition, hydration, food imports, and target-aware dashboarding.

This repository is prepared for:

- GitHub-hosted source control
- HACS custom repository installation
- integration-packaged Lovelace cards
- stable tagged GitHub releases

It is not yet optimized for submission to the official default HACS catalog.

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

- `brian@brizel.de`

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

## HACS Custom Repository Installation

1. In HACS, add `https://github.com/BrianZeltz/brizel-health` as a custom repository.
2. Select repository type `Integration`.
3. Install `Brizel Health`.
4. Restart Home Assistant.
5. Open Lovelace and use the cards directly.

## Lovelace Resources

The custom cards are now served by the integration itself and no longer need loose files under `/config/www`.
For standard storage-managed Lovelace resources, Brizel Health now registers the card resources automatically during config-entry setup.

Use these resource URLs:

- `/api/brizel_health/frontend/brizel-health-hero-card.js`
- `/api/brizel_health/frontend/brizel-nutrition-card.js`
- `/api/brizel_health/frontend/brizel-macro-card.js`
- `/api/brizel_health/frontend/brizel-hydration-card.js`

Example:

```yaml
resources:
  - url: /api/brizel_health/frontend/brizel-health-hero-card.js
    type: module
  - url: /api/brizel_health/frontend/brizel-nutrition-card.js
    type: module
  - url: /api/brizel_health/frontend/brizel-macro-card.js
    type: module
  - url: /api/brizel_health/frontend/brizel-hydration-card.js
    type: module
```

In most Home Assistant installations no manual resource entry is needed anymore.
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
- HACS custom repository users can then update to the new release through HACS

More release details are documented in [docs/releasing.md](docs/releasing.md).

## Canonical Repository

- [https://github.com/BrianZeltz/brizel-health](https://github.com/BrianZeltz/brizel-health)
