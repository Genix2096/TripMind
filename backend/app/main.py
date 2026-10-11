"""FastAPI application. Starting the app and serving health/config makes no external requests."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import health
from app.core.config import Settings, get_settings
from app.core.errors import AgentTripError
from app.core.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.secret_values())

    app = FastAPI(title="AgentTrip API", version="0.1.0")
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def limit_body_size(request: Request, call_next):
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > settings.max_request_body_bytes:
            return JSONResponse(
                status_code=413,
                content={"error": {"code": "request_too_large", "message": "Request body is too large."}},
            )
        return await call_next(request)

    @app.exception_handler(AgentTripError)
    async def handle_agenttrip_error(_: Request, exc: AgentTripError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": exc.to_dict()})

    app.include_router(health.router, prefix="/api")
    from app.api.routes import planning
    app.include_router(planning.router, prefix="/api")
    return app


app = create_app()
