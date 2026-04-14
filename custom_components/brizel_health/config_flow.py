"""Config and options flow for Brizel Health."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .adapters.homeassistant.source_configuration import (
    SOURCE_OPTION_API_KEY,
    SOURCE_OPTION_ENABLED,
    SOURCE_OPTION_PRIORITY,
    SOURCE_OPTIONS_KEY,
    get_default_food_source_options,
)
from .application.body.body_profile_use_cases import (
    get_body_profile,
    upsert_body_profile,
)
from .application.nutrition.search_context import build_food_search_context
from .application.users.user_use_cases import (
    create_user,
    delete_user,
    get_all_users,
    get_user,
    update_user_linked_ha_user_id,
    update_user,
)
from .const import (
    DATA_BRIZEL,
    DOMAIN,
    NAME,
    SIGNAL_BODY_PROFILE_UPDATED,
    SIGNAL_PROFILE_CREATED,
    SIGNAL_PROFILE_DELETED,
    SIGNAL_PROFILE_UPDATED,
)
from .core.users.brizel_user import (
    PREFERRED_LANGUAGE_DE,
    PREFERRED_LANGUAGE_EN,
    PREFERRED_REGION_EU,
    PREFERRED_REGION_GERMANY,
    PREFERRED_REGION_GLOBAL,
    PREFERRED_REGION_USA,
    PREFERRED_UNITS_IMPERIAL,
    PREFERRED_UNITS_METRIC,
)
from .domains.body.errors import BrizelBodyProfileValidationError
from .domains.body.models.body_profile import (
    ACTIVITY_LEVEL_ACTIVE,
    ACTIVITY_LEVEL_LIGHT,
    ACTIVITY_LEVEL_MODERATE,
    ACTIVITY_LEVEL_SEDENTARY,
    ACTIVITY_LEVEL_VERY_ACTIVE,
    SEX_FEMALE,
    SEX_MALE,
)
from .core.users.errors import (
    BrizelUserAlreadyExistsError,
    BrizelUserNotFoundError,
    BrizelUserValidationError,
)

ACTION_ADD_PROFILE = "add_profile"
ACTION_EDIT_PROFILE = "edit_profile"
ACTION_DELETE_PROFILE = "delete_profile"
ACTION_EDIT_BODY_PROFILE = "edit_body_profile"
ACTION_LINK_HA_USER = "link_ha_user"
ACTION_CONFIGURE_FOOD_SOURCES = "configure_food_sources"

_SEX_CHOICES = {
    "": "Not set",
    SEX_FEMALE: "Female",
    SEX_MALE: "Male",
}
_ACTIVITY_LEVEL_CHOICES = {
    "": "Not set",
    ACTIVITY_LEVEL_SEDENTARY: "Sedentary",
    ACTIVITY_LEVEL_LIGHT: "Light",
    ACTIVITY_LEVEL_MODERATE: "Moderate",
    ACTIVITY_LEVEL_ACTIVE: "Active",
    ACTIVITY_LEVEL_VERY_ACTIVE: "Very active",
}
_PREFERRED_LANGUAGE_CHOICES = {
    "": "Automatic (Home Assistant default)",
    PREFERRED_LANGUAGE_DE: "Deutsch",
    PREFERRED_LANGUAGE_EN: "English",
}
_PREFERRED_REGION_CHOICES = {
    "": "Automatic (Home Assistant default)",
    PREFERRED_REGION_GERMANY: "Germany",
    PREFERRED_REGION_EU: "EU",
    PREFERRED_REGION_USA: "USA",
    PREFERRED_REGION_GLOBAL: "Global",
}
_PREFERRED_UNITS_CHOICES = {
    "": "Automatic (Home Assistant default)",
    PREFERRED_UNITS_METRIC: "Metric",
    PREFERRED_UNITS_IMPERIAL: "Imperial",
}


def _options_result(config_entry: config_entries.ConfigEntry) -> dict[str, Any]:
    """Return a stable options payload when the options flow closes."""
    return dict(config_entry.options)


class BrizelHealthConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Brizel Health."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> BrizelHealthOptionsFlow:
        """Create the options flow."""
        return BrizelHealthOptionsFlow(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, object] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Create the single supported integration entry."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title=NAME, data={})


class BrizelHealthOptionsFlow(config_entries.OptionsFlow):
    """Manage Brizel Health profiles through the HA options UI."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow."""
        self._config_entry = config_entry
        self._selected_profile_id: str | None = None

    def _domain_data(self) -> dict[str, Any] | None:
        """Return integration runtime data when the entry is loaded."""
        return self.hass.data.get(DATA_BRIZEL)

    def _user_repository(self):
        """Return the runtime user repository."""
        domain_data = self._domain_data()
        if domain_data is None:
            return None
        return domain_data.get("user_repository")

    def _body_profile_repository(self):
        """Return the runtime body profile repository."""
        domain_data = self._domain_data()
        if domain_data is None:
            return None
        return domain_data.get("body_profile_repository")

    def _profiles_by_id(self) -> dict[str, Any]:
        """Return current profiles keyed by profile ID."""
        repository = self._user_repository()
        if repository is None:
            return {}

        return {user.user_id: user for user in get_all_users(repository)}

    def _profile_choices(self) -> dict[str, str]:
        """Return profile choices for dropdowns."""
        return {
            profile_id: profile.display_name
            for profile_id, profile in sorted(
                self._profiles_by_id().items(),
                key=lambda item: (
                    item[1].display_name.casefold(),
                    item[0],
                ),
            )
        }

    async def _ha_user_choices(
        self,
        current_linked_ha_user_id: str | None = None,
    ) -> dict[str, str]:
        """Return selectable Home Assistant users for profile linking."""
        choices: dict[str, str] = {"": "Not linked"}
        users = await self.hass.auth.async_get_users()
        collected_choices: list[tuple[str, str]] = []
        known_user_ids: set[str] = set()

        for user in users:
            if getattr(user, "system_generated", False):
                continue
            if getattr(user, "is_active", True) is False:
                continue

            user_id = str(getattr(user, "id", "")).strip()
            if not user_id:
                continue

            display_name = str(getattr(user, "name", "")).strip() or user_id
            collected_choices.append((user_id, display_name))
            known_user_ids.add(user_id)

        if (
            current_linked_ha_user_id is not None
            and current_linked_ha_user_id not in known_user_ids
        ):
            collected_choices.append(
                (
                    current_linked_ha_user_id,
                    f"Unavailable ({current_linked_ha_user_id})",
                )
            )

        for user_id, display_name in sorted(
            collected_choices,
            key=lambda item: (item[1].casefold(), item[0]),
        ):
            choices[user_id] = display_name

        return choices

    def _refresh_profile_cache(self) -> None:
        """Refresh the runtime profile cache mirror."""
        domain_data = self._domain_data()
        if domain_data is None:
            return

        storage = domain_data.get("storage")
        if storage is not None:
            domain_data["profiles"] = storage.data.get("profiles", {})

    def _updated_options(self, **changes: Any) -> dict[str, Any]:
        """Return one updated options mapping."""
        updated = dict(self._config_entry.options)
        updated.update(changes)
        return updated

    def _source_options(self) -> dict[str, dict[str, int | bool | str]]:
        """Return merged source options with defaults."""
        merged = get_default_food_source_options()
        configured = self._config_entry.options.get(SOURCE_OPTIONS_KEY, {})
        if not isinstance(configured, dict):
            return merged

        for source_name, raw_options in configured.items():
            if source_name not in merged or not isinstance(raw_options, dict):
                continue
            merged[source_name].update(raw_options)

        return merged

    def _emit_profile_signal(self, signal: str, profile_id: str) -> None:
        """Emit one profile dispatcher signal with the latest profile shape."""
        repository = self._user_repository()
        if repository is None:
            return

        payload: dict[str, Any]
        if signal == SIGNAL_PROFILE_DELETED:
            payload = {"profile": {"profile_id": profile_id}}
        else:
            user = get_user(repository, profile_id)
            payload = {"profile": user.to_dict()}

        async_dispatcher_send(self.hass, signal, payload)

    def _emit_body_profile_signal(self, profile_id: str) -> None:
        """Emit one dispatcher signal for updated body profile data."""
        async_dispatcher_send(
            self.hass,
            SIGNAL_BODY_PROFILE_UPDATED,
            {"profile_id": profile_id},
        )

    @staticmethod
    def _normalize_optional_int(
        user_input: dict[str, Any],
        key: str,
    ) -> int | None:
        """Normalize an optional integer flow value."""
        value = user_input.get(key)
        if value is None:
            return None
        normalized_value = str(value).strip()
        if not normalized_value:
            return None
        try:
            return int(normalized_value)
        except ValueError as err:
            raise ValueError(key) from err

    @staticmethod
    def _normalize_optional_float(
        user_input: dict[str, Any],
        key: str,
    ) -> float | None:
        """Normalize an optional float flow value."""
        value = user_input.get(key)
        if value is None:
            return None
        normalized_value = str(value).strip()
        if not normalized_value:
            return None
        try:
            return float(normalized_value)
        except ValueError as err:
            raise ValueError(key) from err

    @staticmethod
    def _normalize_optional_choice(
        user_input: dict[str, Any],
        key: str,
    ) -> str | None:
        """Normalize an optional choice value."""
        value = user_input.get(key)
        if value is None:
            return None
        normalized_value = str(value).strip()
        if not normalized_value:
            return None
        return normalized_value

    @staticmethod
    def _body_profile_errors_from_exception(
        err: BrizelBodyProfileValidationError,
    ) -> dict[str, str]:
        """Map body validation errors to flow field errors."""
        message = str(err)
        if "age_years" in message:
            return {"age_years": "invalid_age"}
        if "height_cm" in message:
            return {"height_cm": "invalid_height"}
        if "weight_kg" in message:
            return {"weight_kg": "invalid_weight"}
        if "sex" in message:
            return {"sex": "invalid_sex"}
        if "activity_level" in message:
            return {"activity_level": "invalid_activity_level"}
        return {"base": "invalid_body_profile"}

    @staticmethod
    def _profile_errors_from_exception(
        err: BrizelUserValidationError,
    ) -> dict[str, str]:
        """Map profile validation errors to flow field errors."""
        message = str(err)
        if "preferred_language" in message:
            return {"preferred_language": "invalid_preferred_language"}
        if "preferred_region" in message:
            return {"preferred_region": "invalid_preferred_region"}
        if "preferred_units" in message:
            return {"preferred_units": "invalid_preferred_units"}
        return {"display_name": "invalid_name"}

    def _body_profile_schema(self) -> vol.Schema:
        """Return the editable form schema for per-profile body data."""
        return vol.Schema(
            {
                vol.Optional("age_years"): str,
                vol.Optional("sex"): vol.In(_SEX_CHOICES),
                vol.Optional("height_cm"): str,
                vol.Optional("weight_kg"): str,
                vol.Optional("activity_level"): vol.In(_ACTIVITY_LEVEL_CHOICES),
            }
        )

    def _profile_schema(self) -> vol.Schema:
        """Return the editable form schema for one profile."""
        return vol.Schema(
            {
                vol.Required("display_name"): str,
                vol.Optional("preferred_language"): vol.In(
                    _PREFERRED_LANGUAGE_CHOICES
                ),
                vol.Optional("preferred_region"): vol.In(_PREFERRED_REGION_CHOICES),
                vol.Optional("preferred_units"): vol.In(_PREFERRED_UNITS_CHOICES),
            }
        )

    def _hass_units_hint(self) -> str | None:
        """Return one conservative unit hint from Home Assistant."""
        units = getattr(self.hass.config, "units", None)
        if units is None:
            return None

        explicit_name = str(getattr(units, "name", "")).strip()
        if explicit_name:
            return explicit_name

        normalized = str(units).strip()
        return normalized or None

    def _default_search_preference_values(self) -> dict[str, Any]:
        """Return initial search-preference defaults from Home Assistant hints."""
        context = build_food_search_context(
            profile_id=None,
            profile=None,
            hass_language=getattr(self.hass.config, "language", None),
            hass_time_zone=getattr(self.hass.config, "time_zone", None),
            hass_country=getattr(self.hass.config, "country", None),
            hass_units_hint=self._hass_units_hint(),
            recent_foods=None,
        )
        return {
            "preferred_language": context.preferred_language,
            "preferred_region": context.preferred_region,
            "preferred_units": context.preferred_units,
        }

    def _profile_suggested_values(
        self,
        *,
        display_name: str = "",
        preferred_language: str | None = None,
        preferred_region: str | None = None,
        preferred_units: str | None = None,
        use_ha_defaults: bool = False,
    ) -> dict[str, Any]:
        """Return stable suggested values for one profile form."""
        defaults = (
            self._default_search_preference_values()
            if use_ha_defaults
            else {
                "preferred_language": "",
                "preferred_region": "",
                "preferred_units": "",
            }
        )
        return {
            "display_name": display_name,
            "preferred_language": preferred_language or defaults["preferred_language"],
            "preferred_region": preferred_region or defaults["preferred_region"],
            "preferred_units": preferred_units or defaults["preferred_units"],
        }

    @staticmethod
    def _body_profile_suggested_values(body_profile) -> dict[str, Any]:
        """Return stable suggested values for the body profile form."""
        return {
            "age_years": (
                "" if body_profile.age_years is None else str(body_profile.age_years)
            ),
            "sex": body_profile.sex or "",
            "height_cm": (
                "" if body_profile.height_cm is None else str(body_profile.height_cm)
            ),
            "weight_kg": (
                "" if body_profile.weight_kg is None else str(body_profile.weight_kg)
            ),
            "activity_level": body_profile.activity_level or "",
        }

    def _food_source_schema(self) -> vol.Schema:
        """Return the editable form schema for source configuration."""
        return vol.Schema(
            {
                vol.Required("bls_enabled", default=True): bool,
                vol.Optional("bls_priority"): str,
                vol.Required("usda_enabled", default=False): bool,
                vol.Optional("usda_api_key"): str,
                vol.Optional("usda_priority"): str,
                vol.Required("open_food_facts_enabled", default=True): bool,
                vol.Optional("open_food_facts_priority"): str,
            }
        )

    def _food_source_suggested_values(self) -> dict[str, Any]:
        """Return stable suggested values for the source configuration form."""
        source_options = self._source_options()
        bls_options = source_options["bls"]
        usda_options = source_options["usda"]
        off_options = source_options["open_food_facts"]
        return {
            "bls_enabled": bool(bls_options[SOURCE_OPTION_ENABLED]),
            "bls_priority": str(bls_options[SOURCE_OPTION_PRIORITY]),
            "usda_enabled": bool(usda_options[SOURCE_OPTION_ENABLED]),
            "usda_api_key": str(usda_options.get(SOURCE_OPTION_API_KEY, "")),
            "usda_priority": str(usda_options[SOURCE_OPTION_PRIORITY]),
            "open_food_facts_enabled": bool(off_options[SOURCE_OPTION_ENABLED]),
            "open_food_facts_priority": str(off_options[SOURCE_OPTION_PRIORITY]),
        }

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Show the profile management entry point."""
        if self._user_repository() is None:
            return self.async_abort(reason="integration_not_loaded")

        return self.async_show_menu(
            step_id="init",
            menu_options=[
                ACTION_ADD_PROFILE,
                ACTION_EDIT_PROFILE,
                ACTION_DELETE_PROFILE,
                ACTION_EDIT_BODY_PROFILE,
                ACTION_LINK_HA_USER,
                ACTION_CONFIGURE_FOOD_SOURCES,
            ],
        )

    async def async_step_add_profile(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Create a new profile."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                created_user = await create_user(
                    repository=self._user_repository(),
                    display_name=user_input["display_name"],
                    preferred_language=self._normalize_optional_choice(
                        user_input,
                        "preferred_language",
                    ),
                    preferred_region=self._normalize_optional_choice(
                        user_input,
                        "preferred_region",
                    ),
                    preferred_units=self._normalize_optional_choice(
                        user_input,
                        "preferred_units",
                    ),
                )
            except BrizelUserAlreadyExistsError:
                errors["display_name"] = "already_exists"
            except BrizelUserValidationError as err:
                errors.update(self._profile_errors_from_exception(err))
            else:
                self._refresh_profile_cache()
                self._emit_profile_signal(
                    SIGNAL_PROFILE_CREATED,
                    created_user.user_id,
                )
                return self.async_create_entry(
                    title="",
                    data=_options_result(self._config_entry),
                )

        return self.async_show_form(
            step_id="add_profile",
            data_schema=self.add_suggested_values_to_schema(
                self._profile_schema(),
                self._profile_suggested_values(use_ha_defaults=True),
            ),
            errors=errors,
        )

    async def async_step_edit_profile(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Edit an existing profile."""
        repository = self._user_repository()
        if repository is None:
            return self.async_abort(reason="integration_not_loaded")

        if self._selected_profile_id is None:
            return await self.async_step_edit_profile_select()

        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                updated_user = await update_user(
                    repository=repository,
                    user_id=self._selected_profile_id,
                    display_name=user_input["display_name"],
                    preferred_language=self._normalize_optional_choice(
                        user_input,
                        "preferred_language",
                    ),
                    preferred_region=self._normalize_optional_choice(
                        user_input,
                        "preferred_region",
                    ),
                    preferred_units=self._normalize_optional_choice(
                        user_input,
                        "preferred_units",
                    ),
                )
            except BrizelUserAlreadyExistsError:
                errors["display_name"] = "already_exists"
            except BrizelUserValidationError as err:
                errors.update(self._profile_errors_from_exception(err))
            except BrizelUserNotFoundError:
                errors["base"] = "profile_not_found"
            else:
                self._refresh_profile_cache()
                self._emit_profile_signal(
                    SIGNAL_PROFILE_UPDATED,
                    updated_user.user_id,
                )
                return self.async_create_entry(
                    title="",
                    data=_options_result(self._config_entry),
                )

        try:
            profile = get_user(repository, self._selected_profile_id)
        except (BrizelUserNotFoundError, BrizelUserValidationError):
            return self.async_abort(reason="profile_not_found")

        return self.async_show_form(
            step_id="edit_profile",
            data_schema=self.add_suggested_values_to_schema(
                self._profile_schema(),
                self._profile_suggested_values(
                    display_name=profile.display_name,
                    preferred_language=profile.preferred_language,
                    preferred_region=profile.preferred_region,
                    preferred_units=profile.preferred_units,
                ),
            ),
            errors=errors,
        )

    async def async_step_edit_profile_select(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Select which profile should be edited."""
        choices = self._profile_choices()
        if not choices:
            return self.async_abort(reason="no_profiles_available")

        if user_input is not None:
            self._selected_profile_id = user_input["profile_id"]
            return await self.async_step_edit_profile()

        return self.async_show_form(
            step_id="edit_profile_select",
            data_schema=vol.Schema(
                {
                    vol.Required("profile_id"): vol.In(choices),
                }
            ),
        )

    async def async_step_delete_profile(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Delete an existing profile after confirmation."""
        repository = self._user_repository()
        if repository is None:
            return self.async_abort(reason="integration_not_loaded")

        if self._selected_profile_id is None:
            return await self.async_step_delete_profile_select()

        try:
            profile = get_user(repository, self._selected_profile_id)
        except (BrizelUserNotFoundError, BrizelUserValidationError):
            return self.async_abort(reason="profile_not_found")

        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input["confirm"]:
                errors["base"] = "confirmation_required"
            else:
                try:
                    deleted_user = await delete_user(
                        repository=repository,
                        user_id=self._selected_profile_id,
                    )
                except BrizelUserNotFoundError:
                    errors["base"] = "profile_not_found"
                except BrizelUserValidationError:
                    errors["base"] = "invalid_name"
                else:
                    self._refresh_profile_cache()
                    async_dispatcher_send(
                        self.hass,
                        SIGNAL_PROFILE_DELETED,
                        {"profile": deleted_user.to_dict()},
                    )
                    return self.async_create_entry(
                        title="",
                        data=_options_result(self._config_entry),
                    )

        return self.async_show_form(
            step_id="delete_profile",
            data_schema=vol.Schema(
                {
                    vol.Required("confirm", default=False): bool,
                }
            ),
            errors=errors,
            description_placeholders={"profile_name": profile.display_name},
        )

    async def async_step_delete_profile_select(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Select which profile should be deleted."""
        choices = self._profile_choices()
        if not choices:
            return self.async_abort(reason="no_profiles_available")

        if user_input is not None:
            self._selected_profile_id = user_input["profile_id"]
            return await self.async_step_delete_profile()

        return self.async_show_form(
            step_id="delete_profile_select",
            data_schema=vol.Schema(
                {
                    vol.Required("profile_id"): vol.In(choices),
                }
            ),
        )

    async def async_step_edit_body_profile(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Edit body data for an existing profile."""
        user_repository = self._user_repository()
        body_profile_repository = self._body_profile_repository()
        if user_repository is None or body_profile_repository is None:
            return self.async_abort(reason="integration_not_loaded")

        if self._selected_profile_id is None:
            return await self.async_step_edit_body_profile_select()

        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                updated_profile = await upsert_body_profile(
                    repository=body_profile_repository,
                    user_repository=user_repository,
                    profile_id=self._selected_profile_id,
                    age_years=self._normalize_optional_int(user_input, "age_years"),
                    sex=self._normalize_optional_choice(user_input, "sex"),
                    height_cm=self._normalize_optional_float(user_input, "height_cm"),
                    weight_kg=self._normalize_optional_float(user_input, "weight_kg"),
                    activity_level=self._normalize_optional_choice(
                        user_input,
                        "activity_level",
                    ),
                )
            except ValueError as err:
                if "age_years" in str(err):
                    errors["age_years"] = "invalid_age"
                elif "height_cm" in str(err):
                    errors["height_cm"] = "invalid_height"
                elif "weight_kg" in str(err):
                    errors["weight_kg"] = "invalid_weight"
                else:
                    errors["base"] = "invalid_body_profile"
            except BrizelBodyProfileValidationError as err:
                errors.update(self._body_profile_errors_from_exception(err))
            except (BrizelUserNotFoundError, BrizelUserValidationError):
                errors["base"] = "profile_not_found"
            else:
                self._emit_body_profile_signal(updated_profile.profile_id)
                return self.async_create_entry(
                    title="",
                    data=_options_result(self._config_entry),
                )

        try:
            body_profile = get_body_profile(
                repository=body_profile_repository,
                user_repository=user_repository,
                profile_id=self._selected_profile_id,
            )
            profile = get_user(user_repository, self._selected_profile_id)
        except (BrizelUserNotFoundError, BrizelUserValidationError):
            return self.async_abort(reason="profile_not_found")

        return self.async_show_form(
            step_id="edit_body_profile",
            data_schema=self.add_suggested_values_to_schema(
                self._body_profile_schema(),
                self._body_profile_suggested_values(body_profile),
            ),
            errors=errors,
            description_placeholders={"profile_name": profile.display_name},
        )

    async def async_step_edit_body_profile_select(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Select which profile should receive body data updates."""
        choices = self._profile_choices()
        if not choices:
            return self.async_abort(reason="no_profiles_available")

        if user_input is not None:
            self._selected_profile_id = user_input["profile_id"]
            return await self.async_step_edit_body_profile()

        return self.async_show_form(
            step_id="edit_body_profile_select",
            data_schema=vol.Schema(
                {
                    vol.Required("profile_id"): vol.In(choices),
                }
            ),
        )

    async def async_step_link_ha_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Link or unlink one profile to one Home Assistant user."""
        repository = self._user_repository()
        if repository is None:
            return self.async_abort(reason="integration_not_loaded")

        if self._selected_profile_id is None:
            return await self.async_step_link_ha_user_select()

        try:
            profile = get_user(repository, self._selected_profile_id)
        except (BrizelUserNotFoundError, BrizelUserValidationError):
            return self.async_abort(reason="profile_not_found")

        choices = await self._ha_user_choices(profile.linked_ha_user_id)
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                updated_user = await update_user_linked_ha_user_id(
                    repository=repository,
                    user_id=self._selected_profile_id,
                    linked_ha_user_id=user_input.get("linked_ha_user_id"),
                )
            except BrizelUserAlreadyExistsError:
                errors["linked_ha_user_id"] = "ha_user_already_linked"
            except (BrizelUserNotFoundError, BrizelUserValidationError):
                errors["base"] = "profile_not_found"
            else:
                self._refresh_profile_cache()
                self._emit_profile_signal(
                    SIGNAL_PROFILE_UPDATED,
                    updated_user.user_id,
                )
                return self.async_create_entry(
                    title="",
                    data=_options_result(self._config_entry),
                )

        return self.async_show_form(
            step_id="link_ha_user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required("linked_ha_user_id"): vol.In(choices),
                    }
                ),
                {"linked_ha_user_id": profile.linked_ha_user_id or ""},
            ),
            errors=errors,
            description_placeholders={"profile_name": profile.display_name},
        )

    async def async_step_link_ha_user_select(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Select which profile should be linked to one HA user."""
        choices = self._profile_choices()
        if not choices:
            return self.async_abort(reason="no_profiles_available")

        if user_input is not None:
            self._selected_profile_id = user_input["profile_id"]
            return await self.async_step_link_ha_user()

        return self.async_show_form(
            step_id="link_ha_user_select",
            data_schema=vol.Schema(
                {
                    vol.Required("profile_id"): vol.In(choices),
                }
            ),
        )

    async def async_step_configure_food_sources(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Edit source configuration for live external food sources."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                bls_priority = self._normalize_optional_int(
                    user_input,
                    "bls_priority",
                )
                usda_priority = self._normalize_optional_int(
                    user_input,
                    "usda_priority",
                )
                off_priority = self._normalize_optional_int(
                    user_input,
                    "open_food_facts_priority",
                )
            except ValueError:
                errors["base"] = "invalid_source_priority"
            else:
                usda_enabled = bool(user_input["usda_enabled"])
                usda_api_key = str(user_input.get("usda_api_key", "")).strip()
                if usda_enabled and not usda_api_key:
                    errors["usda_api_key"] = "usda_api_key_required"
                else:
                    source_options = self._source_options()
                    source_options["bls"].update(
                        {
                            SOURCE_OPTION_ENABLED: bool(user_input["bls_enabled"]),
                            SOURCE_OPTION_PRIORITY: (
                                source_options["bls"][SOURCE_OPTION_PRIORITY]
                                if bls_priority is None
                                else bls_priority
                            ),
                        }
                    )
                    source_options["usda"].update(
                        {
                            SOURCE_OPTION_ENABLED: usda_enabled,
                            SOURCE_OPTION_PRIORITY: (
                                source_options["usda"][SOURCE_OPTION_PRIORITY]
                                if usda_priority is None
                                else usda_priority
                            ),
                            SOURCE_OPTION_API_KEY: usda_api_key,
                        }
                    )
                    source_options["open_food_facts"].update(
                        {
                            SOURCE_OPTION_ENABLED: bool(
                                user_input["open_food_facts_enabled"]
                            ),
                            SOURCE_OPTION_PRIORITY: (
                                source_options["open_food_facts"][
                                    SOURCE_OPTION_PRIORITY
                                ]
                                if off_priority is None
                                else off_priority
                            ),
                        }
                    )
                    return self.async_create_entry(
                        title="",
                        data=self._updated_options(
                            **{SOURCE_OPTIONS_KEY: source_options}
                        ),
                    )

        return self.async_show_form(
            step_id="configure_food_sources",
            data_schema=self.add_suggested_values_to_schema(
                self._food_source_schema(),
                self._food_source_suggested_values(),
            ),
            errors=errors,
        )
