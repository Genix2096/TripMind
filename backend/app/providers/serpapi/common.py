"""The single SerpApi credential source shared by Google Flights, Google Hotels, and Google Maps."""

from __future__ import annotations

from app.core.config import Settings
from app.core.errors import MissingCredentialsError
from app.models.common import Capability


def get_serpapi_key(settings: Settings, *, provider: str, capability: Capability) -> str:
    key = settings.serpapi_api_key
    if key is None:
        raise MissingCredentialsError(
            provider=provider, capability=capability, env_var="SERPAPI_API_KEY"
        )
    return key.get_secret_value()


def check_serpapi_payload(payload: object, *, provider: str, capability: Capability) -> bool:
    """Return True if the payload is a valid response, False if SerpApi reports 'no results'.

    Raises ProviderRequestError / ProviderResponseError for every other error.
    SerpApi reports a successful search with zero results as an `error` string.
    """
    from app.core.errors import ProviderRequestError, ProviderResponseError

    if not isinstance(payload, dict):
        raise ProviderResponseError(
            f"{provider} returned an unexpected response shape.", provider=provider, capability=capability
        )
    error = payload.get("error")
    if error:
        text = str(error)[:300]
        if "hasn't returned any results" in text.lower():
            return False
        raise ProviderRequestError(f"{provider} reported an error: {text}", provider=provider, capability=capability)
    status = str(as_status(payload)).lower()
    if status == "error":
        raise ProviderRequestError(
            f"{provider} marked the search as failed.", provider=provider, capability=capability
        )
    return True


def as_status(payload: dict) -> str:
    meta = payload.get("search_metadata")
    return str(meta.get("status", "")) if isinstance(meta, dict) else ""
