"""Per-planning-run authorization for external calls.

Every adapter method requires a ``SearchAuthorizer`` and calls ``authorize`` immediately before
the network request. A new authorizer is created for each explicit user-initiated planning
action, so counters and de-duplication state are never shared between runs. There is no
global/default authorizer: code without one cannot reach a provider.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Mapping
from typing import Any

from app.core.errors import (
    DuplicateSearchError,
    ToolAuthorizationError,
    ToolCallLimitExceeded,
)
from app.models.common import Capability


def fingerprint(provider: str, params: Mapping[str, Any]) -> str:
    """Stable identity of a search. Callers must pass params WITHOUT credentials."""
    canonical = json.dumps({"p": provider, "q": params}, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


class SearchAuthorizer:
    def __init__(self, *, run_id: str, limits: Mapping[Capability, int]) -> None:
        self.run_id = run_id
        self._limits = dict(limits)
        self._counts: dict[Capability, int] = {}
        self._seen: set[str] = set()
        self._closed = False
        self._lock = threading.Lock()

    def authorize(self, capability: Capability, *, search_fingerprint: str) -> None:
        with self._lock:
            if self._closed:
                raise ToolAuthorizationError(
                    "This planning run is closed; no further external calls are allowed.",
                    capability=capability,
                )
            limit = self._limits.get(capability, 0)
            used = self._counts.get(capability, 0)
            key = f"{capability.value}:{search_fingerprint}"
            if key in self._seen:
                raise DuplicateSearchError(
                    "An identical search was already made in this planning run; reuse its result.",
                    capability=capability,
                )
            if used >= limit:
                raise ToolCallLimitExceeded(
                    f"Limit of {limit} {capability.value} call(s) per planning run reached.",
                    capability=capability,
                    details={"limit": limit},
                )
            self._seen.add(key)
            self._counts[capability] = used + 1

    def close(self) -> None:
        with self._lock:
            self._closed = True

    def usage(self) -> dict[str, int]:
        with self._lock:
            return {c.value: n for c, n in self._counts.items()}
