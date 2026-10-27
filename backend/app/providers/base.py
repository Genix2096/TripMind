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
            log.warning("Provider timeout: %s %s did not respond in time.", self._provider, capability.value)
            raise ProviderTimeoutError(
                f"{self._provider} did not respond in time.",
                provider=self._provider,
                capability=capability,
            ) from exc
        except httpx.HTTPError as exc:
            category, safe_detail = _categorize_connection_error(exc, secrets)
            log.warning(
                "Provider connection error: %s %s [%s]: %s",
                self._provider,
                capability.value,
                category,
                safe_detail,
            )
            raise ProviderUnavailableError(
                f"Could not reach {self._provider} ({type(exc).__name__} [{category}]: {safe_detail}).",
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


def _categorize_connection_error(exc: Exception, secrets: Sequence[str] = ()) -> tuple[str, str]:
    """Diagnose and categorize connection-level errors into safe, secret-free diagnostics.

    Returns (category_name, safe_description). Never leaks URLs or credentials.
    """
    import socket
    import ssl

    # Traverse exception chain to uncover the underlying cause
    root: Exception = exc
    chain: list[Exception] = [exc]
    while getattr(root, "__cause__", None) is not None or getattr(root, "__context__", None) is not None:
        next_exc = root.__cause__ if getattr(root, "__cause__", None) is not None else root.__context__
        if next_exc in chain or not isinstance(next_exc, Exception):
            break
        root = next_exc
        chain.append(root)

    root_type = type(root).__name__
    root_str = str(root)

    # 1. DNS Resolution Failure
    if isinstance(root, socket.gaierror) or "getaddrinfo" in root_str.lower() or "nodename" in root_str.lower():
        msg = root_str.split(":")[-1].strip() if ":" in root_str else root_str
        return "DNS_RESOLUTION_FAILED", f"DNS lookup failed ({root_type}: {msg})"

    # 2. TLS / SSL Handshake Failure
    if isinstance(root, (ssl.SSLError, ssl.CertificateError)) or "ssl" in root_type.lower() or "certificate" in root_str.lower():
        return "TLS_HANDSHAKE_FAILED", f"TLS/SSL negotiation failed ({root_type})"

    # 3. Connection Refused
    if isinstance(root, ConnectionRefusedError) or "connection refused" in root_str.lower() or "10061" in root_str:
        return "CONNECTION_REFUSED", "Remote endpoint actively refused the connection"

    # 4. Connection / Connect Timeout (failed during TCP connect, before request sent)
    if isinstance(root, (TimeoutError, socket.timeout)) or "timed out" in root_str.lower() or "10060" in root_str:
        return "CONNECT_TIMEOUT", "TCP connection attempt timed out"

    # 5. Network / Host Unreachable
    if "unreachable" in root_str.lower() or "no route" in root_str.lower() or "10051" in root_str or "10065" in root_str:
        return "NETWORK_UNREACHABLE", "Host or network unreachable"

    # 6. Proxy Failure
    if "proxy" in root_type.lower() or "proxy" in root_str.lower():
        return "PROXY_ERROR", f"Proxy connection failed ({root_type})"

    # Fallback generic connection error (redact any possible secrets or URLs)
    clean_msg = redact(root_str[:120], list(secrets))
    if "?" in clean_msg:
        clean_msg = clean_msg.split("?")[0]
    return "CONNECTION_FAILED", f"{root_type}: {clean_msg}" if clean_msg else root_type


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
