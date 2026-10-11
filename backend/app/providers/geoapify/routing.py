"""Geoapify Routing API adapter."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.core.authorization import SearchAuthorizer, fingerprint
from app.core.config import Settings
from app.core.errors import ProviderResponseError
from app.models.common import Capability, Provenance, SearchMeta, SearchResult
from app.models.geo import Route, RouteLeg, RouteRequest
from app.providers.base import BaseAdapter, as_dict, as_float, as_list, as_str, utcnow
from app.providers.geoapify.common import get_geoapify_key

PROVIDER = "geoapify_routing"
URL = "https://api.geoapify.com/v1/routing"


class GeoapifyRoutingAdapter(BaseAdapter):
    provider = PROVIDER

    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None):
        super().__init__(settings, transport=transport)

    @staticmethod
    def build_params(req: RouteRequest) -> dict[str, Any]:
        # Geoapify routing waypoints are "lat,lon" pairs separated by "|".
        return {
            "waypoints": "|".join(f"{w.lat},{w.lon}" for w in req.waypoints),
            "mode": req.mode,
            "units": "metric",
        }

    async def route(self, req: RouteRequest, authorizer: SearchAuthorizer) -> SearchResult[Route]:
        key = get_geoapify_key(self._settings, provider=PROVIDER, capability=Capability.ROUTING)
        params = self.build_params(req)
        
        import logging
        logger = logging.getLogger("app.providers.geoapify.routing")
        logger.info(f"Requesting Geoapify routing: waypoints={len(req.waypoints)} mode={req.mode}")
        
        authorizer.authorize(Capability.ROUTING, search_fingerprint=fingerprint(PROVIDER, params))
        
        try:
            payload = await self._http.request_json(
                "GET",
                URL,
                capability=Capability.ROUTING,
                secrets=[key],
                params={**params, "apiKey": key},
            )
            res = self.parse_response(payload, req, params, retrieved_at=utcnow())
            logger.info(f"Geoapify routing success: {len(res.items)} route(s) returned.")
            return res
        except Exception as e:
            logger.error(f"Geoapify routing failed: {type(e).__name__} - {e!s}")
            raise

    @staticmethod
    def parse_response(
        payload: Any, req: RouteRequest, params: dict[str, Any], *, retrieved_at: datetime
    ) -> SearchResult[Route]:
        if not isinstance(payload, dict) or not isinstance(payload.get("features"), list):
            raise ProviderResponseError(
                f"{PROVIDER} returned an unexpected response shape.",
                provider=PROVIDER,
                capability=Capability.ROUTING,
            )
        limitations = ["Durations are provider estimates and do not include live traffic."]
        if req.mode in ("transit", "approximated_transit"):
            limitations.append("Transit routing is limited by provider coverage.")
        meta = SearchMeta(
            provider=PROVIDER,
            capability=Capability.ROUTING,
            retrieved_at=retrieved_at,
            request_params=params,
            limitations=limitations,
        )
        routes: list[Route] = []
        for feature in payload["features"][:1]:
            f = as_dict(feature)
            props = as_dict(f.get("properties"))
            distance, duration = as_float(props.get("distance")), as_float(props.get("time"))
            if distance is None and duration is None:
                continue
            geometry: list[list[list[float]]] = []
            if req.include_geometry:
                geom = as_dict(f.get("geometry"))
                if geom.get("type") == "MultiLineString":
                    geometry = [_line(line) for line in as_list(geom.get("coordinates"))]
                elif geom.get("type") == "LineString":
                    geometry = [_line(geom.get("coordinates"))]
            legs = [
                RouteLeg(distance_m=as_float(as_dict(l).get("distance")), duration_s=as_float(as_dict(l).get("time")))
                for l in as_list(props.get("legs"))
            ]
            routes.append(
                Route(
                    mode=as_str(props.get("mode")) or req.mode,
                    distance_m=distance,
                    duration_s=duration,
                    legs=legs,
                    geometry=geometry,
                    waypoints=list(req.waypoints),
                    provenance=Provenance(
                        provider=PROVIDER, capability=Capability.ROUTING, retrieved_at=retrieved_at
                    ),
                )
            )
        return SearchResult(status="ok" if routes else "empty", items=routes, meta=meta)


def _line(coords: Any) -> list[list[float]]:
    out: list[list[float]] = []
    for p in as_list(coords):
        pt = as_list(p)
        if len(pt) >= 2:
            lon, lat = as_float(pt[0]), as_float(pt[1])
            if lon is not None and lat is not None:
                out.append([lon, lat])
    return out
