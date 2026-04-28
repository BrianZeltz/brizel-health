"""Guardrails for private data classes, telemetry, and bug-report payloads."""

from __future__ import annotations

from dataclasses import dataclass

DATA_CLASSIFICATION_PRIVATE_HEALTH_PAYLOAD = "private_health_payload"
DATA_CLASSIFICATION_FUTURE_PRIVATE_USER_CONTENT = (
    "future_private_user_content"
)
DATA_CLASSIFICATION_VISIBLE_OPERATIONAL_METADATA = (
    "visible_operational_metadata"
)
DATA_CLASSIFICATION_PUBLIC_OR_COMMUNITY_CONTENT = (
    "public_or_community_content"
)
DATA_CLASSIFICATION_DIAGNOSTIC_OR_BUG_REPORT = (
    "diagnostic_or_bug_report"
)
DATA_CLASSIFICATION_TELEMETRY = "telemetry"

DATA_HANDLING_MODE_NEVER = "never"
DATA_HANDLING_MODE_ALLOWED = "allowed"
DATA_HANDLING_MODE_REDACTED_METADATA_ONLY = "redacted_metadata_only"
DATA_HANDLING_MODE_AGGREGATED_TECHNICAL_ONLY = (
    "aggregated_technical_only"
)
DATA_HANDLING_MODE_EXPLICIT_PUBLISH_ONLY = "explicit_publish_only"
DATA_HANDLING_MODE_EXPLICIT_USER_OPT_IN = "explicit_user_opt_in"


@dataclass(frozen=True)
class DataClassificationRule:
    """One future-facing handling rule for a class of data."""

    classification_id: str
    identifiers: tuple[str, ...]
    must_encrypt_at_rest: bool
    allow_portable_backup: bool
    allow_sync: bool
    allow_journal: bool
    allow_outbox: bool
    bug_report_mode: str
    telemetry_mode: str
    public_exposure_mode: str
    requires_explicit_user_action: bool
    allow_plaintext_persistent_store: bool
    description: str

    def to_dict(self) -> dict[str, object]:
        return {
            "classification_id": self.classification_id,
            "identifiers": list(self.identifiers),
            "must_encrypt_at_rest": self.must_encrypt_at_rest,
            "allow_portable_backup": self.allow_portable_backup,
            "allow_sync": self.allow_sync,
            "allow_journal": self.allow_journal,
            "allow_outbox": self.allow_outbox,
            "bug_report_mode": self.bug_report_mode,
            "telemetry_mode": self.telemetry_mode,
            "public_exposure_mode": self.public_exposure_mode,
            "requires_explicit_user_action": self.requires_explicit_user_action,
            "allow_plaintext_persistent_store": (
                self.allow_plaintext_persistent_store
            ),
            "description": self.description,
        }


@dataclass(frozen=True)
class DataClassificationPolicy:
    """Machine-readable guardrails for future private content handling."""

    policy_id: str
    description: str
    rules: tuple[DataClassificationRule, ...]
    guardrails: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "description": self.description,
            "rules": [rule.to_dict() for rule in self.rules],
            "guardrails": list(self.guardrails),
        }


