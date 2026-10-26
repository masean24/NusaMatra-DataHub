"""
Security middleware: trusted proxy IP resolution, optional API keys, tiered
rate limiting, body-size limits, request IDs, and browser security headers.

Design constraints:
- Read endpoints remain anonymous; API keys only add identity and quota.
- No API key bypasses rate limits completely.
- Proxy headers are trusted only when the direct peer is in
  ``NM_TRUSTED_PROXY_IPS``.
- ``429`` and ``413`` responses still pass through CORS.
"""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import re
import uuid
from typing import Iterable

from starlette.datastructures import MutableHeaders
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import settings
from app.services.api_key import API_KEY_HEADER, ApiKeyIdentity, resolve_api_key
from app.services.rate_limiter import RateLimitDecision, rate_limiter

logger = logging.getLogger(__name__)

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _clean_path(path: str) -> str:
    clean = path.split("?")[0]
    return clean.rstrip("/") or "/"


def _is_health_path(path: str) -> bool:
    return path in {"/health", f"{settings.api_prefix}/health"}


def _is_docs_path(path: str) -> bool:
    return (
        path in {"/docs", "/scalar", "/redoc", "/openapi.json"}
        or path.startswith(f"{settings.api_prefix}/docs")
        or path.startswith(f"{settings.api_prefix}/scalar")
        or path.startswith(f"{settings.api_prefix}/redoc")
        or path == f"{settings.api_prefix}/openapi.json"
    )


def _is_stats_path(path: str) -> bool:
    return path in {"/stats", f"{settings.api_prefix}/stats", f"{settings.api_prefix}/stats/ui"}


def _is_static_path(path: str) -> bool:
    return (
        path.startswith("/static")
        or path in {"/favicon.ico", "/favicon.png", "/apple-touch-icon.png"}
    )


def _is_api_path(path: str) -> bool:
    return path.startswith(f"{settings.api_prefix}/")


def classify_bucket(path: str, method: str, query_string: bytes = b"") -> str | None:
    """Return the rate-limit bucket for a request, or ``None`` if exempt."""
    clean = _clean_path(path)
    if _is_health_path(clean) or _is_static_path(clean) or clean == "/":
        return None
    if _is_docs_path(clean) or _is_stats_path(clean):
        return "docs"
    if clean == f"{settings.api_prefix}/indicators/composite-query" and method.upper() == "POST":
        return "composite"
    if clean == f"{settings.api_prefix}/boundaries" or clean.startswith(
        f"{settings.api_prefix}/boundaries/"
    ):
        return "boundaries"
    if clean == f"{settings.api_prefix}/earthquakes" or clean.startswith(
        f"{settings.api_prefix}/earthquakes/"
    ):
        return "earthquakes"
    if clean == f"{settings.api_prefix}/regions" and b"q=" in query_string:
        return "search"
    if _is_api_path(clean):
        return "read"
    return None


def bucket_limits(bucket: str) -> tuple[int, int]:
    """Return ``(requests_per_minute, burst)`` for a bucket."""
    return {
        "read": (settings.rate_limit_read_per_minute, settings.rate_limit_read_burst),
        "search": (settings.rate_limit_search_per_minute, settings.rate_limit_search_burst),
        "boundaries": (
            settings.rate_limit_boundaries_per_minute,
            settings.rate_limit_boundaries_burst,
        ),
        "composite": (
            settings.rate_limit_composite_per_minute,
            settings.rate_limit_composite_burst,
        ),
        "earthquakes": (
            settings.rate_limit_earthquakes_per_minute,
            settings.rate_limit_earthquakes_burst,
        ),
        "docs": (settings.rate_limit_docs_per_minute, settings.rate_limit_docs_burst),
    }[bucket]


def _parse_ip(value: str | None) -> ipaddress._BaseAddress | None:
    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if candidate.startswith("[") and "]" in candidate:
        candidate = candidate[1 : candidate.index("]")]
    elif candidate.count(":") == 1 and "." in candidate:
        candidate = candidate.rsplit(":", 1)[0]
    try:
        return ipaddress.ip_address(candidate)
    except ValueError:
        return None


