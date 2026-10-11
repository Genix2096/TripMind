"""Shared HTTP plumbing for provider adapters.

* One request per call. **No retries** of any kind (quota safety).
* Maps transport and HTTP failures to typed, credential-free ProviderErrors.
* The ``transport`` argument exists solely so isolated tests can inject an in-process transport.
  Production code never passes it.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import Settings
from app.core.errors import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.core.logging import redact
from app.models.common import Capability

log = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(UTC)


class ProviderHttp:
    def __init__(
        self,
        *,
        provider: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._provider = provider
        self._timeout = httpx.Timeout(timeout_seconds)
        self._transport = transport

    async def request_json(
        self,
        method: str,
        url: str,
        *,
        capability: Capability,
        secrets: Sequence[str],
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        json_body: Any = None,
    ) -> Any:
        log.info("Provider request: %s %s (%s)", self._provider, capability.value, "user-initiated")
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                response = await client.request(
                    method, url, params=params, headers=headers, json=json_body
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                f"{self._provider} did not respond in time.",
                provider=self._provider,
                capability=capability,
            ) from exc
        except httpx.HTTPError as exc:
            # Do not include str(exc): it may contain the request URL with the API key.
            raise ProviderUnavailableError(
                f"Could not reach {self._provider} ({type(exc).__name__}).",
                provider=self._provider,
                capability=capability,
            ) from exc

        if response.status_code >= 400:
            self._raise_for_status(response, capability, secrets)

        try:
            return response.json()
        except ValueError as exc:
            raise ProviderResponseError(
                f"{self._provider} returned a non-JSON response.",
                provider=self._provider,
                capability=capability,
            ) from exc

    def _raise_for_status(
        self, response: httpx.Response, capability: Capability, secrets: Sequence[str]
    ) -> None:
        detail = _extract_error_text(response, secrets)
        kwargs = {"provider": self._provider, "capability": capability}
        status = response.status_code
        suffix = f": {detail}" if detail else ""
        if status in (401, 403):
            raise ProviderAuthError(
                f"{self._provider} rejected the credentials (HTTP {status}){suffix}", **kwargs
            )
        if status == 429:
            raise ProviderRateLimitError(
                f"{self._provider} rate limit or quota exhausted (HTTP 429){suffix}", **kwargs
            )
        if status >= 500:
            raise ProviderUnavailableError(
                f"{self._provider} had a server error (HTTP {status}){suffix}", **kwargs
            )
        raise ProviderRequestError(
            f"{self._provider} rejected the request (HTTP {status}){suffix}", **kwargs
        )


def _extract_error_text(response: httpx.Response, secrets: Sequence[str]) -> str:
    text = ""
    try:
        body = response.json()
        if isinstance(body, dict):
            err = body.get("error") or body.get("message")
            if isinstance(err, dict):
                err = err.get("message")
            text = str(err) if err else ""
    except ValueError:
        text = response.text[:200]
    return redact(text[:300], list(secrets))


class BaseAdapter:
    provider: str = ""

    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None):
        self._settings = settings
        self._http = ProviderHttp(
            provider=self.provider,
            timeout_seconds=settings.provider_timeout_seconds,
            transport=transport,
        )

    @property
    def _secrets(self) -> list[str]:
        return self._settings.secret_values()


# ---- Defensive value helpers (provider payloads are untrusted) ----------------------------


def as_dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def as_list(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def as_str(v: Any) -> str | None:
    if isinstance(v, str) and v.strip():
        return v.strip()
    return None


def as_int(v: Any) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return None


def as_float(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None
