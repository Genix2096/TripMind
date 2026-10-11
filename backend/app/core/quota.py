import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import ClassVar

from app.core.config import get_settings


@dataclass
class TokenReservation:
    timestamp: float
    estimated_input: int
    requested_output: int
    actual_total: int | None = None

    @property
    def cost(self) -> int:
        return self.actual_total if self.actual_total is not None else (self.estimated_input + self.requested_output)


class TokenQuotaManager:
    """
    A global, concurrency-safe rolling-window token manager.
    Enforces a strict Tokens-Per-Minute limit across all concurrent sessions.
    """
    _instance: ClassVar['TokenQuotaManager | None'] = None
    logger = logging.getLogger("app.core.quota")

    def __init__(self, limit_tpm: int):
        self.limit_tpm = limit_tpm
        self.reservations: deque[TokenReservation] = deque()
        self.queue_lock = asyncio.Lock()
        
    @classmethod
    def get_instance(cls) -> 'TokenQuotaManager':
        if cls._instance is None:
            settings = get_settings()
            cls._instance = cls(limit_tpm=settings.limit_tpm)
        return cls._instance

    def _cleanup_old_reservations(self, now: float) -> None:
        """Remove reservations older than 60 seconds."""
        cutoff = now - 60.0
        while self.reservations and self.reservations[0].timestamp < cutoff:
            self.reservations.popleft()

    def _current_usage(self, now: float) -> int:
        """Calculate total token usage within the 60-second window."""
        self._cleanup_old_reservations(now)
        return sum(r.cost for r in self.reservations)

    async def acquire(self, estimated_input: int, requested_output: int, timeout_seconds: float = 45.0) -> TokenReservation:
        """
        Wait until there is enough TPM capacity to schedule this request.
        Returns a TokenReservation object which should be reconciled after the API call.
        """
        cost = estimated_input + requested_output
        if cost > self.limit_tpm:
            from app.core.errors import ProviderRequestError
            from app.models.common import Capability
            raise ProviderRequestError(
                f"Request too large. Estimated {estimated_input} + {requested_output} requested output = {cost} tokens, exceeding safe threshold {self.limit_tpm}.",
                provider="groq",
                capability=Capability.LLM
            )

        start_wait = time.time()
        
        while True:
            now = time.time()
            if now - start_wait > timeout_seconds:
                self.logger.warning(f"Timeout waiting for token quota after {timeout_seconds}s. cost={cost}, limit={self.limit_tpm}")
                from app.core.errors import ProviderRequestError
                from app.models.common import Capability
                raise ProviderRequestError(
                    f"Timeout waiting for token quota after {timeout_seconds}s.",
                    provider="groq",
                    capability=Capability.LLM
                )

            async with self.queue_lock:
                usage = self._current_usage(now)
                
                if usage + cost <= self.limit_tpm:
                    # Allocate
                    reservation = TokenReservation(timestamp=now, estimated_input=estimated_input, requested_output=requested_output)
                    self.reservations.append(reservation)
                    self.logger.debug(f"Quota acquired: usage={usage}, cost={cost}, est_input={estimated_input}, req_out={requested_output}")
                    return reservation

                # Find when the oldest reservation expires and wait
                if self.reservations:
                    oldest = self.reservations[0]
                    wait_time = (oldest.timestamp + 60.0) - now
                else:
                    # Should never happen if usage > 0, but default
                    wait_time = 1.0
                    
            remaining_timeout = timeout_seconds - (now - start_wait)
            if wait_time > remaining_timeout:
                self.logger.warning(f"Timeout inevitable. Wait {wait_time:.1f}s exceeds remaining {remaining_timeout:.1f}s. cost={cost}, limit={self.limit_tpm}")
                from app.core.errors import ProviderRequestError
                from app.models.common import Capability
                raise ProviderRequestError(
                    f"Timeout waiting for token quota after {timeout_seconds}s.",
                    provider="groq",
                    capability=Capability.LLM
                )
                    
            if wait_time > 0:
                self.logger.debug(f"Waiting {wait_time:.1f}s for quota. usage={usage}, cost={cost}, limit={self.limit_tpm}")
                await asyncio.sleep(min(wait_time, 2.0))

    def reconcile(self, reservation: TokenReservation, actual_total: int) -> None:
        """Update a reservation with the actual token usage returned by the API."""
        reservation.actual_total = actual_total
