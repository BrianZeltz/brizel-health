# Server and Home Assistant Catalog Mirror Architecture

## Purpose

This document describes the intended boundary between the central Brizel server
and the Home Assistant repository as a later catalog mirror.

The central server remains the source of truth for:

- community-food submission upload
- review and admin workflows
- canonical approval of public community-food records
- future canonical approval of public community-recipe records

Home Assistant can later mirror public read-only catalog data locally.

The goals are:

- reduce central server load for catalog-style read traffic
- enable power users to run local or near-offline catalog access
- support a later HA-only mode for local search and logging
- keep private, user-specific, and admin-only data separate from public catalog
  data

## Current state

- the FastAPI server currently exists inside the mobile-app workspace under
  `server/`
- that server is not yet deployed on a real staging or production host
- the server already contains submission and admin-review APIs
- the mobile app already supports:
  - local custom-food submission drafts
  - dev upload
  - manual submission status refresh
- real auth and RBAC are still missing
- Docker/Postgres validation on a real Docker-capable environment is still
  pending

For repository boundaries this means:

- the HA architecture belongs in the Home Assistant repo
- the current temporary server code location in the mobile-app repo is an
  implementation detail, not a long-term ownership signal

## Deployment interpretation

“Build the server” now means two separate things:

1. continue developing the server code
2. run that code on a real host

A real staging deployment still needs:

- Linux and Docker Compose
- PostgreSQL with persistent volume
- `.env` configuration
- Alembic migration execution
- reverse proxy
- TLS and domain setup
- logs
- backups

Current dev identity headers are only a temporary bridge and are not production
authentication.

## Data classes

### Private or not globally mirrorable

These data classes must never be distributed as a general HA catalog dump:

- users
- profiles
- food logs
- private custom foods
- private notes
- submission drafts
- rejected submissions
- review events
- admin or internal notes
- submitter IDs
- auth and session data

### Public and read-only mirrorable

These data classes are candidates for later HA mirroring:

- BLS catalog
- BLS nutrient details
- approved active community foods
- public community-food search indexes
- later approved community recipes
- catalog manifest
- checksums
- schema and catalog versions

## Normal server mode

In normal server mode:

- the app talks directly to the central server
- uploads go to the server
- status refresh goes to the server
- future community-food search goes to the server
- admin review stays on the server
- Home Assistant is not involved

## Home Assistant mirror mode

In Home Assistant mirror mode:

- HA downloads public catalog data from the central server
- HA stores that catalog locally
- HA exposes local read-only APIs for catalog-style access
- the app may use HA as a local read source for search and lookup
- upload, review, auth, and approval remain central-server concerns

In other words, HA acts as a mirror and edge cache for approved public catalog
data. It is not the admin system, and it is not the authoritative user-data
store.

## HA-only mode

In HA-only mode:

- power users use HA as their local catalog source
- local search and logging can run against mirrored catalog data

Without the central server:

- there is no community submission upload
- there is no admin review
- there is no central status refresh
- local submission drafts remain local

HA-only is therefore appropriate for read, search, and logging workflows, but
not for community approval workflows.

## Catalog export API concept

Possible future server-side export endpoints:

- `GET /catalog/manifest.json`
- `GET /catalog/bls.sqlite.gz`
- `GET /catalog/community_foods.sqlite.gz`
- `GET /catalog/community_foods_delta.jsonl`
- later:
  - `GET /catalog/recipes.sqlite.gz`
  - `GET /catalog/recipes_delta.jsonl`

Possible manifest fields:

- `catalog_version`
- `schema_version`
- `generated_at`
- `files`
- `url`
- `sha256`
- `size_bytes`
- `content_type`
- `min_app_version`
- `delta_from`
- optional `expires_at`

## HA local API concept

Possible later HA-facing local endpoints:

- `GET /health`
- `GET /catalog/manifest`
- `GET /bls/search`
- `GET /community-foods/search`
- `GET /foods/{source}/{id}`
- later:
  - `GET /recipes/search`
  - `GET /recipes/{id}`

## App data source modes

Possible later app data-source modes:

- `server`
  - the central server is the source
- `ha_mirror`
  - HA is the local read source while the server handles upload and review
- `ha_only`
  - HA or local read-only source, no server submission
- `server_with_ha_fallback`
  - server first, HA on server unavailability
- `ha_first_with_server_fallback`
  - HA first, server when HA lacks data

Important boundary:

- submission upload should only target the real server
- the HA mirror can serve catalog data
- the HA mirror must not review or approve submissions

## Sync and update strategy

Recommended strategy:

- start with full dumps
- add delta updates later
- require checksums
- use atomic download flow:
  - download the new file
  - verify checksum
  - switch it live only after verification
- version all exported catalog artifacts
- allow rollback to the last valid local catalog version
- never store large catalog dumps inside Git

## Security and privacy

HA mirror artifacts must not contain personal or administrative data.

That means no:

- food logs
- private custom foods
- notes
- submitter IDs
- admin review data

Public community foods are curated approved catalog records, not raw user
submissions.

Upload and admin auth remain server-side responsibilities.

## Operational implications

This architecture has direct operational consequences:

- the central server can be relieved from repeated catalog read traffic
- HA can answer local read requests for power users
- the server needs export jobs
- HA needs storage space
- HA needs update-failure handling
- the app needs explicit data-source configuration
- support complexity increases once power-user modes are supported

## Recommended implementation order

1. deploy a staging server
2. validate Postgres and Alembic on a real environment
3. build public community-food search on the server
4. integrate app community-food search against the server
5. finalize the catalog export design
6. build manifest and community-food export
7. build an HA mirror MVP
8. add app HA data-source modes
9. add BLS export and mirror support
10. later add recipe export and mirror support

## Open decisions

- SQLite dump vs JSONL vs both
- full-dump frequency
- delta strategy
- HA add-on vs HA integration
- local HA API auth yes or no
- app configuration UX
- BLS first or community foods first for mirroring
- how long old catalog versions should remain on the server
- whether HA may store local submit drafts
- whether HA should ever support local community catalogs without central
  server approval

## Out of scope for now

- HA add-on code
- catalog export implementation
- real deployment
- real auth
- admin UI
- recipe mirror
- BLS server migration
- automatic app source switching
