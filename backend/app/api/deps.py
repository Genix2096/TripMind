import logging

from fastapi import Depends

from app.agents.coordinator import PlanningCoordinator
from app.core.config import Settings, get_settings
from app.providers.geoapify.routing import GeoapifyRoutingAdapter
from app.providers.groq.client import GroqLLMClient
from app.providers.openweather.adapter import OpenWeatherAdapter
from app.providers.serpapi.flights import SerpApiFlightsAdapter
from app.providers.serpapi.hotels import SerpApiHotelsAdapter
from app.providers.serpapi.maps import SerpApiMapsAdapter

logger = logging.getLogger(__name__)

def get_coordinator(settings: Settings = Depends(get_settings)) -> PlanningCoordinator:  # noqa: B008
    llm = GroqLLMClient(settings)
    flights = SerpApiFlightsAdapter(settings)
    hotels = SerpApiHotelsAdapter(settings)
    places = SerpApiMapsAdapter(settings)
    routing = GeoapifyRoutingAdapter(settings)
    weather = OpenWeatherAdapter(settings)
    
    from app.providers.gemini.client import GeminiUnderstandingClient
    gemini_client = GeminiUnderstandingClient(settings)
    
    return PlanningCoordinator(
        llm=llm,
        understanding_llm=gemini_client,
        synthesis_llm=gemini_client,
        flights_adapter=flights,
        hotels_adapter=hotels,
        places_adapter=places,
        routing_adapter=routing,
        weather_adapter=weather
    )
