"""
Nusa Matra Data Hub — Real-Time Telemetry and Usage Statistics Service.

Collects API metrics:
- Request counts by endpoint and HTTP status
- Latency metrics (mean, min, max in milliseconds)
- Service uptime (persisted across restarts) and process uptime
- Data mode distribution (DEMO vs LIVE)
- Rolling log of recent requests for live monitoring

Persistence is optional and snapshot-based: counters stay in memory for zero
per-request I/O, then a background task flushes them to SQLite every few
seconds. Point ``NM_TELEMETRY_DB_PATH`` to a persistent volume in Coolify so
the counters survive redeploys.
"""

import asyncio
import json
import logging
import time
from collections import deque
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

import aiosqlite

from app.config import settings

logger = logging.getLogger(__name__)

WIB = ZoneInfo("Asia/Jakarta")
# v3 resets counters produced while the route-regex filter was dropping every
# real business API request in production. first_started_at is preserved.
STATE_VERSION = 3


def _iso(timestamp: Optional[float]) -> Optional[str]:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=WIB).isoformat()


def _format_uptime(seconds: int) -> str:
    """Return a compact Indonesian uptime string.

    Months are 30-day display months and weeks are 7 days. Only the most
    useful leading units are shown, so 118 hours becomes
    ``"4 hari 22 jam 19 menit"`` rather than ``"0 bulan 0 minggu ..."``.
    """
    total = max(0, int(seconds))
    day = 86400
    week = 7 * day
    month = 30 * day

    if total >= month:
        units = (("bulan", month), ("minggu", week), ("hari", day), ("jam", 3600))
    elif total >= week:
        units = (("minggu", week), ("hari", day), ("jam", 3600))
    elif total >= day:
        units = (("hari", day), ("jam", 3600), ("menit", 60))
    elif total >= 3600:
        units = (("jam", 3600), ("menit", 60), ("detik", 1))
    else:
        units = (("menit", 60), ("detik", 1))

    parts: list[str] = []
    remaining = total
    for label, size in units:
        value, remaining = divmod(remaining, size)
        if value:
            parts.append(f"{value} {label}")
    return " ".join(parts) or "0 detik"


RANGE_SECONDS = {
    "15m": 15 * 60,
    "1h": 60 * 60,
    "24h": 24 * 60 * 60,
    "7d": 7 * 24 * 60 * 60,
}


