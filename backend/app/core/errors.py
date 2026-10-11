"""Typed application errors. Messages never contain credentials."""

from __future__ import annotations

from typing import Any

from app.models.common import Capability


class AgentTripError(Exception):
    code = "internal_error"
    status_code = 500

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        capability: Capability | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.capability = capability
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "provider": self.provider,
            "capability": self.capability.value if self.capability else None,
            "retry": "manual_only",
            "details": self.details,
        }


class ConfigurationError(AgentTripError):
    code = "configuration_error"
    status_code = 503


class MissingCredentialsError(ConfigurationError):
    code = "missing_credentials"

    def __init__(self, *, provider: str, capability: Capability, env_var: str) -> None:
        super().__init__(
            f"{env_var} is not configured, so {capability.value} cannot be used.",
            provider=provider,
            capability=capability,
            details={"env_var": env_var},
        )


class ProviderError(AgentTripError):
    code = "provider_error"
    status_code = 502


class ProviderAuthError(ProviderError):
    code = "provider_auth_rejected"


class ProviderRateLimitError(ProviderError):
    code = "provider_rate_limited"
    status_code = 429


class ProviderTimeoutError(ProviderError):
    code = "provider_timeout"
    status_code = 504


class ProviderUnavailableError(ProviderError):
    code = "provider_unavailable"


class ProviderRequestError(ProviderError):
    """The provider rejected our parameters (invalid search)."""

    code = "provider_invalid_request"
    status_code = 422


class ProviderResponseError(ProviderError):
    """The provider answered with something we cannot interpret."""

    code = "provider_bad_response"


class LLMOutputError(ProviderError):
    code = "llm_invalid_output"


class ToolAuthorizationError(AgentTripError):
    code = "tool_not_authorized"
    status_code = 403


class ToolCallLimitExceeded(ToolAuthorizationError):
    code = "tool_call_limit_exceeded"


class DuplicateSearchError(ToolAuthorizationError):
    code = "duplicate_search_blocked"
