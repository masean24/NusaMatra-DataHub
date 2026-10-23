"""Tests for telemetry persistence across process restarts."""

import json
import re
import sqlite3
from types import SimpleNamespace

import pytest

from app.services.telemetry_service import TelemetryCollector


@pytest.mark.asyncio
async def test_telemetry_persists_counters_and_uptime(tmp_path):
    db_path = str(tmp_path / "telemetry.db")

    first_process = TelemetryCollector(db_path=db_path, flush_interval=60)
    await first_process.initialize()
    first_process.record_request("GET", "/api/v1/regions", 200, 12.5, "LIVE")
    first_process.record_request("GET", "/api/v1/indicators", 500, 30.0, "DEMO")
    first_process.record_request("GET", "/health", 200, 1.0, "LIVE")  # ignored
    assert first_process.total_requests == 2
    assert await first_process.flush() is True

    first_started_at = first_process.first_started_at

    second_process = TelemetryCollector(db_path=db_path)
    await second_process.initialize()
    summary = second_process.get_summary()

    assert summary["total_requests"] == 2
    assert summary["status_codes"] == {"200": 1, "500": 1}
    assert summary["modes"] == {"DEMO": 1, "LIVE": 1}
    assert summary["latency"]["min_ms"] == 12.5
    assert summary["latency"]["max_ms"] == 30.0
    assert len(summary["recent_requests"]) == 2
    assert {row["path"] for row in summary["recent_requests"]} == {
        "/api/v1/regions",
        "/api/v1/indicators",
    }

    # Service uptime survives restart; process uptime starts fresh.
    assert summary["first_started_at"] == first_process.get_summary()["first_started_at"]
    assert second_process.first_started_at == pytest.approx(first_started_at)
    assert summary["service_uptime_seconds"] >= summary["process_uptime_seconds"] - 1
    assert summary["persistence"]["enabled"] is True
    assert summary["persistence"]["last_flush_at"] is not None


@pytest.mark.asyncio
async def test_telemetry_persistence_can_be_disabled(tmp_path):
    collector = TelemetryCollector(
        db_path=str(tmp_path / "telemetry.db"),
        persistence_enabled=False,
    )
    await collector.initialize()
    collector.record_request("GET", "/api/v1/regions", 200, 5.0, "DEMO")

    assert collector.persistence_active is False
    assert await collector.flush() is False

    summary = collector.get_summary()
    assert summary["total_requests"] == 1
    assert summary["persistence"]["enabled"] is False
    assert summary["persistence"]["last_flush_at"] is None


@pytest.mark.asyncio
async def test_scanner_paths_are_ignored_and_time_is_wib(tmp_path):
    collector = TelemetryCollector(
        db_path=str(tmp_path / "telemetry.db"),
        persistence_enabled=False,
    )
    collector.configure_routes(
        [
            SimpleNamespace(
                path="/api/v1/regions",
                path_regex=re.compile(r"/api/v1/regions"),
            ),
            SimpleNamespace(
                path="/api/v1/indicators/{indicator_id}/values",
                path_regex=re.compile(r"/api/v1/indicators/[^/]+/values"),
            ),
        ]
    )

    collector.record_request("GET", "/api/v1/regions", 200, 1.0, "DEMO")
    collector.record_request(
        "GET",
        "/api/v1/indicators/soc_hdi/values",
        200,
        1.0,
        "DEMO",
        route_path="/api/v1/indicators/{indicator_id}/values",
    )
    collector.record_request("GET", "/.gitmodules", 404, 1.0, "DEMO")
    collector.record_request("GET", "/api/v1/unknown", 404, 1.0, "DEMO")

    assert collector.total_requests == 2
    assert collector.endpoint_counts == {
        "/api/v1/regions": 1,
        "/api/v1/indicators/{indicator_id}/values": 1,
    }
    summary = collector.get_summary()
    assert summary["timezone"] == "Asia/Jakarta"
    assert summary["first_started_at"].endswith("+07:00")
    assert summary["recent_requests"][0]["path"] == "/api/v1/indicators/soc_hdi/values"


@pytest.mark.asyncio
async def test_legacy_scanner_counters_are_reset_once(tmp_path):
    db_path = str(tmp_path / "telemetry.db")
    first_process = TelemetryCollector(db_path=db_path)
    await first_process.initialize()
    first_started_at = first_process.first_started_at
    await first_process.flush()

    with sqlite3.connect(db_path) as db:
        db.execute(
            "UPDATE telemetry_state SET state_version = 1, total_requests = 999, "
            "endpoint_counts = ?, status_counts = ?, recent_requests = ? WHERE id = 1",
            (
                json.dumps({"/.gitmodules": 500, "/runtime.js": 499}),
                json.dumps({"404": 999}),
                json.dumps([{"time": "00:00:00", "path": "/.gitmodules"}]),
            ),
        )
        db.commit()

    second_process = TelemetryCollector(db_path=db_path)
    await second_process.initialize()
    summary = second_process.get_summary()

    assert summary["total_requests"] == 0
    assert summary["status_codes"] == {}
    assert summary["top_endpoints"] == []
    assert summary["recent_requests"] == []
    assert second_process.first_started_at == pytest.approx(first_started_at)
