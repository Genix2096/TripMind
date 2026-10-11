"""Geoapify credential helper shared by Places/Geocoding and Routing."""

from __future__ import annotations

from app.core.config import Settings
from app.core.errors import MissingCredentialsError
from app.models.common import Capability


def get_geoapify_key(settings: Settings, *, provider: str, capability: Capability) -> str:
    key = settings.geoapify_api_key
    if key is None:
        raise MissingCredentialsError(
            provider=provider, capability=capability, env_var="GEOAPIFY_API_KEY"
        )
    return key.get_secret_value()
