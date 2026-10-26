"""
Security middleware regression tests.

Covers anonymous access, API-key scopes, rate limits, body limits, security
headers, CORS rejection, and trusted-proxy IP resolution.
"""

import pytest
from starlette.requests import Request

from app.config import settings
from app.middleware.security import resolve_client_ip
from app.services.api_key import hash_api_key
from app.services.composite_service import clear_composite_cache
from app.services.rate_limiter import rate_limiter


@pytest.fixture(autouse=True)
def reset_security_state():
    rate_limiter.reset()
    clear_composite_cache()
    yield
    rate_limiter.reset()
    clear_composite_cache()


def _request(peer: str, forwarded_for: str | None = None, cf_ip: str | None = None) -> Request:
    headers = []
    if forwarded_for:
        headers.append((b"x-forwarded-for", forwarded_for.encode()))
    if cf_ip:
        headers.append((b"cf-connecting-ip", cf_ip.encode()))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/regions",
        "query_string": b"",
        "headers": headers,
        "client": (peer, 12345),
        "server": ("test", 80),
        "scheme": "http",
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_security_headers_on_success(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "geolocation=()" in resp.headers["Permissions-Policy"]
    assert resp.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert resp.headers["Content-Security-Policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert resp.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_request_id_is_preserved_and_hsts_respects_https(client):
    resp = await client.get(
        "/api/v1/health",
        headers={"X-Request-ID": "judge-request-123", "X-Forwarded-Proto": "https"},
    )
    assert resp.headers["X-Request-ID"] == "judge-request-123"
    assert "max-age=31536000" in resp.headers["Strict-Transport-Security"]


@pytest.mark.asyncio
async def test_cors_rejects_foreign_origin(client):
    resp = await client.get(
        "/api/v1/health",
        headers={"Origin": "https://evil.example"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") is None


@pytest.mark.asyncio
async def test_health_is_exempt_from_rate_limit(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_report_only", False)
    monkeypatch.setattr(settings, "rate_limit_read_per_minute", 1)
    monkeypatch.setattr(settings, "rate_limit_read_burst", 1)
    rate_limiter.reset()

    first = await client.get("/api/v1/health")
    second = await client.get("/api/v1/health")
    assert first.status_code == 200
    assert second.status_code == 200


@pytest.mark.asyncio
async def test_read_rate_limit_returns_429_with_headers_and_cors(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_report_only", False)
    monkeypatch.setattr(settings, "rate_limit_read_per_minute", 1)
    monkeypatch.setattr(settings, "rate_limit_read_burst", 1)
    rate_limiter.reset()

    first = await client.get("/api/v1/regions")
    second = await client.get(
        "/api/v1/regions",
        headers={"Origin": "http://localhost:5173"},
    )

    assert first.status_code == 200
    assert second.status_code == 429
    body = second.json()
    assert body["code"] == "RATE_LIMITED"
    assert second.headers["Retry-After"]
    assert second.headers["X-RateLimit-Limit"] == "1"
    assert second.headers["X-RateLimit-Remaining"] == "0"
    assert second.headers["access-control-allow-origin"] == "http://localhost:5173"


@pytest.mark.asyncio
async def test_docs_bucket_is_separate_from_business_quota(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_report_only", False)
    monkeypatch.setattr(settings, "rate_limit_docs_per_minute", 1)
    monkeypatch.setattr(settings, "rate_limit_docs_burst", 1)
    rate_limiter.reset()

    assert (await client.get("/openapi.json")).status_code == 200
    limited = await client.get("/openapi.json")
    assert limited.status_code == 429
    assert limited.json()["code"] == "RATE_LIMITED"

    # The docs bucket must not consume the business read bucket.
    assert (await client.get("/api/v1/regions")).status_code == 200


@pytest.mark.asyncio
async def test_body_size_limit_rejects_large_content_length(client):
    payload = {"weights": {"x" * 20000: 1}}
    resp = await client.post("/api/v1/indicators/composite-query", json=payload)
    assert resp.status_code == 413
    assert resp.json()["code"] == "PAYLOAD_TOO_LARGE"


@pytest.mark.asyncio
async def test_body_size_limit_rejects_chunked_body(client):
    async def oversized_body():
        yield b"{" + b" " * 20000 + b"}"

    resp = await client.post(
        "/api/v1/indicators/composite-query",
        content=oversized_body(),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 413
    assert resp.json()["code"] == "PAYLOAD_TOO_LARGE"


@pytest.mark.asyncio
async def test_composite_component_limit(client):
    payload = {"weights": {f"indicator_{index}": 1 for index in range(34)}}
    resp = await client.post("/api/v1/indicators/composite-query", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_api_key_scopes_and_invalid_key(client, monkeypatch):
    monkeypatch.setattr(settings, "app_api_key_hash", hash_api_key("app-key"))
    monkeypatch.setattr(settings, "admin_token_hash", hash_api_key("admin-key"))
    rate_limiter.reset()

    valid = await client.get("/api/v1/regions", headers={"X-API-Key": "app-key"})
    assert valid.status_code == 200
    assert valid.headers["X-API-Key-Name"] == "app"

    invalid = await client.get("/api/v1/regions", headers={"X-API-Key": "wrong"})
    assert invalid.status_code == 401
    assert invalid.json()["code"] == "INVALID_API_KEY"

    admin_on_composite = await client.post(
        "/api/v1/indicators/composite-query",
        headers={"X-API-Key": "admin-key"},
        json={"weights": {"soc_poverty_rate": 5000, "hlt_life_expectancy": 5000}},
    )
    assert admin_on_composite.status_code == 403
    assert admin_on_composite.json()["code"] == "INSUFFICIENT_SCOPE"

    app_on_composite = await client.post(
        "/api/v1/indicators/composite-query",
        headers={"X-API-Key": "app-key"},
        json={"weights": {"soc_poverty_rate": 5000, "hlt_life_expectancy": 5000}},
    )
    assert app_on_composite.status_code == 200


def test_forwarded_headers_ignored_from_untrusted_peer(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_ips", "10.0.0.0/8")
    assert resolve_client_ip(_request("8.8.8.8", "1.2.3.4")) == "8.8.8.8"
    assert resolve_client_ip(_request("8.8.8.8", "1.2.3.4", "5.6.7.8")) == "8.8.8.8"


def test_forwarded_headers_used_from_trusted_proxy(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_ips", "10.0.0.0/8")
    assert resolve_client_ip(_request("10.0.0.5", "1.2.3.4")) == "1.2.3.4"
    assert resolve_client_ip(_request("10.0.0.5", "1.2.3.4, 10.0.0.5")) == "1.2.3.4"
    assert resolve_client_ip(_request("10.0.0.5", cf_ip="5.6.7.8")) == "5.6.7.8"


@pytest.mark.asyncio
async def test_stats_response_omits_persistence_internals(client):
    resp = await client.get("/api/v1/stats")
    assert resp.status_code == 200
    assert "persistence" not in resp.json()["data"]


@pytest.mark.asyncio
async def test_root_dashboard_csp_allows_its_assets(client):
    resp = await client.get("/", headers={"Accept": "text/html"})
    assert resp.status_code == 200
    csp = resp.headers["Content-Security-Policy"]
    assert "cdn.tailwindcss.com" in csp
    assert "fonts.googleapis.com" in csp


def test_security_list_settings_accept_comma_separated(monkeypatch):
    from app.config import Settings

    monkeypatch.setenv("NM_ALLOWED_HOSTS", "api.example.com,localhost")
    monkeypatch.setenv("NM_CORS_ORIGINS", "https://app.example.com,http://localhost:5173")
    loaded = Settings()
    assert loaded.allowed_hosts == ["api.example.com", "localhost"]
    assert loaded.cors_origins == ["https://app.example.com", "http://localhost:5173"]
