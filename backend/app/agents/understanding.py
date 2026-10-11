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
        # Pass existing state to update in follow-up queries if provided
        context = ""
        if existing_state:
            context = f"\nExisting Trip State to update: {existing_state}\n"
            
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
