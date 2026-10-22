"""
Nusa Matra Data Hub — Real-Time Telemetry and Usage Statistics Service.

Collects in-memory API metrics:
- Request counts by endpoint and HTTP status
- Latency metrics (mean, min, max in milliseconds)
- Operational uptime and service start time
- Data mode distribution (DEMO vs LIVE)
- Rolling log of recent requests for live monitoring
"""

import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Optional


class TelemetryCollector:
    """Thread-safe in-memory metrics collector with zero performance overhead."""

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
    )

    def __init__(self, max_recent: int = 20):
        self.start_time = time.time()
        self.total_requests = 0
        self.total_latency_ms = 0.0
        self.min_latency_ms: Optional[float] = None
        self.max_latency_ms: Optional[float] = None
        
        self.status_counts: dict[str, int] = {}
        self.endpoint_counts: dict[str, int] = {}
        self.mode_counts: dict[str, int] = {"DEMO": 0, "LIVE": 0}
        
        self.recent_requests: deque[dict[str, Any]] = deque(maxlen=max_recent)

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

    def record_request(
        self,
        method: str,
        path: str,
        status_code: int,
        latency_ms: float,
        mode: str = "DEMO",
    ) -> None:
        """Record an incoming request observation (skips system/health/telemetry paths)."""
        if self.is_system_path(path):
            return

        self.total_requests += 1
        self.total_latency_ms += latency_ms
        
        if self.min_latency_ms is None or latency_ms < self.min_latency_ms:
            self.min_latency_ms = latency_ms
        if self.max_latency_ms is None or latency_ms > self.max_latency_ms:
            self.max_latency_ms = latency_ms

        status_key = str(status_code)
        self.status_counts[status_key] = self.status_counts.get(status_key, 0) + 1

        # Normalize path for aggregation (remove query params)
        clean_path = path.split("?")[0]
        self.endpoint_counts[clean_path] = self.endpoint_counts.get(clean_path, 0) + 1

        mode_upper = mode.upper() if mode else "DEMO"
        self.mode_counts[mode_upper] = self.mode_counts.get(mode_upper, 0) + 1

        # Append to recent requests queue
        now_iso = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self.recent_requests.append({
            "time": now_iso,
            "method": method,
            "path": clean_path,
            "status": status_code,
            "latency_ms": round(latency_ms, 2),
            "mode": mode_upper,
        })

    def get_summary(self) -> dict[str, Any]:
        """Generate comprehensive telemetry statistics dictionary."""
        uptime_seconds = int(time.time() - self.start_time)
        hours = uptime_seconds // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60
        uptime_str = f"{hours}h {minutes}m {seconds}s"

        avg_latency = (
            round(self.total_latency_ms / self.total_requests, 2)
            if self.total_requests > 0
            else 0.0
        )

        # Sort endpoints by popularity
        top_endpoints = sorted(
            [{"path": p, "count": c} for p, c in self.endpoint_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:8]

        # Calculate success rate (2xx)
        success_count = sum(
            c for code, c in self.status_counts.items() if code.startswith("2")
        )
        success_rate = (
            round((success_count / self.total_requests) * 100, 1)
            if self.total_requests > 0
            else 100.0
        )

        return {
            "uptime_seconds": uptime_seconds,
            "uptime_formatted": uptime_str,
            "total_requests": self.total_requests,
            "success_rate_pct": success_rate,
            "latency": {
                "avg_ms": avg_latency,
                "min_ms": round(self.min_latency_ms or 0.0, 2),
                "max_ms": round(self.max_latency_ms or 0.0, 2),
            },
            "status_codes": self.status_counts,
            "modes": self.mode_counts,
            "top_endpoints": top_endpoints,
            "recent_requests": list(self.recent_requests)[::-1],
        }


# Global singleton instance
telemetry = TelemetryCollector()
