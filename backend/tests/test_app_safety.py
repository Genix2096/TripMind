"""Repository-level guarantees: no demo/fallback modes, no database, no secrets in responses,
no external calls from startup or health checks."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.authorization import SearchAuthorizer
from app.core.errors import ToolCallLimitExceeded
from app.core.logging import redact
from app.main import create_app
from app.models.common import Capability

BACKEND = Path(__file__).resolve().parents[1]
APP_SRC = BACKEND / "app"


def _runtime_sources():
    return [p for p in APP_SRC.rglob("*.py")]


def test_app_startup_health_and_config_make_no_external_calls(settings):
    # conftest blocks non-loopback sockets, so any external call would raise.
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health").json() == {"status": "ok", "external_calls_made": False}
        body = client.get("/api/config/status").json()
    assert body["credentials_verified_live"] is False
    assert all(body["capabilities_configured"].values())
    assert "test-serp-key-123" not in str(body)


def test_config_status_reports_missing_credentials(empty_settings):
    with TestClient(create_app(empty_settings)) as client:
        body = client.get("/api/config/status").json()
    assert not any(body["capabilities_configured"].values())


def test_oversized_request_rejected(settings):
    with TestClient(create_app(settings)) as client:
        r = client.post("/api/health", content=b"x" * (settings.max_request_body_bytes + 1))
    assert r.status_code == 413


def test_no_demo_or_fallback_flags_in_runtime_code():
    forbidden = re.compile(
        r"APP_MODE|USE_MOCK_DATA|ENABLE_DEMO_DATA|LIVE_TOOL_FALLBACK_TO_LOCAL|demo_mode|mock_data|fallback",
        re.IGNORECASE,
    )
    hits = [
        (p.name, m.group(0))
        for p in _runtime_sources()
        for m in forbidden.finditer(p.read_text(encoding="utf-8"))
    ]
    assert hits == []


def test_runtime_code_never_imports_test_fixtures_or_mocks():
    for p in _runtime_sources():
        text = p.read_text(encoding="utf-8")
        assert "tests.fixtures" not in text and "from tests" not in text, p
        assert "MockTransport" not in text, p


def test_no_database_dependencies_or_code():
    reqs = (BACKEND / "requirements.txt").read_text().lower() + (BACKEND / "requirements-dev.txt").read_text().lower()
    for db in ("sqlalchemy", "sqlite", "psycopg", "pymysql", "mongo", "alembic", "supabase", "asyncpg", "redis"):
        assert db not in reqs
    pattern = re.compile(r"^\s*(import|from)\s+(sqlite3|sqlalchemy|psycopg2?|pymongo|motor|alembic|supabase)\b", re.MULTILINE)
    assert not [p for p in _runtime_sources() if pattern.search(p.read_text(encoding="utf-8"))]


def test_no_adapter_registers_retries():
    for p in (APP_SRC / "providers").rglob("*.py"):
        text = p.read_text(encoding="utf-8").lower()
        assert "retries=" not in text and "retry(" not in text and "tenacity" not in text, p


def test_gitignore_excludes_env():
    gi = (BACKEND.parent / ".gitignore").read_text()
    assert re.search(r"^\.env$", gi, re.MULTILINE) and "!.env.example" in gi


def test_env_example_has_only_placeholders():
    text = (BACKEND / ".env.example").read_text()
    for var in ("GROQ_API_KEY", "GROQ_MODEL", "SERPAPI_API_KEY", "GEOAPIFY_API_KEY", "OPENWEATHER_API_KEY"):
        assert re.search(rf"^{var}=$", text, re.MULTILINE)


def test_redaction():
    out = redact("GET https://x/y?api_key=SECRET1&apiKey=SECRET2&q=1 Bearer abc.def", ["SECRET1"])
    assert "SECRET1" not in out and "SECRET2" not in out and "abc.def" not in out and "q=1" in out


def test_settings_blank_values_are_treated_as_missing():
    from app.core.config import Settings

    s = Settings(_env_file=None, serpapi_api_key="  ", groq_model="")
    assert s.serpapi_api_key is None and s.groq_model is None
    assert s.capability_configured()["flights"] is False

def test_authorizer_enforces_limits_and_zero_limit_blocks():
    auth = SearchAuthorizer(run_id="x", limits={Capability.LLM: 1})
    auth.authorize(Capability.LLM, search_fingerprint="1")
    
    with pytest.raises(ToolCallLimitExceeded, match="Limit of 1"):
        auth.authorize(Capability.LLM, search_fingerprint="2")

    auth2 = SearchAuthorizer(run_id="y", limits={Capability.LLM: 0})
    with pytest.raises(ToolCallLimitExceeded, match="Limit of 0"):
        auth2.authorize(Capability.LLM, search_fingerprint="1")

    auth3 = SearchAuthorizer(run_id="z", limits={Capability.FLIGHTS: 3})
    with pytest.raises(ToolCallLimitExceeded, match="Limit of 0"):
        auth3.authorize(Capability.LLM, search_fingerprint="1")

def test_authorizer_respects_settings_limits(settings):
    limits = settings.call_limits()
    auth = SearchAuthorizer(run_id="a", limits=limits)
    assert limits[Capability.LLM] == 20
    auth.authorize(Capability.LLM, search_fingerprint="ok")