def _percentile(values: list[float], fraction: float) -> float:
    """Linear-interpolated percentile for a bounded latency sample."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 2)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * weight, 2)



class TelemetryCollector:
    """In-memory metrics collector with optional periodic SQLite snapshots."""

    SYSTEM_PATHS = {
        "/",
        "/health",
        "/stats",
        "/docs",
        "/redoc",
        "/scalar",
        "/openapi.json",
        "/favicon.ico",
        "/favicon.png",
        "/apple-touch-icon.png",
    }

    SYSTEM_PREFIXES = (
        "/static",
        "/health",
        "/stats",
        "/docs",
        "/redoc",
        "/scalar",
        "/api/v1/health",
        "/api/v1/stats",
        "/api/v1/docs",
        "/api/v1/redoc",
        "/api/v1/scalar",
        "/api/v1/openapi.json",
    )

    # Explicit business API prefixes. This is intentionally static: relying on
    # APIRoute.path_regex made production deployments sensitive to router
    # registration/order differences, which silently dropped every real API hit.
    KNOWN_API_PREFIXES = (
        "/api/v1/regions",
        "/api/v1/indicators",
        "/api/v1/boundaries",
        "/api/v1/datasets",
        "/api/v1/snapshots",
        "/api/v1/earthquakes",
    )

    def __init__(
        self,
        max_recent: int = 20,
        db_path: Optional[str] = None,
        flush_interval: Optional[float] = None,
        persistence_enabled: Optional[bool] = None,
    ):
        self.process_started_at = time.time()
        self.first_started_at = self.process_started_at
        self.last_flush_at: Optional[float] = None

        self.total_requests = 0
        self.total_latency_ms = 0.0
        self.min_latency_ms: Optional[float] = None
        self.max_latency_ms: Optional[float] = None

        self.status_counts: dict[str, int] = {}
        self.endpoint_counts: dict[str, int] = {}
        self.mode_counts: dict[str, int] = {"DEMO": 0, "LIVE": 0}

        self.recent_requests: deque[dict[str, Any]] = deque(maxlen=max_recent)
        self.request_events: deque[dict[str, Any]] = deque(maxlen=20000)
        self.latency_samples: deque[float] = deque(maxlen=5000)

        self.db_path = db_path if db_path is not None else settings.telemetry_db_path
        self.flush_interval = (
            flush_interval
            if flush_interval is not None
            else settings.telemetry_flush_interval_seconds
        )
        self.persistence_enabled = (
            persistence_enabled
            if persistence_enabled is not None
            else settings.telemetry_persistence_enabled
        )
        self._initialized = False
        self._needs_flush = False
        self._flush_task: Optional[asyncio.Task] = None

    def is_api_path(self, path: str) -> bool:
        clean = path.split("?")[0].rstrip("/") or "/"
        return clean.startswith(f"{settings.api_prefix}/") and not self.is_system_path(clean)

    def is_trackable_path(self, path: str) -> bool:
        """Track known business API prefixes only; ignore scanners and system paths."""
        clean = path.split("?")[0].rstrip("/") or "/"
        if not self.is_api_path(clean):
            return False
        return any(
            clean == prefix or clean.startswith(prefix + "/")
            for prefix in self.KNOWN_API_PREFIXES
        )

    @classmethod
    def is_system_path(cls, path: str) -> bool:
        """
        Check if a request path belongs to internal infrastructure, health checks,
        or telemetry polling that should not pollute business domain metrics.
        """
        clean = path.split("?")[0].rstrip("/") or "/"
        if clean in cls.SYSTEM_PATHS:
            return True
        return any(clean == p or clean.startswith(p + "/") for p in cls.SYSTEM_PREFIXES)

    # ------------------------------------------------------------------
    # Persistence lifecycle
    # ------------------------------------------------------------------
    @property
    def persistence_active(self) -> bool:
        return bool(self.persistence_enabled and self.db_path)

    async def initialize(self) -> None:
        """Create the telemetry table and load the previous snapshot, if any."""
        if not self.persistence_active or self._initialized:
            return

        try:
            path = Path(self.db_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                await db.execute("PRAGMA journal_mode = WAL")
                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS telemetry_state (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        first_started_at REAL,
                        total_requests INTEGER NOT NULL DEFAULT 0,
                        total_latency_ms REAL NOT NULL DEFAULT 0,
                        min_latency_ms REAL,
                        max_latency_ms REAL,
                        status_counts TEXT NOT NULL DEFAULT '{}',
                        endpoint_counts TEXT NOT NULL DEFAULT '{}',
                        mode_counts TEXT NOT NULL DEFAULT '{}',
                        recent_requests TEXT NOT NULL DEFAULT '[]',
                        latency_samples TEXT NOT NULL DEFAULT '[]',
                        updated_at REAL,
                        state_version INTEGER NOT NULL DEFAULT 1
                    )
                    """
                )
                cursor = await db.execute("PRAGMA table_info(telemetry_state)")
                columns = {row[1] for row in await cursor.fetchall()}
                if "state_version" not in columns:
                    await db.execute(
                        "ALTER TABLE telemetry_state "
                        "ADD COLUMN state_version INTEGER NOT NULL DEFAULT 1"
                    )
                if "latency_samples" not in columns:
                    await db.execute(
                        "ALTER TABLE telemetry_state "
                        "ADD COLUMN latency_samples TEXT NOT NULL DEFAULT '[]'"
                    )
                cursor = await db.execute("SELECT * FROM telemetry_state WHERE id = 1")
                row = await cursor.fetchone()
                await db.commit()

            if row is not None:
                self._restore(row)
            self._initialized = True
        except Exception:
            logger.exception("Telemetry persistence unavailable; continuing in-memory only")

    def _reset_counters(self) -> None:
        self.total_requests = 0
        self.total_latency_ms = 0.0
        self.min_latency_ms = None
        self.max_latency_ms = None
        self.status_counts = {}
        self.endpoint_counts = {}
        self.mode_counts = {"DEMO": 0, "LIVE": 0}
        self.recent_requests.clear()
        self.request_events.clear()
        self.latency_samples.clear()

    def _restore(self, row: aiosqlite.Row) -> None:
        first_started_at = row["first_started_at"]
        if first_started_at:
            self.first_started_at = min(float(first_started_at), self.process_started_at)

        state_version = int(row["state_version"] or 1)
        if state_version < STATE_VERSION:
            # v1 counters include internet scanner noise (unknown paths) and UTC
            # timestamps. Reset once, keep the service start time.
            self._reset_counters()
            self.last_flush_at = None
            self._needs_flush = True
            return

        self.total_requests = int(row["total_requests"] or 0)
        self.total_latency_ms = float(row["total_latency_ms"] or 0.0)
        self.min_latency_ms = row["min_latency_ms"]
        self.max_latency_ms = row["max_latency_ms"]
        self.status_counts = self._load_json(row["status_counts"], {})
        self.endpoint_counts = self._load_json(row["endpoint_counts"], {})
        self.mode_counts = self._load_json(row["mode_counts"], {"DEMO": 0, "LIVE": 0})
        for key in ("DEMO", "LIVE"):
            self.mode_counts.setdefault(key, 0)

        recent = self._load_json(row["recent_requests"], [])
        self.recent_requests.clear()
        self.recent_requests.extend(recent)
        self.latency_samples.clear()
        for value in self._load_json(row["latency_samples"], []):
            try:
                self.latency_samples.append(float(value))
            except (TypeError, ValueError):
                continue
        self.last_flush_at = row["updated_at"]

    @staticmethod
    def _load_json(raw: Any, fallback: Any) -> Any:
        try:
            value = json.loads(raw) if raw else fallback
            return value if isinstance(value, type(fallback)) else fallback
        except (TypeError, ValueError):
            return fallback

    async def flush(self) -> bool:
        """Write a consistent counter snapshot to SQLite."""
        if not self.persistence_active:
            return False

        try:
            await self.initialize()
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("PRAGMA journal_mode = WAL")
                await db.execute(
                    """
                    INSERT INTO telemetry_state (
                        id, first_started_at, total_requests, total_latency_ms,
                        min_latency_ms, max_latency_ms, status_counts,
                        endpoint_counts, mode_counts, recent_requests,
                        latency_samples, updated_at, state_version
                    ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        first_started_at = excluded.first_started_at,
                        total_requests = excluded.total_requests,
                        total_latency_ms = excluded.total_latency_ms,
                        min_latency_ms = excluded.min_latency_ms,
                        max_latency_ms = excluded.max_latency_ms,
                        status_counts = excluded.status_counts,
                        endpoint_counts = excluded.endpoint_counts,
                        mode_counts = excluded.mode_counts,
                        recent_requests = excluded.recent_requests,
                        latency_samples = excluded.latency_samples,
                        updated_at = excluded.updated_at,
                        state_version = excluded.state_version
                    """,
                    (
                        self.first_started_at,
                        self.total_requests,
                        self.total_latency_ms,
                        self.min_latency_ms,
                        self.max_latency_ms,
                        json.dumps(self.status_counts),
                        json.dumps(self.endpoint_counts),
                        json.dumps(self.mode_counts),
                        json.dumps(list(self.recent_requests)),
                        json.dumps(list(self.latency_samples)),
                        time.time(),
                        STATE_VERSION,
                    ),
                )
                await db.commit()
            self.last_flush_at = time.time()
            self._needs_flush = False
            return True
        except Exception:
            logger.exception("Telemetry flush failed")
            return False

    async def start(self) -> None:
        """Load persisted state and start the periodic flush loop."""
        await self.initialize()
        if not self.persistence_active or self._flush_task is not None:
            return
        if self.last_flush_at is None or self._needs_flush:
            # Persist first_started_at immediately so a fast restart still has it,
            # and persist the one-time cleanup of legacy scanner counters.
            await self.flush()
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def _flush_loop(self) -> None:
        interval = max(0.5, float(self.flush_interval))
        while True:
            await asyncio.sleep(interval)
            await self.flush()

    async def stop(self) -> None:
        """Cancel the flush loop and write one final snapshot."""
        if self._flush_task is not None:
            self._flush_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._flush_task
            self._flush_task = None
        await self.flush()

    # ------------------------------------------------------------------
    # Request recording and summary
    # ------------------------------------------------------------------
    def record_request(
        self,
        method: str,
        path: str,
        status_code: int,
        latency_ms: float,
        mode: str = "DEMO",
        route_path: Optional[str] = None,
    ) -> None:
        """Record an incoming request observation (skips system paths and unknown routes)."""
        if not self.is_trackable_path(path):
            return

        self.total_requests += 1
        self.total_latency_ms += latency_ms

        if self.min_latency_ms is None or latency_ms < self.min_latency_ms:
            self.min_latency_ms = latency_ms
        if self.max_latency_ms is None or latency_ms > self.max_latency_ms:
            self.max_latency_ms = latency_ms

        status_key = str(status_code)
        self.status_counts[status_key] = self.status_counts.get(status_key, 0) + 1

        # Normalize path for aggregation (remove query params and trailing slash)
        clean_path = path.split("?")[0]
        if len(clean_path) > 1:
            clean_path = clean_path.rstrip("/")
        endpoint_key = route_path if route_path and self.is_api_path(route_path) else clean_path
        self.endpoint_counts[endpoint_key] = self.endpoint_counts.get(endpoint_key, 0) + 1

        mode_upper = mode.upper() if mode else "DEMO"
        self.mode_counts[mode_upper] = self.mode_counts.get(mode_upper, 0) + 1
        self.latency_samples.append(latency_ms)

        # Append to recent requests queue (WIB, independent of VPS timezone)
        observed_at = time.time()
        now_iso = datetime.fromtimestamp(observed_at, tz=WIB).strftime("%H:%M:%S")
        self.recent_requests.append({
            "time": now_iso,
            "method": method,
            "path": clean_path,
            "status": status_code,
            "latency_ms": round(latency_ms, 2),
            "mode": mode_upper,
        })
        self.request_events.append({
            "ts": observed_at,
            "method": method,
            "path": clean_path,
            "endpoint": endpoint_key,
            "status": status_code,
            "latency_ms": round(latency_ms, 2),
            "mode": mode_upper,
        })

    def get_summary(self, range_key: str = "all") -> dict[str, Any]:
        """Generate comprehensive telemetry statistics dictionary.

        ``range_key`` accepts ``all``, ``15m``, ``1h``, ``24h``, or ``7d``.
        Range views use the bounded in-memory event log; lifetime counters
        remain the source of truth for ``all``.
        """
        now = time.time()
        process_uptime = max(0, int(now - self.process_started_at))
        service_uptime = max(0, int(now - self.first_started_at))
        range_key = (range_key or "all").lower()
        if range_key not in RANGE_SECONDS:
            range_key = "all"

        if range_key == "all":
            total_requests = self.total_requests
            total_latency_ms = self.total_latency_ms
            min_latency = self.min_latency_ms
            max_latency = self.max_latency_ms
            status_counts = self.status_counts
            endpoint_counts = self.endpoint_counts
            mode_counts = self.mode_counts
            latency_values = list(self.latency_samples)
            if not latency_values:
                latency_values = [row["latency_ms"] for row in self.recent_requests]
            recent_requests = list(self.recent_requests)[::-1]
        else:
            cutoff = now - RANGE_SECONDS[range_key]
            events = [event for event in self.request_events if event["ts"] >= cutoff]
            total_requests = len(events)
            total_latency_ms = sum(event["latency_ms"] for event in events)
            latency_values = [event["latency_ms"] for event in events]
            min_latency = min(latency_values) if latency_values else None
            max_latency = max(latency_values) if latency_values else None
            status_counts = {}
            endpoint_counts = {}
            mode_counts = {"DEMO": 0, "LIVE": 0}
            for event in events:
                status_key = str(event["status"])
                status_counts[status_key] = status_counts.get(status_key, 0) + 1
                endpoint_key = event["endpoint"]
                endpoint_counts[endpoint_key] = endpoint_counts.get(endpoint_key, 0) + 1
                mode = event["mode"]
                mode_counts[mode] = mode_counts.get(mode, 0) + 1
            recent_requests = [
                {
                    "time": datetime.fromtimestamp(event["ts"], tz=WIB).strftime("%H:%M:%S"),
                    "method": event["method"],
                    "path": event["path"],
                    "status": event["status"],
                    "latency_ms": event["latency_ms"],
                    "mode": event["mode"],
                }
                for event in sorted(events, key=lambda row: row["ts"], reverse=True)[:20]
            ]

        avg_latency = (
            round(total_latency_ms / total_requests, 2)
            if total_requests > 0
            else 0.0
        )

        # Sort endpoints by popularity, keeping only known API routes.
        top_endpoints = sorted(
            [
                {"path": p, "count": c}
                for p, c in endpoint_counts.items()
                if self.is_trackable_path(p)
            ],
            key=lambda x: x["count"],
            reverse=True,
        )[:8]

        # Calculate success rate (2xx)
        success_count = sum(
            c for code, c in status_counts.items() if code.startswith("2")
        )
        success_rate = (
            round((success_count / total_requests) * 100, 1)
            if total_requests > 0
            else 100.0
        )

        return {
            # Backwards-compatible fields. "uptime" is now service uptime,
            # which survives redeploys when persistence is enabled.
            "timezone": "Asia/Jakarta",
            "server_time": datetime.now(WIB).isoformat(),
            "range": range_key,
            "uptime_seconds": service_uptime,
            "uptime_formatted": _format_uptime(service_uptime),
            "service_uptime_seconds": service_uptime,
            "service_uptime_formatted": _format_uptime(service_uptime),
            "process_uptime_seconds": process_uptime,
            "process_uptime_formatted": _format_uptime(process_uptime),
            "first_started_at": _iso(self.first_started_at),
            "persistence": {
                "enabled": self.persistence_active,
                "initialized": self._initialized,
                "flush_interval_seconds": self.flush_interval,
                "last_flush_at": _iso(self.last_flush_at),
            },
            "total_requests": total_requests,
            "success_rate_pct": success_rate,
            "latency": {
                "avg_ms": avg_latency,
                "min_ms": round(min_latency or 0.0, 2),
                "max_ms": round(max_latency or 0.0, 2),
                "p50_ms": _percentile(latency_values, 0.50),
                "p95_ms": _percentile(latency_values, 0.95),
                "p99_ms": _percentile(latency_values, 0.99),
            },
            "status_codes": status_counts,
            "modes": mode_counts,
            "top_endpoints": top_endpoints,
            "recent_requests": recent_requests,
        }


# Global singleton instance
telemetry = TelemetryCollector()
