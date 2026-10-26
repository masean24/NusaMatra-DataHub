"""
In-memory token-bucket rate limiting primitives.

The limiter is intentionally small and dependency-free. It is sufficient for a
single-process deployment behind Coolify/Traefik. If the service is scaled to
multiple workers or replicas, counters must move to a shared store such as
Redis; the interface here is designed so that swap can happen behind
``TokenBucketLimiter`` without touching middleware code.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class RateLimitDecision:
    """Result of one token-bucket check."""

    allowed: bool
    limit: int
    remaining: int
    retry_after: int
    reset_at: int
    bucket: str


@dataclass
class _BucketState:
    tokens: float
    updated_at: float


class TokenBucketLimiter:
    """Token bucket keyed by an opaque caller-provided string."""

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
        cleanup_interval: int = 1000,
        max_idle_seconds: float = 600.0,
    ) -> None:
        self._clock = clock
        self._wall_clock = wall_clock
        self._cleanup_interval = max(1, cleanup_interval)
        self._max_idle_seconds = max(60.0, max_idle_seconds)
        self._states: dict[str, _BucketState] = {}
        self._checks = 0

    def check(
        self,
        key: str,
        limit_per_minute: int,
        burst: int,
        bucket: str = "",
    ) -> RateLimitDecision:
        """Consume one token for ``key`` if available.

        ``limit_per_minute`` is the sustained refill rate. ``burst`` is the
        bucket capacity. Limits <= 0 are treated as a single-request bucket.
        """
        limit = max(1, int(limit_per_minute))
        capacity = max(1, int(burst))
        rate_per_second = limit / 60.0

        now = self._clock()
        state = self._states.get(key)
        if state is None:
            tokens = float(capacity)
        else:
            elapsed = max(0.0, now - state.updated_at)
            tokens = min(float(capacity), state.tokens + elapsed * rate_per_second)

        allowed = tokens >= 1.0
        if allowed:
            tokens -= 1.0
            retry_after = 0
        else:
            retry_after = max(1, int(math.ceil((1.0 - tokens) / rate_per_second)))

        self._states[key] = _BucketState(tokens=tokens, updated_at=now)
        self._checks += 1
        if self._checks % self._cleanup_interval == 0:
            self.cleanup(now)

        return RateLimitDecision(
            allowed=allowed,
            limit=limit,
            remaining=max(0, int(tokens)),
            retry_after=retry_after,
            reset_at=int(self._wall_clock() + retry_after),
            bucket=bucket,
        )

    def cleanup(self, now: float | None = None) -> None:
        """Drop states that have been idle long enough to be irrelevant."""
        current = self._clock() if now is None else now
        stale = [
            key
            for key, state in self._states.items()
            if current - state.updated_at > self._max_idle_seconds
        ]
        for key in stale:
            self._states.pop(key, None)

    def reset(self) -> None:
        """Clear all counters. Intended for tests and operational resets."""
        self._states.clear()
        self._checks = 0


rate_limiter = TokenBucketLimiter()
