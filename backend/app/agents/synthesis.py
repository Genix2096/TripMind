from typing import Any

from app.core.authorization import SearchAuthorizer
from app.models.itinerary import LLMSynthesisOutput
from app.providers.gemini.client import GeminiUnderstandingClient


class ItinerarySynthesisAgent:
    """Agent 8: Itinerary Synthesis Agent"""

    def __init__(self, llm: GeminiUnderstandingClient | Any):
        self.llm = llm

    async def synthesize(
        self,
        context: str,
        authorizer: SearchAuthorizer,
    ) -> LLMSynthesisOutput:
        if hasattr(self.llm, "synthesize"):
            return await self.llm.synthesize(context, authorizer)

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

        result = await self.llm.complete_structured(
            messages, LLMSynthesisOutput, authorizer, max_tokens=4096
        )
        return result