def _trusted_networks() -> list[ipaddress._BaseNetwork]:
    networks = []
    for raw in settings.trusted_proxy_ips.split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            networks.append(ipaddress.ip_network(raw, strict=False))
        except ValueError:
            logger.warning("Ignoring invalid NM_TRUSTED_PROXY_IPS entry: %s", raw)
    return networks


def _is_trusted_proxy(address: ipaddress._BaseAddress | None, networks: Iterable) -> bool:
    return bool(address and any(address in network for network in networks))


def resolve_client_ip(request: Request) -> str:
    """Resolve the effective client IP, trusting proxy headers only from peers."""
    peer_raw = request.client.host if request.client else ""
    peer = _parse_ip(peer_raw)
    networks = _trusted_networks()
    if not peer or not _is_trusted_proxy(peer, networks):
        return peer_raw or "unknown"

    # Cloudflare overwrites this at the edge; Traefik forwards it unchanged.
    cloudflare_ip = _parse_ip(request.headers.get("cf-connecting-ip"))
    if cloudflare_ip is not None:
        return str(cloudflare_ip)

    forwarded = request.headers.get("x-forwarded-for", "")
    for candidate in reversed([part.strip() for part in forwarded.split(",") if part.strip()]):
        parsed = _parse_ip(candidate)
        if parsed is None or _is_trusted_proxy(parsed, networks):
            continue
        return str(parsed)

    real_ip = _parse_ip(request.headers.get("x-real-ip"))
    return str(real_ip) if real_ip is not None else (peer_raw or "unknown")


def _required_scope(path: str) -> str | None:
    clean = _clean_path(path)
    if clean == f"{settings.api_prefix}/indicators/composite-query":
        return "composite"
    if clean.startswith(f"{settings.api_prefix}/admin"):
        return "admin"
    if _is_api_path(clean):
        return "read"
    return None


def _error_response(
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"status": "error", "code": code, "message": message},
        headers=headers,
    )


def _rate_headers(decisions: list[RateLimitDecision], exceeded: bool = False) -> dict[str, str]:
    if not decisions:
        return {}
    worst = min(decisions, key=lambda decision: (decision.remaining, decision.allowed))
    retry_after = max((decision.retry_after for decision in decisions if not decision.allowed), default=0)
    headers = {
        "X-RateLimit-Limit": str(worst.limit),
        "X-RateLimit-Remaining": str(worst.remaining),
        "X-RateLimit-Reset": str(worst.reset_at),
        "X-RateLimit-Bucket": worst.bucket or "global",
    }
    if retry_after:
        headers["Retry-After"] = str(retry_after)
    if exceeded:
        headers["X-RateLimit-Exceeded"] = "true"
    return headers


