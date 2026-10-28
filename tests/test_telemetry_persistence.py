"""Tests for telemetry persistence across process restarts."""

import json
import sqlite3

import pytest

from app.services.telemetry_service import TelemetryCollector, _format_uptime


def test_format_uptime_uses_readable_units():
    assert _format_uptime(118 * 3600 + 19 * 60 + 54) == "4 hari 22 jam 19 menit"
    assert _format_uptime(8 * 86400 + 3 * 3600) == "1 minggu 1 hari 3 jam"
    assert _format_uptime(31 * 86400 + 2 * 3600) == "1 bulan 1 hari 2 jam"
    assert _format_uptime(14 * 3600 + 28 * 60 + 19) == "14 jam 28 menit 19 detik"
    assert _format_uptime(0) == "0 detik"


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

    collector.record_request("GET", "/api/v1/regions", 200, 1.0, "DEMO")
    collector.record_request(
        "GET",
        "/api/v1/indicators/soc_hdi/values",
        200,
        1.0,
        "DEMO",
        route_path="/api/v1/indicators/{indicator_id}/values",
    )
    collector.record_request("POST", "/api/v1/indicators/composite-query", 200, 1.0, "DEMO")
    collector.record_request("GET", "/api/v1/openapi.json", 200, 1.0, "DEMO")
    collector.record_request("GET", "/.gitmodules", 404, 1.0, "DEMO")
    collector.record_request("GET", "/api/v1/unknown", 404, 1.0, "DEMO")
    collector.record_request("GET", "/api/v1/stats", 200, 1.0, "DEMO")

    assert collector.total_requests == 3
    assert collector.endpoint_counts == {
        "/api/v1/regions": 1,
        "/api/v1/indicators/{indicator_id}/values": 1,
        "/api/v1/indicators/composite-query": 1,
    }
    summary = collector.get_summary()
    assert summary["timezone"] == "Asia/Jakarta"
    assert summary["first_started_at"].endswith("+07:00")
    assert summary["recent_requests"][0]["path"] == "/api/v1/indicators/composite-query"
    assert {row["path"] for row in summary["top_endpoints"]} == {
        "/api/v1/regions",
        "/api/v1/indicators/{indicator_id}/values",
        "/api/v1/indicators/composite-query",
    }


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
