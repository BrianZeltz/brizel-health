"""HTTP views for the Brizel Health app bridge."""

from __future__ import annotations

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from ...const import APP_BRIDGE_BASE_URL
from .bridge_responses import bridge_error_response
from .bridge_router import (
    BridgeDomainError,
    BridgeRouteNotFoundError,
    BrizelAppBridgeRouter,
)
from .bridge_schemas import (
    ERROR_INTERNAL_ERROR,
    ERROR_INVALID_PAYLOAD,
    BridgeValidationError,
)


def _authenticated_ha_user_id(request) -> str | None:
    """Return the Home Assistant user ID attached by HA auth middleware."""
    try:
        hass_user = request.get("hass_user")
    except AttributeError:
        try:
            hass_user = request["hass_user"]
        except (KeyError, TypeError):
            hass_user = None

    user_id = str(getattr(hass_user, "id", "") or "").strip()
    return user_id or None


class BrizelAppBridgeView(HomeAssistantView):
    """Authenticated HTTP view for one app bridge route."""

    requires_auth = True

    def __init__(self, route: str) -> None:
        self.route = route
        self.url = f"{APP_BRIDGE_BASE_URL}/{route}"
        self.name = f"api:brizel_health:app_bridge:{route}"

    async def get(self, request):
        """Handle one authenticated bridge GET request."""
        hass: HomeAssistant = request.app["hass"]
        router = BrizelAppBridgeRouter(
            hass,
            ha_user_id=_authenticated_ha_user_id(request),
        )
        try:
            return self.json(router.dispatch_get(self.route))
        except BridgeDomainError as err:
            return self.json(
                bridge_error_response(
                    error_code=err.error_code,
                    message=err.message,
                    field_errors=err.field_errors,
                ),
                status_code=err.status_code,
            )
        except BridgeRouteNotFoundError as err:
            return self.json(
                bridge_error_response(
                    error_code="route_not_found",
                    message=str(err),
                ),
                status_code=404,
            )
        except Exception:  # pragma: no cover - defensive HTTP boundary
            return self.json(
                bridge_error_response(
                    error_code=ERROR_INTERNAL_ERROR,
                    message="The Brizel Health app bridge could not handle this request.",
                ),
                status_code=500,
            )

    async def post(self, request):
        """Handle one authenticated bridge POST request."""
        hass: HomeAssistant = request.app["hass"]
        router = BrizelAppBridgeRouter(
            hass,
            ha_user_id=_authenticated_ha_user_id(request),
        )
        try:
            data = await request.json()
        except Exception:
            return self.json(
                bridge_error_response(
                    error_code=ERROR_INVALID_PAYLOAD,
                    message="Request body must be valid JSON.",
                    field_errors={"body": "invalid_json"},
                ),
                status_code=400,
            )

        try:
            return self.json(await router.dispatch_post(self.route, data))
        except BridgeValidationError as err:
            return self.json(
                bridge_error_response(
                    error_code=err.error_code,
                    message=err.message,
                    field_errors=err.field_errors,
                ),
                status_code=400,
            )
        except BridgeDomainError as err:
            return self.json(
                bridge_error_response(
                    error_code=err.error_code,
                    message=err.message,
                    field_errors=err.field_errors,
                ),
                status_code=err.status_code,
            )
        except BridgeRouteNotFoundError as err:
            return self.json(
                bridge_error_response(
                    error_code="route_not_found",
                    message=str(err),
                ),
                status_code=404,
            )
        except Exception:  # pragma: no cover - defensive HTTP boundary
            return self.json(
                bridge_error_response(
                    error_code=ERROR_INTERNAL_ERROR,
                    message="The Brizel Health app bridge could not handle this request.",
                ),
                status_code=500,
            )


def async_register_app_bridge_views(hass: HomeAssistant) -> None:
    """Register authenticated app bridge HTTP views."""
    hass.http.register_view(BrizelAppBridgeView("ping"))
    hass.http.register_view(BrizelAppBridgeView("capabilities"))
    hass.http.register_view(BrizelAppBridgeView("profiles"))
    hass.http.register_view(BrizelAppBridgeView("profile_context"))
    hass.http.register_view(BrizelAppBridgeView("sync_status"))
    hass.http.register_view(BrizelAppBridgeView("sync_pull"))
    hass.http.register_view(BrizelAppBridgeView("steps"))
    hass.http.register_view(BrizelAppBridgeView("body_measurements"))
    hass.http.register_view(BrizelAppBridgeView("body_goals"))
    hass.http.register_view(BrizelAppBridgeView("food_logs"))
