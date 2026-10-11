"""Groq LLM client (OpenAI-compatible chat completions).

The LLM interprets, ranks and explains. Its output is untrusted text: ``tool_calls`` are only
*requests* that the Planning Coordinator may or may not authorize. This client never executes them.
"""

from __future__ import annotations

import json
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.authorization import SearchAuthorizer, fingerprint
from app.core.config import Settings
from app.core.errors import (
    LLMOutputError,
    MissingCredentialsError,
    ProviderResponseError,
)
from app.models.common import Capability
from app.providers.base import BaseAdapter, as_dict, as_int, as_list, as_str

PROVIDER = "groq"
URL = "https://api.groq.com/openai/v1/chat/completions"
M = TypeVar("M", bound=BaseModel)


class ToolCallRequest(BaseModel):
    id: str | None = None
    name: str
    arguments: dict[str, Any]


class LLMResponse(BaseModel):
    content: str | None
    tool_calls: list[ToolCallRequest] = []
    model: str | None = None
    finish_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class GroqLLMClient(BaseAdapter):
    provider = PROVIDER

    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None):
        super().__init__(settings, transport=transport)
        # LLM calls get their own, longer timeout.
        self._http._timeout = httpx.Timeout(settings.llm_timeout_seconds)

    def _credentials(self) -> tuple[str, str]:
        if self._settings.groq_api_key is None:
            raise MissingCredentialsError(
                provider=PROVIDER, capability=Capability.LLM, env_var="GROQ_API_KEY"
            )
        if not self._settings.groq_model:
            raise MissingCredentialsError(
                provider=PROVIDER, capability=Capability.LLM, env_var="GROQ_MODEL"
            )
        return self._settings.groq_api_key.get_secret_value(), self._settings.groq_model

    async def chat(
        self,
        messages: list[dict[str, Any]],
        authorizer: SearchAuthorizer,
        *,
        tools: list[dict[str, Any]] | None = None,
        json_mode: bool = False,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        key, model = self._credentials()
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if json_mode:
            body["response_format"] = {"type": "json_object"}
            
        from app.core.quota import TokenQuotaManager
        
        # Rough token estimation (chars / 4 is a standard conservative heuristic).
        # We must leave room for the requested max_tokens in the output.
        estimated_input = int(len(json.dumps(body)) / 4.0)
        
        quota_mgr = TokenQuotaManager.get_instance()
        reservation = await quota_mgr.acquire(estimated_input, max_tokens)
            
        authorizer.authorize(
            Capability.LLM, search_fingerprint=fingerprint(PROVIDER, {"model": model, "body": body})
        )
        try:
            payload = await self._http.request_json(
                "POST",
                URL,
                capability=Capability.LLM,
                secrets=[key],
                headers={"Authorization": f"Bearer {key}"},
                json_body=body,
            )
            
            res = self.parse_response(payload)
            actual_total = (res.prompt_tokens or estimated_input) + (res.completion_tokens or 0)
            return res
        except Exception:
            # Re-raise so the caller handles it
            raise
        finally:
            # Reconcile quota with actual token usage, or 0 if failed/cancelled
            if 'actual_total' in locals():
                quota_mgr.reconcile(reservation, actual_total)
            else:
                quota_mgr.reconcile(reservation, 0)

    async def complete_structured(
        self,
        messages: list[dict[str, Any]],
        schema: type[M],
        authorizer: SearchAuthorizer,
        **kwargs: Any,
    ) -> M:
        """One call, JSON mode, validated against `schema`. A bad answer raises; it is NOT retried."""
        instruction = (
            "Respond with a single JSON object that validates against this JSON schema. "
            "Use null for anything not stated by the user; never invent values.\n"
            + json.dumps(schema.model_json_schema())
        )
        response = await self.chat(
            [{"role": "system", "content": instruction}, *messages],
            authorizer,
            json_mode=True,
            **kwargs,
        )
        try:
            return schema.model_validate_json(response.content or "")
        except (ValidationError, ValueError) as exc:
            raise LLMOutputError(
                "The language model returned output that did not match the required structure.",
                provider=PROVIDER,
                capability=Capability.LLM,
            ) from exc

    @staticmethod
    def parse_response(payload: Any) -> LLMResponse:
        choices = as_list(as_dict(payload).get("choices"))
        if not choices:
            raise ProviderResponseError(
                "Groq returned no choices.", provider=PROVIDER, capability=Capability.LLM
            )
        choice = as_dict(choices[0])
        message = as_dict(choice.get("message"))
        calls: list[ToolCallRequest] = []
        for raw in as_list(message.get("tool_calls")):
            fn = as_dict(as_dict(raw).get("function"))
            name = as_str(fn.get("name"))
            if not name:
                continue
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except (TypeError, ValueError):
                args = None
            if not isinstance(args, dict):
                raise LLMOutputError(
                    "The language model produced malformed tool arguments.",
                    provider=PROVIDER,
                    capability=Capability.LLM,
                )
            calls.append(ToolCallRequest(id=as_str(as_dict(raw).get("id")), name=name, arguments=args))
        usage = as_dict(as_dict(payload).get("usage"))
        return LLMResponse(
            content=message.get("content") if isinstance(message.get("content"), str) else None,
            tool_calls=calls,
            model=as_str(as_dict(payload).get("model")),
            finish_reason=as_str(choice.get("finish_reason")),
            prompt_tokens=as_int(usage.get("prompt_tokens")),
            completion_tokens=as_int(usage.get("completion_tokens")),
        )