def default_data_classification_policy() -> DataClassificationPolicy:
    """Return the shared guardrail policy for current and future data classes."""
    return DataClassificationPolicy(
        policy_id="data_classification_and_telemetry_policy_v1",
        description=(
            "Guardrail policy for private payloads, visible operational "
            "metadata, future private user content, bug-report payloads, "
            "telemetry, and community publication."
        ),
        rules=(
            DataClassificationRule(
                classification_id=DATA_CLASSIFICATION_PRIVATE_HEALTH_PAYLOAD,
                identifiers=(
                    "profile_context",
                    "steps",
                    "body_measurements",
                    "body_goals",
                    "food_logs",
                ),
                must_encrypt_at_rest=True,
                allow_portable_backup=True,
                allow_sync=True,
                allow_journal=True,
                allow_outbox=True,
                bug_report_mode=DATA_HANDLING_MODE_NEVER,
                telemetry_mode=DATA_HANDLING_MODE_NEVER,
                public_exposure_mode=DATA_HANDLING_MODE_NEVER,
                requires_explicit_user_action=False,
                allow_plaintext_persistent_store=False,
                description=(
                    "Current private health payload classes. They must stay "
                    "encrypted at rest and must never be sent automatically "
                    "into bug reports, telemetry, or public/community channels."
                ),
            ),
            DataClassificationRule(
                classification_id=(
                    DATA_CLASSIFICATION_FUTURE_PRIVATE_USER_CONTENT
                ),
                identifiers=(
                    "private_foods",
                    "food_favorites",
                    "recipes",
                    "recipe_variants",
                    "cooked_recipe_batches",
                    "local_food_cache",
                ),
                must_encrypt_at_rest=True,
                allow_portable_backup=False,
                allow_sync=False,
                allow_journal=False,
                allow_outbox=False,
                bug_report_mode=DATA_HANDLING_MODE_NEVER,
                telemetry_mode=DATA_HANDLING_MODE_NEVER,
                public_exposure_mode=DATA_HANDLING_MODE_NEVER,
                requires_explicit_user_action=False,
                allow_plaintext_persistent_store=False,
                description=(
                    "Reserved future private user-content classes. They must "
                    "be classified and designed before any sync, backup, or "
                    "reporting path is allowed."
                ),
            ),
            DataClassificationRule(
                classification_id=(
                    DATA_CLASSIFICATION_VISIBLE_OPERATIONAL_METADATA
                ),
                identifiers=(
                    "profile_id",
                    "local_profile_id",
                    "record_id",
                    "record_type",
                    "domain",
                    "source_type",
                    "source_detail",
                    "origin_node_id",
                    "source_node_id",
                    "updated_by_node_id",
                    "created_at",
                    "updated_at",
                    "deleted_at",
                    "revision",
                    "cursor",
                    "sequence",
                    "updated_after",
                    "outbox_updated_after",
                    "content_sha256",
                    "integrity_algorithm",
                ),
                must_encrypt_at_rest=False,
                allow_portable_backup=True,
                allow_sync=True,
                allow_journal=True,
                allow_outbox=True,
                bug_report_mode=DATA_HANDLING_MODE_REDACTED_METADATA_ONLY,
                telemetry_mode=DATA_HANDLING_MODE_AGGREGATED_TECHNICAL_ONLY,
                public_exposure_mode=DATA_HANDLING_MODE_NEVER,
                requires_explicit_user_action=False,
                allow_plaintext_persistent_store=True,
                description=(
                    "Operational metadata that may stay visible for sync, "
                    "routing, tombstones, backup integrity, and replay. It "
                    "still leaks timing and topology patterns and must not be "
                    "mistaken for public payload."
                ),
            ),
            DataClassificationRule(
                classification_id=(
                    DATA_CLASSIFICATION_PUBLIC_OR_COMMUNITY_CONTENT
                ),
                identifiers=(
                    "explicitly_published_food",
                    "explicitly_published_recipe",
                    "community_catalog_entry",
                ),
                must_encrypt_at_rest=False,
                allow_portable_backup=False,
                allow_sync=False,
                allow_journal=False,
                allow_outbox=False,
                bug_report_mode=DATA_HANDLING_MODE_NEVER,
                telemetry_mode=DATA_HANDLING_MODE_NEVER,
                public_exposure_mode=DATA_HANDLING_MODE_EXPLICIT_PUBLISH_ONLY,
                requires_explicit_user_action=True,
                allow_plaintext_persistent_store=True,
                description=(
                    "Public or community-facing content is only public after "
                    "an explicit publish/share action. It must not become "
                    "public by default just because it originated from a "
                    "private workflow."
                ),
            ),
            DataClassificationRule(
                classification_id=(
                    DATA_CLASSIFICATION_DIAGNOSTIC_OR_BUG_REPORT
                ),
                identifiers=(
                    "diagnostic_snapshot",
                    "bug_report_bundle",
                    "support_export",
                ),
                must_encrypt_at_rest=False,
                allow_portable_backup=False,
                allow_sync=False,
                allow_journal=False,
                allow_outbox=False,
                bug_report_mode=DATA_HANDLING_MODE_EXPLICIT_USER_OPT_IN,
                telemetry_mode=DATA_HANDLING_MODE_NEVER,
                public_exposure_mode=DATA_HANDLING_MODE_NEVER,
                requires_explicit_user_action=True,
                allow_plaintext_persistent_store=False,
                description=(
                    "Bug reports and support exports are payload-free by "
                    "default. Additional contents require explicit user action "
                    "and should stay limited to redacted operational metadata "
                    "unless deliberately reviewed."
                ),
            ),
            DataClassificationRule(
                classification_id=DATA_CLASSIFICATION_TELEMETRY,
                identifiers=(
                    "technical_event",
                    "aggregated_sync_metric",
                    "retry_counter_sample",
                ),
                must_encrypt_at_rest=False,
                allow_portable_backup=False,
                allow_sync=False,
                allow_journal=False,
                allow_outbox=False,
                bug_report_mode=DATA_HANDLING_MODE_NEVER,
                telemetry_mode=DATA_HANDLING_MODE_AGGREGATED_TECHNICAL_ONLY,
                public_exposure_mode=DATA_HANDLING_MODE_NEVER,
                requires_explicit_user_action=True,
                allow_plaintext_persistent_store=False,
                description=(
                    "Telemetry is off by default unless consciously enabled "
                    "later. It must stay payload-free and limited to "
                    "aggregated technical events."
                ),
            ),
        ),
        guardrails=(
            "private_health_payload must never be plaintext in persistent storage.",
            "future_private_user_content must never be plaintext in persistent storage.",
            "private payload classes must never be attached automatically to bug reports.",
            "private payload classes must never be sent through telemetry.",
            "visible_operational_metadata may stay visible, but is still part of the privacy threat model.",
            "public_or_community_content only becomes public through explicit publish/share action.",
            "No new private data class without classification, encryption decision, backup decision, sync decision, bug-report decision, telemetry decision.",
        ),
    )


def data_classification_for_identifier(
    identifier: str,
) -> DataClassificationRule | None:
    """Return the policy rule for one known identifier or field."""
    normalized = str(identifier).strip()
    if not normalized:
        return None
    for rule in default_data_classification_policy().rules:
        if normalized in rule.identifiers:
            return rule
    return None


def requires_classification_before_implementation(identifier: str) -> bool:
    """Return whether a future identifier is still unclassified."""
    return data_classification_for_identifier(identifier) is None

