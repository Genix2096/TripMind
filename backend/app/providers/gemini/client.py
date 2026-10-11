import json
from typing import Any

from google import genai
from google.genai import types

from app.core.authorization import SearchAuthorizer, fingerprint
from app.core.config import Settings
from app.core.errors import (
    AgentTripError,
    LLMOutputError,
    MissingCredentialsError,
    ProviderRequestError,
    ProviderUnavailableError,
)
from app.models.common import Capability
from app.models.itinerary import LLMSynthesisOutput
from app.providers.base import BaseAdapter, utcnow

PROVIDER = "gemini"


class GeminiUnderstandingClient:
    def __init__(self, settings: Settings):
        self._settings = settings

    def _key(self, capability: Capability = Capability.UNDERSTANDING) -> str:
        key = self._settings.gemini_api_key
        if key is None:
            raise MissingCredentialsError(
                provider=PROVIDER, capability=capability, env_var="GEMINI_API_KEY"
            )
        return key.get_secret_value()

    def _normalize_schema(self, schema: Any, parent_key: str | None = None) -> Any:
        """Recursively clean up Pydantic JSON schema for Gemini compatibility."""
        if isinstance(schema, dict):
            cleaned = {}
            for k, v in schema.items():
                if parent_key != "properties" and k in ("title", "default"):
                    continue
                if k == "exclusiveMinimum":
                    cleaned["minimum"] = v
                    continue
                elif k == "exclusiveMaximum":
                    cleaned["maximum"] = v
                    continue
                cleaned[k] = self._normalize_schema(v, parent_key=k)
            return cleaned
        elif isinstance(schema, list):
            return [self._normalize_schema(item, parent_key=parent_key) for item in schema]
        return schema

    async def complete_structured(
        self,
        messages: list[dict[str, Any]],
        schema: type,
        authorizer: SearchAuthorizer,
        max_tokens: int = 4096,
        capability: Capability = Capability.UNDERSTANDING,
    ) -> Any:
        authorizer.authorize(capability, search_fingerprint=fingerprint(PROVIDER, {"messages": messages}))

        try:
            client = genai.Client(api_key=self._key(capability=capability))
            model = self._settings.gemini_model or "gemini-2.5-pro"

            # Convert messages to Gemini format
            contents = []
            system_instruction = None
            for msg in messages:
                if msg["role"] == "system":
                    system_instruction = msg["content"]
                else:
                    contents.append(msg["content"])

            # Normalize schema for Gemini
            pydantic_schema = schema.model_json_schema()
            normalized_schema = self._normalize_schema(pydantic_schema)

            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=normalized_schema,
                max_output_tokens=max_tokens,
                temperature=0.1,
            )

            if system_instruction:
                config.system_instruction = system_instruction

            # google-genai supports async using client.aio
            response = await client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )

            if not response.text:
                raise ProviderUnavailableError(
                    "Gemini returned an empty response.", provider=PROVIDER, capability=capability
                )

            try:
                from pydantic import ValidationError

                return schema.model_validate_json(response.text)
            except (ValidationError, ValueError) as exc:
                raise LLMOutputError(
                    "The language model returned output that did not match the required structure.",
                    provider=PROVIDER,
                    capability=capability,
                    details={"error": str(exc)},
                ) from exc

        except Exception as e:
            if isinstance(e, AgentTripError):
                raise
            raise ProviderRequestError(str(e), provider=PROVIDER, capability=capability) from e

    async def synthesize(
        self,
        context: str,
        authorizer: SearchAuthorizer,
        max_tokens: int = 4096,
    ) -> LLMSynthesisOutput:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are the Itinerary Synthesis Agent. Your job is to combine the validated flights, hotels, "
                    "attractions, routing, and weather into a coherent day-wise itinerary.\n"
                    "CRITICAL REQUIREMENTS:\n"
                    "1. You MUST generate a DayPlan for EVERY requested travel day from the departure date to the return date (inclusive). "
                    "Each DayPlan must have its exact date (YYYY-MM-DD).\n"
                    "2. On the departure date, schedule the outbound travel and hotel check-in. "
                    "On the return date, schedule hotel check-out and the return journey.\n"
                    "3. On intermediate days, schedule activities grounded strictly in the provided Places and attractions data.\n"
                    "4. DO NOT invent entities, flight numbers, hotels, or attractions. If places/attractions data is unavailable or empty, "
                    "do not invent fake activities; note in missing_information and the trip_summary that attraction data was unavailable.\n"
                    "5. Preserve source provenance and note scheduling or weather warnings."
                ),
            },
            {
                "role": "user",
                "content": context,
            },
        ]
        return await self.complete_structured(
            messages=messages,
            schema=LLMSynthesisOutput,
            authorizer=authorizer,
            max_tokens=max_tokens,
            capability=Capability.UNDERSTANDING,
        )


GeminiClient = GeminiUnderstandingClient
