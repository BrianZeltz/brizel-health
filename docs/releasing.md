# Releasing

## Purpose

This document describes the intended lightweight release flow for `brizel_health`.

## Distribution Target

- GitHub repository
- future HACS custom repository distribution
- tagged GitHub releases

## Stable Branch Rule

- keep `main` releasable
- do unfinished work on feature branches
- avoid publishing partial work from `main`

## Version Source Of Truth

- the current integration version is stored in:
  - `custom_components/brizel_health/manifest.json`

## Release Steps

1. Make sure `main` contains only the stable release state.
2. Update the integration version in `manifest.json`.
3. Run the local checks:
   - `pytest`
   - `py_compile` for changed Python files
4. Commit the release changes.
5. Create a Git tag such as `v0.1.0`.
6. Create a GitHub Release from that tag.
7. Let HACS custom repository users update to the tagged release.

## Validation In GitHub

This repository includes lightweight GitHub Actions for:

- Hassfest
- HACS validation

These checks help keep the repository ready for future custom-repository distribution and later release work.

## Frontend Cards

- frontend card files are packaged inside the integration at `custom_components/brizel_health/frontend/`
- Home Assistant serves them from:
  - `/api/brizel_health/frontend/`
- no loose `/config/www` packaging is required anymore

## Post-Upload Checklist

After the first GitHub upload, verify:

- the repository URL in `manifest.json`
- the issue tracker URL in `manifest.json`
- the `codeowners` entry in `manifest.json`
- the planned HACS custom repository distribution flow
- the Lovelace resource URLs
