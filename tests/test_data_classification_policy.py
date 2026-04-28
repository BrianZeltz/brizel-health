"""Focused tests for future data-classification guardrails."""

from __future__ import annotations

from custom_components.brizel_health.domains.security.models.data_classification_policy import (
    DATA_CLASSIFICATION_DIAGNOSTIC_OR_BUG_REPORT,
    DATA_CLASSIFICATION_FUTURE_PRIVATE_USER_CONTENT,
    DATA_CLASSIFICATION_PRIVATE_HEALTH_PAYLOAD,
    DATA_CLASSIFICATION_PUBLIC_OR_COMMUNITY_CONTENT,
    DATA_CLASSIFICATION_TELEMETRY,
    DATA_CLASSIFICATION_VISIBLE_OPERATIONAL_METADATA,
    DATA_HANDLING_MODE_AGGREGATED_TECHNICAL_ONLY,
    DATA_HANDLING_MODE_EXPLICIT_PUBLISH_ONLY,
    DATA_HANDLING_MODE_EXPLICIT_USER_OPT_IN,
    DATA_HANDLING_MODE_NEVER,
    data_classification_for_identifier,
    default_data_classification_policy,
    requires_classification_before_implementation,
)


def test_core_payload_classes_are_private_health_payload() -> None:
    for identifier in (
        "profile_context",
        "steps",
        "body_measurements",
        "body_goals",
        "food_logs",
    ):
        rule = data_classification_for_identifier(identifier)

        assert rule is not None
        assert rule.classification_id == DATA_CLASSIFICATION_PRIVATE_HEALTH_PAYLOAD
        assert rule.must_encrypt_at_rest is True
        assert rule.allow_plaintext_persistent_store is False
        assert rule.telemetry_mode == DATA_HANDLING_MODE_NEVER
        assert rule.bug_report_mode == DATA_HANDLING_MODE_NEVER


def test_future_private_classes_are_preclassified_and_blocked() -> None:
    for identifier in (
        "private_foods",
        "food_favorites",
        "recipes",
        "recipe_variants",
        "cooked_recipe_batches",
        "local_food_cache",
    ):
        rule = data_classification_for_identifier(identifier)

        assert rule is not None
        assert (
            rule.classification_id
            == DATA_CLASSIFICATION_FUTURE_PRIVATE_USER_CONTENT
        )
        assert rule.must_encrypt_at_rest is True
        assert rule.allow_plaintext_persistent_store is False
        assert rule.allow_portable_backup is False
        assert rule.allow_sync is False
        assert rule.bug_report_mode == DATA_HANDLING_MODE_NEVER
        assert rule.telemetry_mode == DATA_HANDLING_MODE_NEVER


def test_visible_metadata_is_operational_not_private_payload() -> None:
    rule = data_classification_for_identifier("record_id")

    assert rule is not None
    assert (
        rule.classification_id
        == DATA_CLASSIFICATION_VISIBLE_OPERATIONAL_METADATA
    )
    assert rule.must_encrypt_at_rest is False
    assert rule.allow_plaintext_persistent_store is True
    assert rule.allow_sync is True
    assert rule.allow_journal is True
    assert rule.allow_outbox is True


def test_public_community_content_requires_explicit_publish() -> None:
    rule = data_classification_for_identifier("explicitly_published_recipe")

    assert rule is not None
    assert (
        rule.classification_id == DATA_CLASSIFICATION_PUBLIC_OR_COMMUNITY_CONTENT
    )
    assert rule.public_exposure_mode == DATA_HANDLING_MODE_EXPLICIT_PUBLISH_ONLY
    assert rule.requires_explicit_user_action is True


def test_diagnostic_and_telemetry_rules_stay_payload_free_and_explicit() -> None:
    diagnostic = data_classification_for_identifier("bug_report_bundle")
    telemetry = data_classification_for_identifier("technical_event")

    assert diagnostic is not None
    assert (
        diagnostic.classification_id
        == DATA_CLASSIFICATION_DIAGNOSTIC_OR_BUG_REPORT
    )
    assert diagnostic.bug_report_mode == DATA_HANDLING_MODE_EXPLICIT_USER_OPT_IN
    assert diagnostic.requires_explicit_user_action is True

    assert telemetry is not None
    assert telemetry.classification_id == DATA_CLASSIFICATION_TELEMETRY
    assert (
        telemetry.telemetry_mode
        == DATA_HANDLING_MODE_AGGREGATED_TECHNICAL_ONLY
    )
    assert telemetry.requires_explicit_user_action is True


def test_policy_guardrails_require_classification_before_new_private_class() -> None:
    policy = default_data_classification_policy()

    assert any(
        "No new private data class without classification" in item
        for item in policy.guardrails
    )
    assert requires_classification_before_implementation("mood_journal") is True
    assert requires_classification_before_implementation("recipes") is False

