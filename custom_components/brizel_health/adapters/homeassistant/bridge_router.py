"""Small router for the Brizel Health app bridge."""

from __future__ import annotations

from datetime import UTC, datetime
import logging
from uuid import uuid4

from homeassistant.helpers.dispatcher import async_dispatcher_send

from ...application.body.body_goal_use_cases import (
    get_body_goal_target_weight_records_for_peer,
    upsert_body_goal_target_weight_peer_record,
)
from ...application.body.body_profile_use_cases import (
    get_body_profile,
    upsert_body_profile,
)
from ...application.body.body_measurement_queries import get_latest_measurement
from ...application.body.body_measurement_use_cases import (
    BODY_MEASUREMENT_PEER_SYNC_TYPES,
    upsert_body_measurement_peer_record,
)
from ...application.fit.step_queries import (
    get_last_steps_import_status,
    get_last_successful_steps_sync,
)
from ...application.fit.step_use_cases import (
    ConflictingStepRecordError,
    DuplicateStepMessageError,
    import_step_entry,
)
from ...application.nutrition.food_entry_use_cases import (
    get_food_log_records_for_peer,
    upsert_food_log_peer_record,
)
from ...application.users.user_use_cases import get_all_users, update_user
from ...const import DATA_BRIZEL, SIGNAL_FIT_STEPS_UPDATED
from ...core.users.brizel_user import BrizelUser, normalize_linked_ha_user_id
from ...domains.body.models.body_measurement_entry import BodyMeasurementEntry
from ...domains.body.models.body_goal import BodyGoal
from ...domains.nutrition.models.food_entry import FoodEntry
from .bridge_responses import bridge_success_response
from .bridge_schemas import (
    BRIDGE_SERVICE_NAME,
    BRIDGE_VERSION,
    ERROR_CONFLICTING_RECORD,
    ERROR_DUPLICATE_RECORD,
    ERROR_AUTH_FAILED,
    ERROR_INTERNAL_ERROR,
    ERROR_INVALID_PAYLOAD,
    ERROR_PROFILE_ACCESS_DENIED,
    ERROR_PROFILE_LINK_AMBIGUOUS,
    ERROR_PROFILE_NOT_LINKED,
    get_capabilities_payload,
    parse_body_goal_peer_request,
    parse_body_measurement_peer_request,
    parse_food_log_peer_request,
    parse_profile_context_sync_request,
    parse_sync_pull_request,
    parse_step_import_request,
    serialize_body_goal_peer_record,
    serialize_body_measurement_peer_record,
    serialize_food_log_peer_record,
    serialize_bridge_profile,
    serialize_bridge_profile_sync_status,
    serialize_step_peer_record,
)

_LOGGER = logging.getLogger(__name__)
_BODY_MEASUREMENT_TYPE_ALIASES = {
    "weight_kg": "weight",
    "body_weight": "weight",
    "height_cm": "height",
}
_ACTIVITY_LEVEL_ALIASES = {
    "sedentary": "sedentary",
    "low": "sedentary",
    "1.2": "sedentary",
    "light": "light",
    "lightly_active": "light",
    "1.375": "light",
    "moderate": "moderate",
    "moderately_active": "moderate",
    "1.55": "moderate",
    "active": "active",
    "high": "active",
    "1.725": "active",
    "very_high": "very_active",
    "very_active": "very_active",
    "extra_active": "very_active",
    "1.9": "very_active",
}


class BridgeRouteNotFoundError(ValueError):
    """Raised when a bridge route is unknown."""


