
import logging
from typing import Any

from app.agents.weather import WeatherRequest
from app.core.authorization import SearchAuthorizer, fingerprint
from app.models.common import Capability, Coordinate, SearchMeta, SearchResult
from app.models.flights import FlightSearchRequest
from app.models.geo import PlacesSearchRequest, RouteRequest
from app.models.hotels import HotelSearchRequest
from app.models.itinerary import ProviderResultStatus, ProviderStatus
from app.providers.base import utcnow
from app.providers.geoapify.places import GeoapifyPlacesAdapter
from app.providers.geoapify.routing import GeoapifyRoutingAdapter
from app.providers.groq.client import GroqLLMClient, ToolCallRequest
from app.providers.openweather.adapter import OpenWeatherAdapter

# Adapters
from app.providers.serpapi.flights import SerpApiFlightsAdapter
from app.providers.serpapi.hotels import SerpApiHotelsAdapter
from app.providers.serpapi.maps import SerpApiMapsAdapter

logger = logging.getLogger("app.agents.coordinator")


class PlanningCoordinator:
    """The Planning Coordinator controls the overall workflow, validates tool calls, and executes them."""

    def __init__(
        self,
        llm: GroqLLMClient,
        flights_adapter: SerpApiFlightsAdapter,
        hotels_adapter: SerpApiHotelsAdapter,
        places_adapter: GeoapifyPlacesAdapter | SerpApiMapsAdapter | Any,
        routing_adapter: GeoapifyRoutingAdapter,
        weather_adapter: OpenWeatherAdapter,
        understanding_llm: Any = None,
        synthesis_llm: Any = None,
    ):
        self.llm = llm
        self.understanding_llm = understanding_llm
        self.synthesis_llm = synthesis_llm or understanding_llm or llm
        self.flights = flights_adapter
        self.hotels = hotels_adapter
        self.places = places_adapter
        self.routing = routing_adapter
        self.weather = weather_adapter

        # State tracking for places caching and call budget preservation within a run
        self._places_cache: dict[str, Any] = {}
        self._retrieved_places: list[Any] = []
        self._places_call_count: int = 0

    async def execute_tool(self, call: ToolCallRequest, authorizer: SearchAuthorizer) -> tuple[str, Any, ProviderResultStatus]:
        """Validate and execute the proposed tool call using the appropriate adapter."""
        name = call.name
        args = call.arguments

        try:
            if name == "search_flights":
                req = FlightSearchRequest(**args)
                has_return = bool(req.return_date)

                # Search outbound as one-way
                out_req = req.model_copy()
                out_req.return_date = None
                res = await self.flights.search(out_req, authorizer)

                # If there's a return date, search return leg separately as one-way
                if has_return:
                    ret_req = req.model_copy()
                    ret_req.origin = req.destination
                    ret_req.destination = req.origin
                    ret_req.outbound_date = req.return_date
                    ret_req.return_date = None
                    try:
                        ret_res = await self.flights.search(ret_req, authorizer)
                        res.items.extend(ret_res.items)
                    except Exception as e:
                        logger.warning(f"Return flight search failed: {e!s}")

                status = ProviderStatus.SUCCESS if res.items else ProviderStatus.EMPTY
                compact_res = res.model_dump_json(exclude={"meta": {"provider_extras": True}, "items": {"__all__": {"provenance": True, "departure_token": True, "booking_token": True}}})
                return compact_res, res, ProviderResultStatus(capability=Capability.FLIGHTS, status=status)

            elif name == "search_hotels":
                req = HotelSearchRequest(**args)
                res = await self.hotels.search(req, authorizer)
                status = ProviderStatus.SUCCESS if res.items else ProviderStatus.EMPTY
                compact_res = res.model_dump_json(exclude={"meta": {"provider_extras": True}, "items": {"__all__": {"provenance": True}}})
                return compact_res, res, ProviderResultStatus(capability=Capability.HOTELS, status=status)

            elif name == "search_places":
                req = PlacesSearchRequest(**args)

                # Check if identical search was already performed in this run
                if isinstance(self.places, SerpApiMapsAdapter):
                    provider_name = SerpApiMapsAdapter.provider
                    fp_params = SerpApiMapsAdapter.build_params(req)
                elif isinstance(self.places, GeoapifyPlacesAdapter):
                    provider_name = GeoapifyPlacesAdapter.provider
                    fp_params = GeoapifyPlacesAdapter.build_places_params(req)
                else:
                    prov = getattr(self.places, "provider", None)
                    provider_name = prov if isinstance(prov, str) else GeoapifyPlacesAdapter.provider
                    fp_params = GeoapifyPlacesAdapter.build_places_params(req)
                fp = fingerprint(provider_name, fp_params)

                if fp in self._places_cache:
                    cached_res = self._places_cache[fp]
                    self._places_call_count += 1
                    logger.info(
                        "Places invocation #%d [REUSED]: categories=%s, center=(%.4f, %.4f), radius=%dm, result_count=%d",
                        self._places_call_count,
                        req.categories,
                        req.center.lat,
                        req.center.lon,
                        req.radius_m,
                        len(cached_res.items),
                    )
                    compact_res = cached_res.model_dump_json(
                        exclude={"meta": {"provider_extras": True}, "items": {"__all__": {"provenance": True}}}
                    )
                    return compact_res, cached_res, ProviderResultStatus(
                        capability=Capability.PLACES,
                        status=ProviderStatus.SUCCESS if cached_res.items else ProviderStatus.EMPTY,
                    )

                self._places_call_count += 1
                call_num = self._places_call_count

                # If budget already reached and we have retrieved places, reuse them
                if call_num > 4 and self._retrieved_places:
                    logger.info(
                        "Places invocation #%d [BUDGET EXHAUSTED - REUSED]: categories=%s, returning %d previously retrieved places",
                        call_num,
                        req.categories,
                        len(self._retrieved_places),
                    )
                    reused_res = SearchResult(
                        status="ok",
                        items=list(self._retrieved_places),
                        meta=SearchMeta(
                            provider=provider_name,
                            capability=Capability.PLACES,
                            retrieved_at=utcnow(),
                        ),
                    )
                    compact_res = reused_res.model_dump_json(
                        exclude={"meta": {"provider_extras": True}, "items": {"__all__": {"provenance": True}}}
                    )
                    return compact_res, reused_res, ProviderResultStatus(capability=Capability.PLACES, status=ProviderStatus.SUCCESS)

                try:
                    res = await self.places.search_places(req, authorizer)
                    self._places_cache[fp] = res
                    if res.items:
                        existing_ids = {p.place_id for p in self._retrieved_places if p.place_id}
                        for item in res.items:
                            if not item.place_id or item.place_id not in existing_ids:
                                self._retrieved_places.append(item)
                                if item.place_id:
                                    existing_ids.add(item.place_id)

                    logger.info(
                        "Places invocation #%d: categories=%s, center=(%.4f, %.4f), radius=%dm, result_count=%d, reused=False",
                        call_num,
                        req.categories,
                        req.center.lat,
                        req.center.lon,
                        req.radius_m,
                        len(res.items),
                    )
                    status = ProviderStatus.SUCCESS if res.items else ProviderStatus.EMPTY
                    compact_res = res.model_dump_json(
                        exclude={"meta": {"provider_extras": True}, "items": {"__all__": {"provenance": True}}}
                    )
                    return compact_res, res, ProviderResultStatus(capability=Capability.PLACES, status=status)
                except Exception as e:
                    # If this call failed (e.g. limit reached) but we already have retrieved places, preserve them!
                    if self._retrieved_places:
                        logger.warning(
                            "Places invocation #%d failed (%s), preserving %d previously retrieved places",
                            call_num,
                            str(e),
                            len(self._retrieved_places),
                        )
                        reused_res = SearchResult(
                            status="ok",
                            items=list(self._retrieved_places),
                            meta=SearchMeta(
                                provider=provider_name,
                                capability=Capability.PLACES,
                                retrieved_at=utcnow(),
                            ),
                        )
                        compact_res = reused_res.model_dump_json(
                            exclude={"meta": {"provider_extras": True}, "items": {"__all__": {"provenance": True}}}
                        )
                        return compact_res, reused_res, ProviderResultStatus(capability=Capability.PLACES, status=ProviderStatus.SUCCESS)
                    raise

            elif name == "route":
                req = RouteRequest(**args)
                res = await self.routing.route(req, authorizer)
                status = ProviderStatus.SUCCESS
                compact_res = res.model_dump_json(exclude={"geometry": True, "provenance": True})
                return compact_res, res, ProviderResultStatus(capability=Capability.ROUTING, status=status)

            elif name == "get_weather":
                req = WeatherRequest(**args)
                coord = Coordinate(lat=req.lat, lon=req.lon)
                if req.kind == "current":
                    res_w = await self.weather.get_current(coord, authorizer)
                else:
                    res_w = await self.weather.get_forecast(coord, authorizer)
                return res_w.model_dump_json(), res_w, ProviderResultStatus(capability=Capability.WEATHER, status=ProviderStatus.SUCCESS)
            else:
                return f"Error: Unknown tool {name}", None, ProviderResultStatus(capability=Capability.FLIGHTS, status=ProviderStatus.ERROR, error_detail=f"Unknown tool {name}")
        except Exception as e:  # noqa: BLE001
            cap_map = {
                "search_flights": Capability.FLIGHTS,
                "search_hotels": Capability.HOTELS,
                "search_places": Capability.PLACES,
                "route": Capability.ROUTING,
                "get_weather": Capability.WEATHER
            }
            cap = cap_map.get(name, Capability.FLIGHTS)
            return f"Error executing {name}: {e!s}", None, ProviderResultStatus(capability=cap, status=ProviderStatus.ERROR, error_detail=str(e))
