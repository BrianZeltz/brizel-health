# Data Classification and Telemetry Policy

## Purpose

This policy exists to stop future features from accidentally storing, exporting,
reporting, or publishing private payloads outside the intended encrypted paths.

It is a guardrail for future implementation work, not a promise that every
possible future feature already exists.

## Current rule

No new private data class without classification, encryption decision, backup
decision, sync decision, bug-report decision, telemetry decision.

## Data classes

### `private_health_payload`

Examples:
- `profile_context`
- `steps`
- `body_measurements`
- `body_goals`
- `food_logs`

Rules:
- must be encrypted at rest
- may participate in sync / journal / outbox when needed
- may participate in portable backup only through the encrypted backup path
- must not be stored as plaintext payload in persistent stores
- must not be attached automatically to bug reports
- must not be sent through telemetry
- must not be exposed publicly or through community uploads by default

### `future_private_user_content`

Examples:
- `private_foods`
- `food_favorites`
- `recipes`
- `recipe_variants`
- `cooked_recipe_batches`
- `local_food_cache`

Rules:
- must be treated as private from day one
- must be encrypted at rest
- default is no sync / no journal / no outbox / no backup until explicitly designed
- must not be stored as plaintext payload in persistent stores
- must not be attached automatically to bug reports
- must not be sent through telemetry
- must not become public by default

### `visible_operational_metadata`

Examples:
- `profile_id`
- `local_profile_id`
- `record_id`
- `domain`
- `revision`
- `updated_at`
- `deleted_at`
- `cursor`
- `sequence`
- `source_node_id`
- `updated_by_node_id`

Rules:
- may stay visible where sync, routing, journal replay, tombstones, integrity,
  or operational checkpoints need it
- is still part of the privacy threat model
- may leak timing, topology, churn, and activity patterns
- must not be mistaken for safe public payload

### `public_or_community_content`

Examples:
- `explicitly_published_food`
- `explicitly_published_recipe`
- `community_catalog_entry`

Rules:
- may only become public after explicit publish/share action
- private origin does not imply permission to publish
- public exposure must be deliberate and product-visible

### `diagnostic_or_bug_report`

Rules:
- default payload-free
- no health / food / recipe payloads attached automatically
- at most redacted operational metadata unless the user explicitly opts in
- explicit user action required for richer support exports

### `telemetry`

Rules:
- default off unless consciously enabled later
- payload-free
- no health / food / recipe payloads
- limited to aggregated or technical events only

## What must be encrypted

Any class classified as `private_health_payload` or
`future_private_user_content` must not persist as plaintext payload.

## What may remain visible

Operational metadata may remain visible only when needed for:
- sync partitioning
- routing
- journal replay
- outbox retry / replay
- tombstones
- backup manifest / integrity

Visible metadata still leaks patterns. Encryption of payloads does not erase
those pattern leaks.

## Community upload versus private data

Community/public content is a separate class from private user data.

Private data does not become public just because it could be useful to others.
Publication requires an explicit share/publish action and a product flow built
for that purpose.

## Bug-report rules

- no automatic private payload attachment
- prefer redacted operational metadata
- richer exports require explicit user approval

## Telemetry rules

- no private payloads
- no health / food / recipe content
- only aggregated or technical events when intentionally enabled

