"""
Optional API-key identity and scope handling.

Keys are stored only as SHA-256 hashes in configuration. A browser key is not a
secret; it exists for attribution and higher aggregate quotas, never as a
replacement for per-IP abuse controls or admin authentication.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Iterable

from app.config import settings


API_KEY_HEADER = "X-API-Key"


@dataclass(frozen=True)
class ApiKeyIdentity:
    """Resolved API-key identity with the scopes it may exercise."""

    name: str
    scopes: frozenset[str]
    quota_per_minute: int
    digest: str

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes


def hash_api_key(raw_key: str) -> str:
    """Return the lowercase SHA-256 hex digest used for configuration."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _candidates() -> Iterable[tuple[str, str, frozenset[str], int]]:
    yield (
        "app",
        settings.app_api_key_hash.strip().lower(),
        frozenset({"read", "composite"}),
        settings.rate_limit_app_key_per_minute,
    )
    yield (
        "judge",
        settings.judge_api_key_hash.strip().lower(),
        frozenset({"read", "composite"}),
        settings.rate_limit_judge_key_per_minute,
    )
    yield (
        "admin",
        settings.admin_token_hash.strip().lower(),
        frozenset({"admin"}),
        settings.rate_limit_admin_key_per_minute,
    )


def resolve_api_key(raw_key: str | None) -> ApiKeyIdentity | None:
    """Resolve a raw header value to an identity, or ``None`` if invalid."""
    if not raw_key:
        return None

    digest = hash_api_key(raw_key)
    matched: ApiKeyIdentity | None = None
    for name, expected, scopes, quota in _candidates():
        if not expected:
            continue
        # Compare every configured candidate to avoid early-exit timing leaks.
        if hmac.compare_digest(digest, expected):
            matched = ApiKeyIdentity(
                name=name,
                scopes=scopes,
                quota_per_minute=quota,
                digest=digest,
            )
    return matched
