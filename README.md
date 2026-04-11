# Brizel Health

Brizel Health is a custom Home Assistant integration for profile-based nutrition, hydration, food imports, and target-aware dashboarding.

This repository is prepared for:

- GitHub-hosted source control
- HACS custom repository installation
- integration-packaged Lovelace cards
- stable tagged GitHub releases

It is not yet optimized for submission to the official default HACS catalog.

## Repository Layout

- integration code: `custom_components/brizel_health/`
- frontend cards packaged with the integration: `custom_components/brizel_health/frontend/`
- developer documentation: `docs/`
- HACS metadata: `hacs.json`

## HACS Custom Repository Installation

1. Push this repository to GitHub.
2. In HACS, add the GitHub repository as a custom repository.
3. Select repository type `Integration`.
4. Install `Brizel Health`.
5. Restart Home Assistant.
6. Add the Lovelace card resources listed below.

## Lovelace Resources

The custom cards are now served by the integration itself and no longer need loose files under `/config/www`.

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

## Important Assumption

This repository currently assumes it will be published at:

- `https://github.com/brizel/brizel_health`

If you publish it under a different owner or repository name, update these fields afterwards:

- `custom_components/brizel_health/manifest.json`
  - `documentation`
  - `issue_tracker`
  - `codeowners`