class SecurityMiddleware(BaseHTTPMiddleware):
    """Apply API-key scopes and tiered per-IP/per-key rate limits."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = _clean_path(request.url.path)
        identity: ApiKeyIdentity | None = None
        raw_key = request.headers.get(API_KEY_HEADER)

        if raw_key:
            identity = resolve_api_key(raw_key)
            if identity is None:
                return _error_response(
                    401,
                    "INVALID_API_KEY",
                    "The supplied API key is not valid.",
                )
            required = _required_scope(path)
            if required and not identity.has_scope(required):
                return _error_response(
                    403,
                    "INSUFFICIENT_SCOPE",
                    f"This API key does not have the '{required}' scope.",
                )

        decisions: list[RateLimitDecision] = []
        bucket = classify_bucket(path, request.method, request.url.query.encode("utf-8"))
        if settings.rate_limit_enabled and bucket is not None:
            ip = resolve_client_ip(request)
            limit, burst = bucket_limits(bucket)
            decisions.append(
                rate_limiter.check(f"ip:{ip}:{bucket}", limit, burst, bucket=bucket)
            )
            decisions.append(
                rate_limiter.check(
                    f"ip:{ip}:global",
                    settings.rate_limit_global_per_minute,
                    settings.rate_limit_global_burst,
                    bucket="global",
                )
            )
            if identity is not None:
                decisions.append(
                    rate_limiter.check(
                        f"key:{identity.digest}:global",
                        identity.quota_per_minute,
                        max(1, min(identity.quota_per_minute, 300)),
                        bucket=f"key:{identity.name}",
                    )
                )

        headers = _rate_headers(decisions)
        denied = [decision for decision in decisions if not decision.allowed]
        if denied:
            headers = _rate_headers(decisions, exceeded=True)
            log_ip = hashlib.sha256(resolve_client_ip(request).encode("utf-8")).hexdigest()[:12]
            logger.warning(
                "rate limit exceeded bucket=%s ip_hash=%s report_only=%s request_id=%s",
                bucket,
                log_ip,
                settings.rate_limit_report_only,
                getattr(request.state, "request_id", ""),
            )
            if not settings.rate_limit_report_only:
                return _error_response(
                    429,
                    "RATE_LIMITED",
                    "Terlalu banyak permintaan dalam waktu singkat. Silakan tunggu beberapa detik lalu coba lagi.",
                    headers=headers,
                )

        response = await call_next(request)
        for key, value in headers.items():
            response.headers.setdefault(key, value)
        if identity is not None:
            response.headers.setdefault("X-API-Key-Name", identity.name)
        return response


class BodySizeLimitMiddleware:
    """Reject request bodies larger than the configured limit.

    ``Content-Length`` is checked first. For chunked bodies without a length,
    the body is buffered up to the limit and replayed to the app. The limit is
    small (16 KB), so buffering is bounded and avoids turning the rejection
    into FastAPI's generic body-parse 400.
    """

    BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method", "").upper() not in self.BODY_METHODS:
            await self.app(scope, receive, send)
            return

        limit = max(1, int(settings.max_request_body_bytes))
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        raw_length = headers.get(b"content-length")
        if raw_length:
            try:
                if int(raw_length) > limit:
                    await _payload_too_large(scope, receive, send)
                    return
            except ValueError:
                pass

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            body.extend(message.get("body", b""))
            if len(body) > limit:
                await _payload_too_large(scope, receive, send)
                return
            if not message.get("more_body", False):
                break

        replayed = False

        async def replay_receive() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return {"type": "http.disconnect"}

        await self.app(scope, replay_receive, send)


async def _payload_too_large(scope: Scope, receive: Receive, send: Send) -> None:
    response = JSONResponse(
        status_code=413,
        content={
            "status": "error",
            "code": "PAYLOAD_TOO_LARGE",
            "message": "Ukuran request melebihi batas yang diizinkan.",
        },
    )
    await response(scope, receive, send)


class SecurityHeadersMiddleware:
    """Inject browser security headers and a correlation request ID."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = _clean_path(scope.get("path", ""))
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        raw_request_id = headers.get(b"x-request-id", b"").decode("latin-1").strip()
        request_id = (
            raw_request_id
            if REQUEST_ID_PATTERN.fullmatch(raw_request_id)
            else uuid.uuid4().hex
        )
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                response_headers.setdefault("X-Request-ID", request_id)
                response_headers.setdefault("X-Content-Type-Options", "nosniff")
                response_headers.setdefault("X-Frame-Options", "DENY")
                response_headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
                response_headers.setdefault(
                    "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
                )
                response_headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
                response_headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
                response_headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")

                content_type = response_headers.get("content-type", "").lower()
                is_html = "text/html" in content_type
                if is_html and _is_docs_path(path):
                    response_headers.setdefault(
                        "Content-Security-Policy",
                        "default-src 'self' https: data: blob:; "
                        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https: blob:; "
                        "style-src 'self' 'unsafe-inline' https:; "
                        "font-src 'self' https: data:; "
                        "img-src 'self' data: https:; "
                        "connect-src 'self' https:; worker-src 'self' blob:; "
                        "frame-ancestors 'none'",
                    )
                elif is_html:
                    response_headers.setdefault(
                        "Content-Security-Policy",
                        "default-src 'self' https: data:; "
                        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com; "
                        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                        "font-src 'self' https://fonts.gstatic.com data:; "
                        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'",
                    )
                else:
                    response_headers.setdefault(
                        "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
                    )

                forwarded_proto = headers.get(b"x-forwarded-proto", b"").decode("latin-1")
                if scope.get("scheme") == "https" or forwarded_proto.lower() == "https":
                    response_headers.setdefault(
                        "Strict-Transport-Security",
                        "max-age=31536000; includeSubDomains",
                    )
            await send(message)

        await self.app(scope, receive, send_wrapper)