class BridgeDomainError(ValueError):
    """Raised when a valid bridge request cannot be applied."""

    def __init__(
        self,
        *,
        error_code: str,
        message: str,
        field_errors: dict[str, str] | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.field_errors = field_errors or {}
        self.status_code = status_code


class BrizelAppBridgeRouter:
    """Dispatch app bridge requests without mixing transport and domain code."""

    def __init__(self, hass, *, ha_user_id: str | None = None) -> None:
        self._hass = hass
        self._ha_user_id = normalize_linked_ha_user_id(ha_user_id)

    def _user_repository(self):
        """Return the runtime user repository or raise a bridge error."""
        domain_data = self._hass.data.get(DATA_BRIZEL, {})
        user_repository = domain_data.get("user_repository")
        if user_repository is None:
            raise BridgeDomainError(
                error_code=ERROR_INTERNAL_ERROR,
                message="The Brizel profile repository is not available.",
                status_code=500,
            )
        return user_repository

    def _profile_for_authenticated_ha_user(self) -> BrizelUser:
        """Return the one profile linked to the authenticated HA user."""
        if self._ha_user_id is None:
            _LOGGER.warning(
                "App bridge denied request because no authenticated HA user context "
                "was available."
            )
            raise BridgeDomainError(
                error_code=ERROR_AUTH_FAILED,
                message="The authenticated Home Assistant user context is required.",
                status_code=401,
            )

        profiles = [
            profile
            for profile in get_all_users(self._user_repository())
            if profile.linked_ha_user_id == self._ha_user_id
        ]
        if not profiles:
            _LOGGER.warning(
                "App bridge denied request because the authenticated HA user has "
                "no linked Brizel Health profile."
            )
            raise BridgeDomainError(
                error_code=ERROR_PROFILE_NOT_LINKED,
                message=(
                    "No Brizel Health profile is linked to the authenticated "
                    "Home Assistant user."
                ),
                status_code=403,
            )
        if len(profiles) > 1:
            _LOGGER.error(
                "App bridge denied request because multiple Brizel Health profiles "
                "are linked to the authenticated HA user."
            )
            raise BridgeDomainError(
                error_code=ERROR_PROFILE_LINK_AMBIGUOUS,
                message=(
                    "Multiple Brizel Health profiles are linked to the authenticated "
                    "Home Assistant user."
                ),
                status_code=409,
            )

        return profiles[0]

    def handle_ping(self) -> dict[str, object]:
        """Return a basic bridge health response."""
        return bridge_success_response(
            service=BRIDGE_SERVICE_NAME,
            bridge_version=BRIDGE_VERSION,
        )

    def handle_capabilities(self) -> dict[str, object]:
        """Return bridge capabilities for app clients."""
        domain_data = self._hass.data.get(DATA_BRIZEL, {})
        return bridge_success_response(
            **get_capabilities_payload(
                fit_module_available=bool(domain_data.get("step_repository")),
                body_measurement_available=bool(
                    domain_data.get("body_measurement_repository")
                ),
                body_goal_available=bool(domain_data.get("body_goal_repository")),
                food_log_available=bool(domain_data.get("food_entry_repository")),
            )
        )

    def _serialize_effective_profile(
        self,
        *,
        profile: BrizelUser,
        domain_data: dict[str, object],
    ) -> dict[str, object]:
        body_profile_repository = domain_data.get("body_profile_repository")
        body_measurement_repository = domain_data.get("body_measurement_repository")
        body_profile = None
        if body_profile_repository is not None:
            body_profile = get_body_profile(
                repository=body_profile_repository,
                user_repository=self._user_repository(),
                profile_id=profile.user_id,
            )
        latest_height = None
        latest_weight = None
        if body_measurement_repository is not None:
            latest_height = get_latest_measurement(
                repository=body_measurement_repository,
                user_repository=self._user_repository(),
                profile_id=profile.user_id,
                measurement_type="height",
            )
            latest_weight = get_latest_measurement(
                repository=body_measurement_repository,
                user_repository=self._user_repository(),
                profile_id=profile.user_id,
                measurement_type="weight",
            )

        return serialize_bridge_profile(
            profile,
            body_profile=body_profile,
            activity_level=_resolve_effective_activity_level(
                domain_data,
                profile.user_id,
            ),
            height_cm=(
                None
                if latest_height is None
                else latest_height.canonical_value
            ),
            weight_kg=(
                None
                if latest_weight is None
                else latest_weight.canonical_value
            ),
        )

    def handle_profiles(self) -> dict[str, object]:
        """Return the one Brizel profile allowed for this HA user."""
        profile = self._profile_for_authenticated_ha_user()
        domain_data = self._hass.data.get(DATA_BRIZEL, {})
        return bridge_success_response(
            bridge_version=BRIDGE_VERSION,
            profiles=[
                self._serialize_effective_profile(
                    profile=profile,
                    domain_data=domain_data,
                )
            ],
        )

    async def handle_profile_context_sync(self, data: object) -> dict[str, object]:
        """Apply synced stable profile context fields for one linked profile."""
        request = parse_profile_context_sync_request(data)
        profile = self._profile_for_authenticated_ha_user()
        requested_profile_id = self._extract_explicit_profile_id(request, data)
        if (
            requested_profile_id is not None
            and requested_profile_id != profile.user_id
        ):
            raise BridgeDomainError(
                error_code=ERROR_PROFILE_ACCESS_DENIED,
                message=(
                    "The requested profile is not available to the authenticated "
                    "Home Assistant user."
                ),
                field_errors={"profile_id": "not_allowed"},
                status_code=403,
            )

        domain_data = self._hass.data.get(DATA_BRIZEL, {})
        user_repository = self._user_repository()
        body_profile_repository = domain_data.get("body_profile_repository")
        applied: dict[str, bool] = {
            "display_name": False,
            "birth_date": False,
            "sex": False,
            "activity_level": False,
        }

        normalized_display_name = str(request.display_name or "").strip()
        if normalized_display_name and normalized_display_name != profile.display_name:
            await update_user(
                repository=user_repository,
                user_id=profile.user_id,
                display_name=normalized_display_name,
            )
            applied["display_name"] = True

        if body_profile_repository is not None:
            birth_date_value = (
                request.birth_date
                if request.birth_date is not None
                else request.date_of_birth
            )
            if request.sex is not None or birth_date_value is not None:
                await upsert_body_profile(
                    repository=body_profile_repository,
                    user_repository=user_repository,
                    profile_id=profile.user_id,
                    birth_date=birth_date_value,
                    sex=request.sex,
                )
                if birth_date_value is not None:
                    applied["birth_date"] = True
                if request.sex is not None:
                    applied["sex"] = True

        if request.activity_level is not None:
            # Fit remains the owner. This endpoint accepts activity_level as
            # sync input and exposes it in responses when a fit context is
            # available, but does not force a new persistence owner here.
            applied["activity_level"] = False

        refreshed_profile = self._profile_for_authenticated_ha_user()
        serialized_profile = self._serialize_effective_profile(
            profile=refreshed_profile,
            domain_data=domain_data,
        )
        return bridge_success_response(
            bridge_version=BRIDGE_VERSION,
            profile=serialized_profile,
            applied=applied,
            accepted_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        )

    def handle_sync_pull(self, data: object) -> dict[str, object]:
        """Return per-domain record deltas by cursor for one linked profile."""
        request = parse_sync_pull_request(data)
        profile = self._profile_for_authenticated_ha_user()
        requested_profile_id = self._extract_explicit_profile_id(request, data)
        if (
            requested_profile_id is not None
            and requested_profile_id != profile.user_id
        ):
            raise BridgeDomainError(
                error_code=ERROR_PROFILE_ACCESS_DENIED,
                message=(
                    "The requested profile is not available to the authenticated "
                    "Home Assistant user."
                ),
                field_errors={"profile_id": "not_allowed"},
                status_code=403,
            )

        domain_data = self._hass.data.get(DATA_BRIZEL, {})
        pull_steps_after = request.cursors.get("steps")
        pull_measurements_after = request.cursors.get("body_measurements")
        pull_goals_after = request.cursors.get("body_goals")
        pull_food_logs_after = request.cursors.get("food_logs")

        step_repository = domain_data.get("step_repository")
        if step_repository is None:
            raise BridgeDomainError(
                error_code=ERROR_INTERNAL_ERROR,
                message="The Fit step repository is not available.",
                status_code=500,
            )
        all_steps = step_repository.list_step_entries(profile.user_id)
        steps = _records_updated_after(all_steps, pull_steps_after)

        body_measurement_repository = domain_data.get("body_measurement_repository")
        if body_measurement_repository is None:
            raise BridgeDomainError(
                error_code=ERROR_INTERNAL_ERROR,
                message="The Body measurement repository is not available.",
                status_code=500,
            )
        all_measurements = [
            record
            for record in body_measurement_repository.get_by_profile_id(
                profile.user_id,
                include_deleted=True,
            )
            if _normalized_body_measurement_type(
                getattr(record, "measurement_type", "")
            )
            in BODY_MEASUREMENT_PEER_SYNC_TYPES
        ]
        measurements = _records_updated_after(
            all_measurements,
            pull_measurements_after,
        )

        body_goal_repository = domain_data.get("body_goal_repository")
        if body_goal_repository is None:
            raise BridgeDomainError(
                error_code=ERROR_INTERNAL_ERROR,
                message="The Body goal repository is not available.",
                status_code=500,
            )
        all_goals = get_body_goal_target_weight_records_for_peer(
            body_goal_repository,
            profile_id=profile.user_id,
            include_deleted=True,
        )
        goals = _records_updated_after(all_goals, pull_goals_after)

        food_log_repository = domain_data.get("food_entry_repository")
        if food_log_repository is None:
            raise BridgeDomainError(
                error_code=ERROR_INTERNAL_ERROR,
                message="The Food log repository is not available.",
                status_code=500,
            )
        all_food_logs = get_food_log_records_for_peer(
            food_log_repository,
            profile_id=profile.user_id,
            include_deleted=True,
        )
        food_logs = _records_updated_after(all_food_logs, pull_food_logs_after)

        return bridge_success_response(
            bridge_version=BRIDGE_VERSION,
            profile=self._serialize_effective_profile(
                profile=profile,
                domain_data=domain_data,
            ),
            domains={
                "steps": {
                    "latest_updated_at": _latest_updated_at_iso(all_steps),
                    "records": [serialize_step_peer_record(record) for record in steps],
                },
                "body_measurements": {
                    "latest_updated_at": _latest_updated_at_iso(all_measurements),
                    "records": [
                        serialize_body_measurement_peer_record(record)
                        for record in measurements
                    ],
                },
                "body_goals": {
                    "latest_updated_at": _latest_updated_at_iso(all_goals),
                    "records": [
                        serialize_body_goal_peer_record(record) for record in goals
                    ],
                },
                "food_logs": {
                    "latest_updated_at": _latest_updated_at_iso(all_food_logs),
                    "records": [
                        serialize_food_log_peer_record(record) for record in food_logs
                    ],
                },
            },
        )

    def handle_sync_status(self) -> dict[str, object]:
        """Return sync status for the profile allowed for this HA user."""
        domain_data = self._hass.data.get(DATA_BRIZEL, {})
        step_repository = domain_data.get("step_repository")
        if step_repository is None:
            raise BridgeDomainError(
                error_code=ERROR_INTERNAL_ERROR,
                message="The Fit step repository is not available.",
                status_code=500,
            )

        profile = self._profile_for_authenticated_ha_user()
        return bridge_success_response(
            bridge_version=BRIDGE_VERSION,
            profiles=[
                serialize_bridge_profile_sync_status(
                    profile=profile,
                    last_steps_sync=get_last_successful_steps_sync(
                        repository=step_repository,
                        profile_id=profile.user_id,
                    ),
                    last_steps_import_status=get_last_steps_import_status(
                        repository=step_repository,
                        profile_id=profile.user_id,
                    ),
                )
            ],
        )

    def dispatch_get(self, route: str) -> dict[str, object]:
        """Dispatch one GET route by stable bridge route name."""
        if route == "ping":
            return self.handle_ping()
        if route == "capabilities":
            return self.handle_capabilities()
        if route == "profiles":
            return self.handle_profiles()
        if route == "sync_status":
            return self.handle_sync_status()
        if route == "steps":
            return self.handle_steps()
        if route == "body_measurements":
            return self.handle_body_measurements()
        if route == "body_goals":
            return self.handle_body_goals()
        if route == "food_logs":
            return self.handle_food_logs()
        raise BridgeRouteNotFoundError(f"Unknown bridge route '{route}'.")

    @staticmethod
    def _extract_explicit_profile_id(request: object, data: object) -> str | None:
        """Return only an explicitly supplied profile ID; never infer one."""
        profile_id = str(getattr(request, "profile_id", "") or "").strip()
        if profile_id:
            return profile_id

        if not isinstance(data, dict):
            return None

        profile_id = str(data.get("profile_id", "") or "").strip()
        if profile_id:
            return profile_id

        payload = data.get("payload")
        if not isinstance(payload, dict):
            return None

        profile_id = str(payload.get("profile_id", "") or "").strip()
        return profile_id or None

    async def handle_steps_import(self, data: object) -> dict[str, object]:
        """Validate and import one step entry through the Fit application layer."""
        request = parse_step_import_request(data)
        accepted_at = datetime.now(UTC)
        domain_data = self._hass.data.get(DATA_BRIZEL, {})
        repository = domain_data.get("step_repository")
        if repository is None:
            raise BridgeDomainError(
                error_code=ERROR_INTERNAL_ERROR,
                message="The Fit step repository is not available.",
                status_code=500,
            )

        profile = self._profile_for_authenticated_ha_user()
        requested_profile_id = self._extract_explicit_profile_id(request, data)
        if (
            requested_profile_id is not None
            and requested_profile_id != profile.user_id
        ):
            _LOGGER.warning(
                "App bridge denied steps import because the payload profile_id "
                "does not match the authenticated HA user's linked profile."
            )
            raise BridgeDomainError(
                error_code=ERROR_PROFILE_ACCESS_DENIED,
                message=(
                    "The requested profile is not available to the authenticated "
                    "Home Assistant user."
                ),
                field_errors={"payload.profile_id": "not_allowed"},
                status_code=403,
            )

        try:
            result = await import_step_entry(
                repository=repository,
                external_record_id=request.external_record_id,
                profile_id=profile.user_id,
                message_id=request.message_id,
                device_id=request.device_id,
                source=request.source,
                start=request.start,
                end=request.end,
                steps=request.steps,
                received_at=accepted_at,
                timezone=request.timezone,
                record_id=request.record_id,
                record_type=request.record_type,
                origin_node_id=request.origin_node_id,
                source_type=request.source_type,
                source_detail=request.source_detail,
                created_at=request.created_at,
                updated_at=request.updated_at,
                updated_by_node_id=request.updated_by_node_id,
                revision=request.revision,
                payload_version=request.payload_version,
                deleted_at=request.deleted_at,
                read_mode=request.read_mode,
                data_origin=request.data_origin,
            )
        except ConflictingStepRecordError as err:
            raise BridgeDomainError(
                error_code=ERROR_CONFLICTING_RECORD,
                message=str(err),
                field_errors={"payload.external_record_id": "conflicting_record"},
                status_code=409,
            ) from err
        except DuplicateStepMessageError as err:
            raise BridgeDomainError(
                error_code=ERROR_DUPLICATE_RECORD,
                message=str(err),
                field_errors={"message_id": "duplicate_message"},
                status_code=409,
            ) from err

        async_dispatcher_send(
            self._hass,
            SIGNAL_FIT_STEPS_UPDATED,
            {
                "profile_id": result.step_entry.profile_id,
                "result": result.to_result_dict(),
                "accepted_at": accepted_at.isoformat().replace("+00:00", "Z"),
            },
        )

        return bridge_success_response(
            correlation_id=str(uuid4()),
            accepted_at=accepted_at.isoformat().replace("+00:00", "Z"),
            result=result.to_result_dict(),
        )

    def handle_steps(self) -> dict[str, object]:
        """Return raw step CoreRecords for this HA user's linked profile."""
        domain_data = self._hass.data.get(DATA_BRIZEL, {})
        repository = domain_data.get("step_repository")
        if repository is None:
            raise BridgeDomainError(
                error_code=ERROR_INTERNAL_ERROR,
                message="The Fit step repository is not available.",
                status_code=500,
            )

        profile = self._profile_for_authenticated_ha_user()
        records = repository.list_step_entries(profile.user_id)
        return bridge_success_response(
            bridge_version=BRIDGE_VERSION,
            record_type="steps",
            profile_id=profile.user_id,
            records=[serialize_step_peer_record(record) for record in records],
        )

    def handle_body_measurements(self) -> dict[str, object]:
        """Return supported body-measurement CoreRecords for this HA user."""
        domain_data = self._hass.data.get(DATA_BRIZEL, {})
        repository = domain_data.get("body_measurement_repository")
        if repository is None:
            raise BridgeDomainError(
                error_code=ERROR_INTERNAL_ERROR,
                message="The Body measurement repository is not available.",
                status_code=500,
            )

        profile = self._profile_for_authenticated_ha_user()
        records = [
            record
            for record in repository.get_by_profile_id(
                profile.user_id,
                include_deleted=True,
            )
            if _normalized_body_measurement_type(
                getattr(record, "measurement_type", "")
            )
            in BODY_MEASUREMENT_PEER_SYNC_TYPES
        ]
        return bridge_success_response(
            bridge_version=BRIDGE_VERSION,
            record_type="body_measurement",
            measurement_types=sorted(BODY_MEASUREMENT_PEER_SYNC_TYPES),
            profile_id=profile.user_id,
            records=[
                serialize_body_measurement_peer_record(record)
                for record in records
            ],
        )

    async def handle_body_measurement_peer_upsert(
        self,
        data: object,
    ) -> dict[str, object]:
        """Validate and upsert one supported body measurement from a peer app."""
        request = parse_body_measurement_peer_request(data)
        accepted_at = datetime.now(UTC)
        domain_data = self._hass.data.get(DATA_BRIZEL, {})
        repository = domain_data.get("body_measurement_repository")
        if repository is None:
            raise BridgeDomainError(
                error_code=ERROR_INTERNAL_ERROR,
                message="The Body measurement repository is not available.",
                status_code=500,
            )

        profile = self._profile_for_authenticated_ha_user()
        requested_profile_id = self._extract_explicit_profile_id(request, data)
        if (
            requested_profile_id is not None
            and requested_profile_id != profile.user_id
        ):
            _LOGGER.warning(
                "App bridge denied body_measurement peer sync because the "
                "payload profile_id does not match the authenticated HA user's "
                "linked profile."
            )
            raise BridgeDomainError(
                error_code=ERROR_PROFILE_ACCESS_DENIED,
                message=(
                    "The requested profile is not available to the authenticated "
                    "Home Assistant user."
                ),
                field_errors={"profile_id": "not_allowed"},
                status_code=403,
            )

        incoming = BodyMeasurementEntry.from_dict(
            {
                "record_id": request.record_id,
                "record_type": request.record_type,
                "profile_id": profile.user_id,
                "source_type": request.source_type,
                "source_detail": request.source_detail,
                "origin_node_id": request.origin_node_id,
                "created_at": request.created_at.isoformat(),
                "updated_at": request.updated_at.isoformat(),
                "updated_by_node_id": request.updated_by_node_id,
                "revision": request.revision,
                "payload_version": request.payload_version,
                "deleted_at": (
                    None
                    if request.deleted_at is None
                    else request.deleted_at.isoformat()
                ),
                "measurement_type": request.measurement_type,
                "canonical_value": request.canonical_value,
                "measured_at": request.measured_at.isoformat(),
                "note": request.note,
            }
        )
        try:
            result = await upsert_body_measurement_peer_record(
                repository,
                incoming=incoming,
            )
        except ValueError as err:
            raise BridgeDomainError(
                error_code=ERROR_INVALID_PAYLOAD,
                message=str(err),
                field_errors={"record_id": "invalid_for_profile"},
                status_code=409,
            ) from err

        return bridge_success_response(
            correlation_id=str(uuid4()),
            accepted_at=accepted_at.isoformat().replace("+00:00", "Z"),
            record=serialize_body_measurement_peer_record(result.measurement),
            result=result.to_result_dict(),
        )

    def handle_body_goals(self) -> dict[str, object]:
        """Return target-weight body-goal CoreRecords for this HA user."""
        domain_data = self._hass.data.get(DATA_BRIZEL, {})
        repository = domain_data.get("body_goal_repository")
        if repository is None:
            raise BridgeDomainError(
                error_code=ERROR_INTERNAL_ERROR,
                message="The Body goal repository is not available.",
                status_code=500,
            )

        profile = self._profile_for_authenticated_ha_user()
        records = get_body_goal_target_weight_records_for_peer(
            repository,
            profile_id=profile.user_id,
            include_deleted=True,
        )
        return bridge_success_response(
            bridge_version=BRIDGE_VERSION,
            record_type="body_goal",
            goal_type="target_weight",
            profile_id=profile.user_id,
            records=[serialize_body_goal_peer_record(record) for record in records],
        )

    async def handle_body_goal_peer_upsert(
        self,
        data: object,
    ) -> dict[str, object]:
        """Validate and upsert one target-weight body goal from a peer app."""
        request = parse_body_goal_peer_request(data)
        accepted_at = datetime.now(UTC)
        domain_data = self._hass.data.get(DATA_BRIZEL, {})
        repository = domain_data.get("body_goal_repository")
        if repository is None:
            raise BridgeDomainError(
                error_code=ERROR_INTERNAL_ERROR,
                message="The Body goal repository is not available.",
                status_code=500,
            )

        profile = self._profile_for_authenticated_ha_user()
        requested_profile_id = self._extract_explicit_profile_id(request, data)
        if (
            requested_profile_id is not None
            and requested_profile_id != profile.user_id
        ):
            _LOGGER.warning(
                "App bridge denied body_goal peer sync because the payload "
                "profile_id does not match the authenticated HA user's linked "
                "profile."
            )
            raise BridgeDomainError(
                error_code=ERROR_PROFILE_ACCESS_DENIED,
                message=(
                    "The requested profile is not available to the authenticated "
                    "Home Assistant user."
                ),
                field_errors={"profile_id": "not_allowed"},
                status_code=403,
            )

        incoming = BodyGoal.from_dict(
            {
                "record_id": request.record_id,
                "record_type": request.record_type,
                "profile_id": profile.user_id,
                "source_type": request.source_type,
                "source_detail": request.source_detail,
                "origin_node_id": request.origin_node_id,
                "created_at": request.created_at.isoformat(),
                "updated_at": request.updated_at.isoformat(),
                "updated_by_node_id": request.updated_by_node_id,
                "revision": request.revision,
                "payload_version": request.payload_version,
                "deleted_at": (
                    None
                    if request.deleted_at is None
                    else request.deleted_at.isoformat()
                ),
                "goal_type": request.goal_type,
                "target_value": request.target_value,
                "note": request.note,
            }
        )
        try:
            result = await upsert_body_goal_target_weight_peer_record(
                repository,
                incoming=incoming,
            )
        except ValueError as err:
            raise BridgeDomainError(
                error_code=ERROR_INVALID_PAYLOAD,
                message=str(err),
                field_errors={"record_id": "invalid_for_profile"},
                status_code=409,
            ) from err

        return bridge_success_response(
            correlation_id=str(uuid4()),
            accepted_at=accepted_at.isoformat().replace("+00:00", "Z"),
            record=serialize_body_goal_peer_record(result.goal),
            result=result.to_result_dict(),
        )

    def handle_food_logs(self) -> dict[str, object]:
        """Return food_log CoreRecords for this HA user's linked profile."""
        domain_data = self._hass.data.get(DATA_BRIZEL, {})
        repository = domain_data.get("food_entry_repository")
        if repository is None:
            raise BridgeDomainError(
                error_code=ERROR_INTERNAL_ERROR,
                message="The Food log repository is not available.",
                status_code=500,
            )

        profile = self._profile_for_authenticated_ha_user()
        records = get_food_log_records_for_peer(
            repository,
            profile_id=profile.user_id,
            include_deleted=True,
        )
        return bridge_success_response(
            bridge_version=BRIDGE_VERSION,
            record_type="food_log",
            profile_id=profile.user_id,
            records=[serialize_food_log_peer_record(record) for record in records],
        )

    async def handle_food_log_peer_upsert(
        self,
        data: object,
    ) -> dict[str, object]:
        """Validate and upsert one food_log record from a peer app."""
        request = parse_food_log_peer_request(data)
        accepted_at = datetime.now(UTC)
        domain_data = self._hass.data.get(DATA_BRIZEL, {})
        repository = domain_data.get("food_entry_repository")
        if repository is None:
            raise BridgeDomainError(
                error_code=ERROR_INTERNAL_ERROR,
                message="The Food log repository is not available.",
                status_code=500,
            )

        profile = self._profile_for_authenticated_ha_user()
        requested_profile_id = self._extract_explicit_profile_id(request, data)
        if (
            requested_profile_id is not None
            and requested_profile_id != profile.user_id
        ):
            _LOGGER.warning(
                "App bridge denied food_log peer sync because the payload "
                "profile_id does not match the authenticated HA user's linked "
                "profile."
            )
            raise BridgeDomainError(
                error_code=ERROR_PROFILE_ACCESS_DENIED,
                message=(
                    "The requested profile is not available to the authenticated "
                    "Home Assistant user."
                ),
                field_errors={"profile_id": "not_allowed"},
                status_code=403,
            )

        incoming = FoodEntry.from_dict(
            {
                "record_id": request.record_id,
                "record_type": request.record_type,
                "profile_id": profile.user_id,
                "source_type": request.source_type,
                "source_detail": request.source_detail,
                "origin_node_id": request.origin_node_id,
                "created_at": request.created_at.isoformat(),
                "updated_at": request.updated_at.isoformat(),
                "updated_by_node_id": request.updated_by_node_id,
                "revision": request.revision,
                "payload_version": request.payload_version,
                "deleted_at": (
                    None
                    if request.deleted_at is None
                    else request.deleted_at.isoformat()
                ),
                "food_id": request.food_id,
                "food_name": request.food_name,
                "food_brand": request.food_brand,
                "amount_grams": request.amount_grams,
                "meal_type": request.meal_type,
                "note": request.note,
                "consumed_at": request.consumed_at.isoformat(),
                "kcal": request.kcal,
                "protein": request.protein,
                "carbs": request.carbs,
                "fat": request.fat,
            }
        )
        try:
            result = await upsert_food_log_peer_record(
                repository,
                incoming=incoming,
            )
        except ValueError as err:
            raise BridgeDomainError(
                error_code=ERROR_INVALID_PAYLOAD,
                message=str(err),
                field_errors={"record_id": "invalid_for_profile"},
                status_code=409,
            ) from err

        return bridge_success_response(
            correlation_id=str(uuid4()),
            accepted_at=accepted_at.isoformat().replace("+00:00", "Z"),
            record=serialize_food_log_peer_record(result.food_log),
            result=result.to_result_dict(),
        )

    async def dispatch_post(self, route: str, data: object) -> dict[str, object]:
        """Dispatch one POST route by stable bridge route name."""
        if route == "steps":
            return await self.handle_steps_import(data)
        if route == "profile_context":
            return await self.handle_profile_context_sync(data)
        if route == "sync_pull":
            return self.handle_sync_pull(data)
        if route == "body_measurements":
            return await self.handle_body_measurement_peer_upsert(data)
        if route == "body_goals":
            return await self.handle_body_goal_peer_upsert(data)
        if route == "food_logs":
            return await self.handle_food_log_peer_upsert(data)
        raise BridgeRouteNotFoundError(f"Unknown bridge route '{route}'.")


def _record_updated_at(record: object) -> datetime | None:
    raw_value = getattr(record, "updated_at", None)
    if raw_value is None:
        return None
    if isinstance(raw_value, datetime):
        return raw_value if raw_value.tzinfo is not None else raw_value.replace(tzinfo=UTC)
    text_value = str(raw_value).strip()
    if not text_value:
        return None
    try:
        parsed = datetime.fromisoformat(text_value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _records_updated_after(
    records: list[object],
    updated_after: datetime | None,
) -> list[object]:
    if updated_after is None:
        return list(records)
    filtered: list[object] = []
    for record in records:
        record_updated_at = _record_updated_at(record)
        if record_updated_at is None:
            continue
        if record_updated_at > updated_after:
            filtered.append(record)
    return filtered


def _latest_updated_at_iso(records: list[object]) -> str | None:
    latest: datetime | None = None
    for record in records:
        record_updated_at = _record_updated_at(record)
        if record_updated_at is None:
            continue
        if latest is None or record_updated_at > latest:
            latest = record_updated_at
    if latest is None:
        return None
    return latest.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _normalized_body_measurement_type(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return ""
    return _BODY_MEASUREMENT_TYPE_ALIASES.get(normalized, normalized)


def _normalize_activity_level(value: object) -> str | None:
    """Normalize activity aliases into the HA body-target vocabulary."""
    normalized = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not normalized:
        return None
    return _ACTIVITY_LEVEL_ALIASES.get(normalized.replace(",", "."))


def _resolve_fit_activity_level(
    domain_data: dict[str, object],
    profile_id: str,
) -> str | None:
    """Best-effort Fit-owned activity context without making Profile the owner."""
    for key in ("fit_profile_repository", "activity_profile_repository"):
        repository = domain_data.get(key)
        if repository is None:
            continue
        for method_name in ("get_by_profile_id", "get_profile", "get"):
            method = getattr(repository, method_name, None)
            if method is None:
                continue
            try:
                fit_profile = method(profile_id)
            except TypeError:
                continue
            activity_level = str(
                getattr(fit_profile, "activity_level", "") or ""
            ).strip()
            normalized_activity_level = _normalize_activity_level(activity_level)
            if normalized_activity_level:
                return normalized_activity_level
    return None


def _resolve_effective_activity_level(
    domain_data: dict[str, object],
    profile_id: str,
) -> str | None:
    """Return Fit-owned activity level for the app bridge read model."""
    return _resolve_fit_activity_level(domain_data, profile_id)
