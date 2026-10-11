"""Health and configuration status. Neither endpoint contacts any external provider."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "external_calls_made": False}


@router.get("/config/status")
def config_status(request: Request) -> dict[str, object]:
    """Which capabilities have credentials configured (presence only, never validated live)."""
    settings = request.app.state.settings
    return {
        "capabilities_configured": settings.capability_configured(),
        "credentials_verified_live": False,
        "storage": "none (no database; browser localStorage is used by the frontend only)",
    }
