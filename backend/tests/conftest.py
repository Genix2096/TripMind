"""Test safety net: tests must never reach a real network host.

Only loopback connections (needed by the asyncio event loop on Windows) are allowed. Provider
adapters are exercised through injected in-process httpx transports in isolated test code.
"""

from __future__ import annotations

import socket
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from app.core.authorization import SearchAuthorizer
from app.core.config import Settings
from app.models.common import Capability

_real_connect = socket.socket.connect
_LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def _guarded_connect(self: socket.socket, address: Any) -> None:
    host = address[0] if isinstance(address, tuple) else address
    if host not in _LOOPBACK:
        raise AssertionError(f"Test attempted a real network connection to {host!r}")
    return _real_connect(self, address)


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)


FAKE_KEYS = {
    "serpapi_api_key": "test-serp-key-123",
    "geoapify_api_key": "test-geo-key-456",
    "openweather_api_key": "test-ow-key-789",
    "groq_api_key": "test-groq-key-abc",
    "groq_model": "test-model",
    "gemini_api_key": "test-gemini-key",
    "gemini_model": "test-gemini-model",
}


@pytest.fixture
def settings() -> Settings:
    # _env_file=None: never read a developer's real .env during tests.
    return Settings(_env_file=None, **FAKE_KEYS)


@pytest.fixture
def empty_settings() -> Settings:
    return Settings(_env_file=None)


@pytest.fixture
def authorizer() -> SearchAuthorizer:
    return SearchAuthorizer(run_id="test", limits={c: 5 for c in Capability})


class RecordingTransport:
    """In-process transport that records requests and returns a canned response."""

    def __init__(self, responder: Callable[[httpx.Request], httpx.Response]) -> None:
        self.requests: list[httpx.Request] = []
        self._responder = responder

    def build(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return self._responder(request)

        return httpx.MockTransport(handler)


def json_transport(body: Any, status: int = 200) -> RecordingTransport:
    return RecordingTransport(lambda _r: httpx.Response(status, json=body))


NOW = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)
