"""
Composite cache regression tests: deterministic hits, key isolation, and
single-flight behavior for identical concurrent requests.
"""

import asyncio

import aiosqlite
import pytest

from app.config import settings
from app.models.indicators import CompositeQueryRequest
from app.services import composite_service
from app.services.composite_service import (
    clear_composite_cache,
    compute_composite_scores_cached,
    get_composite_cache_info,
)

WEIGHTS = {
    "soc_poverty_rate": 3000,
    "hlt_stunting_prevalence": 3000,
    "inf_safe_water_pct": 2000,
    "inf_safe_sanitation_pct": 2000,
}


@pytest.fixture(autouse=True)
async def reset_cache():
    clear_composite_cache()
    yield
    clear_composite_cache()


async def _db():
    db = await aiosqlite.connect(settings.database_path)
    db.row_factory = aiosqlite.Row
    return db


@pytest.mark.asyncio
async def test_cache_hit_is_deterministic():
    request = CompositeQueryRequest(weights=WEIGHTS)
    db = await _db()
    try:
        first = await compute_composite_scores_cached(
            db, request, snapshot_id=settings.default_snapshot_id, mode="DEMO"
        )
        second = await compute_composite_scores_cached(
            db, request, snapshot_id=settings.default_snapshot_id, mode="DEMO"
        )
    finally:
        await db.close()

    info = get_composite_cache_info()
    assert info["misses"] == 1
    assert info["hits"] == 1
    assert first.model_dump() == second.model_dump()


@pytest.mark.asyncio
async def test_cache_key_isolates_different_weights():
    request_a = CompositeQueryRequest(weights=WEIGHTS)
    request_b = CompositeQueryRequest(
        weights={"soc_poverty_rate": 5000, "hlt_life_expectancy": 5000}
    )
    db = await _db()
    try:
        await compute_composite_scores_cached(db, request_a, mode="DEMO")
        await compute_composite_scores_cached(db, request_b, mode="DEMO")
    finally:
        await db.close()

    info = get_composite_cache_info()
    assert info["entries"] == 2
    assert info["misses"] == 2
    assert info["hits"] == 0


@pytest.mark.asyncio
async def test_identical_concurrent_requests_single_flight(monkeypatch):
    request = CompositeQueryRequest(weights=WEIGHTS)
    calls = 0
    original = composite_service.compute_composite_scores

    async def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return await original(*args, **kwargs)

    monkeypatch.setattr(composite_service, "compute_composite_scores", counted)
    db = await _db()
    try:
        results = await asyncio.gather(
            *(
                compute_composite_scores_cached(
                    db, request, snapshot_id=settings.default_snapshot_id, mode="DEMO"
                )
                for _ in range(5)
            )
        )
    finally:
        await db.close()

    assert calls == 1
    assert all(result.model_dump() == results[0].model_dump() for result in results)
    assert get_composite_cache_info()["misses"] == 1
