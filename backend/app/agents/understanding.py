from datetime import date

from app.core.authorization import SearchAuthorizer
from app.models.trip import TripState
from app.providers.gemini.client import GeminiUnderstandingClient


class TravelRequestUnderstandingAgent:
    """Agent 1: Travel Request Understanding Agent
    Interpret natural-language requests and extract a validated TripState.
    """
    
    def __init__(self, llm: GeminiUnderstandingClient):
        self.llm = llm

    async def understand(self, request: str, today: date, authorizer: SearchAuthorizer, existing_state: str = None) -> TripState:
        # Pass existing state to update in follow-up queries if provided and valid JSON
        context = ""
        if existing_state and isinstance(existing_state, str):
            trimmed = existing_state.strip()
            # Only inject if it represents structured trip state (not raw pace strings or malformed inputs)
            if trimmed.startswith("{") and ("origin" in trimmed or "destination" in trimmed or "departure_date" in trimmed or "travelers" in trimmed):
                context = f"\nExisting Trip State to update: {trimmed}\n"
            
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a travel planning assistant. Your task is to interpret a user's natural language request and output a structured JSON TripState.\n"
                    f"Today's date is {today.isoformat()}.\n"
                    "Instructions:\n"
                    "- Extract origin, destination, and travel dates.\n"
                    "- For missing years, infer the upcoming occurrence from today's date.\n"
                    "- For travel duration, 'calendar_days' means total span (e.g. Oct 12 to 16 is 5 calendar days), and 'nights' is one less.\n"
                    "- Extract budget, travelers (adults/children), and explicit preferences or constraints.\n"
                    "- For attraction preferences:\n"
                    "  * Extract explicitly stated attraction interests into preferences.interests and preferences.attraction_preferences.\n"
                    "  * Categorize into primary_interests (core focus) and secondary_interests (secondary/optional focus).\n"
                    "  * Categories include: historical architecture & heritage, forts/palaces/monuments, wildlife/sanctuaries, "
                    "nature/forests/lakes/scenic, beaches/coastal, museums/art/culture, food/local cuisine, shopping/markets, "
                    "adventure/outdoors, religious/spiritual, family-friendly, nightlife/entertainment, photography/viewpoints.\n"
                    "  * Preserve the user's wording in raw_interest_phrases.\n"
                    "  * Set preference_source='explicitly_stated' if the user explicitly stated attraction interests.\n"
                    "  * CRITICAL: Do NOT infer personal attraction interests merely because the user is visiting a particular destination. "
                    "If the user did not state attraction interests, leave primary_interests and secondary_interests empty with preference_source='default_balanced'.\n"
                    "- For trip pace preferences (preferences.pace and preferences.pace_preferences):\n"
                    "  * Values: 'RUSHED', 'BALANCED', 'SLOW'. Default to 'BALANCED' if no clear pace is expressed.\n"
                    "  * Recognize expressions such as:\n"
                    "    - RUSHED: 'visit as many places as possible', 'packed itinerary', 'busy schedule', 'cover more attractions every day', 'fast-paced', 'see everything'.\n"
                    "    - SLOW: 'relaxed vacation', 'take it slow', 'spend more time at each place', 'leave plenty of free time', 'leisurely', 'unhurried'.\n"
                    "    - BALANCED: 'mix of sightseeing and relaxation', 'keep the schedule comfortable', 'balanced itinerary', 'moderate pace'.\n"
                    "  * If explicitly stated, set preferences.pace to 'RUSHED' or 'SLOW' and set preference_source='explicitly_stated' with raw_pace_phrase.\n"
                    "  * If not explicitly stated, use 'BALANCED' with preference_source='default_balanced'.\n"
                    "  * CRITICAL: Do NOT infer RUSHED merely because the user lists many interests or attractions. Attraction interests and trip pace are separate preferences.\n"
                    "  * If explicit pace instructions conflict, resolve conservatively to BALANCED and note the conflict in 'assumptions' or 'clarification_question'.\n"
                    "- Do not invent missing preferences or information. If something is not stated, leave it null.\n"
                    "- Distinguish between explicitly stated facts and reasonable assumptions. Put inferences in 'assumptions'.\n"
                    "- If a request is a follow-up or correction to an existing state, apply the changes to the existing state and output the complete updated state.\n"
                    "- If there is a genuine, unresolvable ambiguity or if essential information (origin, destination, dates/duration) is missing, provide a single, specific question in 'clarification_question'."
                    + context
                )
            },
            {
                "role": "user",
                "content": request
            }
        ]
        try:
            state = await self.llm.complete_structured(messages, TripState, authorizer, max_tokens=1024)
        except Exception as e:
            from app.core.errors import LLMOutputError
            if isinstance(e, LLMOutputError):
                details = e.details.get("error", "The generated plan did not meet strict application constraints.")
                return TripState(
                    raw_request=request,
                    clarification_question=f"I couldn't process your request because: {details}. Please adjust your request and try again."
                )
            raise e
        state.raw_request = request
        return state
