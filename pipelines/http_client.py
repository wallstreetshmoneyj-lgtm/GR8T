"""Shared outbound HTTP client (SPEC Section 6 rules).

- One place for per-provider rate limiting, retries with exponential backoff
  on 429/5xx, and a hard timeout.
- Every raw response body is cached to data/cache/<provider>/ with a
  .meta.json sidecar (url, fetched_at, status) BEFORE parsing, so a parser
  bug never forces a re-fetch. Latest response per cache key is kept
  (overwritten on refresh); the fetched_at timestamp lives in the sidecar.
- SEC calls require a real User-Agent from SEC_USER_AGENT and fail loudly
  without one (SEC fair-access policy).
"""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from core.config import settings

log = logging.getLogger(__name__)

TIMEOUT_SECONDS = 30.0
MAX_RETRIES = 4
BACKOFF_SECONDS = [2, 4, 8, 16]
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class RateLimiter:
    """Simple thread-safe minimum-interval limiter.

    A token bucket would allow bursts; a fixed floor between requests is
    simpler and strictly conservative, which is what SEC etiquette wants.
    """

    def __init__(self, min_interval: float) -> None:
        self.min_interval = min_interval
        self._lock = threading.Lock()
        self._last_request = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            sleep_for = self._last_request + self.min_interval - now
            if sleep_for > 0:
                time.sleep(sleep_for)
            self._last_request = time.monotonic()


@dataclass(frozen=True)
class Provider:
    name: str
    limiter: RateLimiter


# SEC allows 10 req/sec but the spec budgets <= 5/sec for batch work; one
# shared limiter covers ALL SEC hosts (data.sec.gov + www.sec.gov).
PROVIDERS: dict[str, Provider] = {
    "sec": Provider("sec", RateLimiter(min_interval=0.21)),
    # Finnhub free tier is 60/min; budget 30/min sustained (Phase 2).
    "finnhub": Provider("finnhub", RateLimiter(min_interval=2.0)),
    "fred": Provider("fred", RateLimiter(min_interval=1.0)),
    "coingecko": Provider("coingecko", RateLimiter(min_interval=2.0)),
    # One-time seed fetches (Wikipedia constituents table).
    "misc": Provider("misc", RateLimiter(min_interval=1.0)),
}

_client: httpx.Client | None = None
_client_lock = threading.Lock()

# When set, a cached response younger than this many seconds is used instead
# of making a request. Off by default (scheduled jobs must fetch fresh data);
# turned on by `--from-cache` so the owner can re-parse everything after a
# parser fix without hitting SEC again — the reason SPEC 6 caches raw bodies.
_cache_reuse_max_age: float | None = None


def set_cache_reuse(max_age_seconds: float | None) -> None:
    global _cache_reuse_max_age
    _cache_reuse_max_age = max_age_seconds


def _get_client() -> httpx.Client:
    global _client
    with _client_lock:
        if _client is None:
            _client = httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=True)
        return _client


def _headers_for(provider: str) -> dict[str, str]:
    if provider == "sec":
        if not settings.sec_user_agent:
            raise RuntimeError(
                "SEC_USER_AGENT is not set. SEC fair-access policy requires a real "
                "contact in the User-Agent header. Copy .env.example to .env and fill it in."
            )
        return {"User-Agent": settings.sec_user_agent, "Accept-Encoding": "gzip, deflate"}
    return {"User-Agent": "company-research-terminal/0.1 (personal research tool)"}


def _cache_paths(provider: str, cache_key: str) -> tuple[Path, Path]:
    cache_dir = settings.cache_dir / provider
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / cache_key, cache_dir / f"{cache_key}.meta.json"


def get(
    url: str,
    provider: str,
    cache_key: str | None = None,
    params: dict[str, str] | None = None,
    cache_max_age: float | None = None,
) -> bytes:
    """GET with rate limiting, retries, and raw-response caching.

    cache_max_age: serve from cache when the cached copy is younger than this
    many seconds. Pass `float("inf")` for content that is immutable once
    published (old EDGAR history files), so it is fetched exactly once ever.
    Defaults to the global `--from-cache` setting.

    Returns the response body bytes. Raises httpx.HTTPStatusError after
    retries are exhausted (callers wrap per-item so one bad company never
    kills a batch job).
    """
    if cache_key:
        max_age = cache_max_age if cache_max_age is not None else _cache_reuse_max_age
        cached = _read_fresh_cache(provider, cache_key, max_age)
        if cached is not None:
            return cached

    prov = PROVIDERS[provider]
    headers = _headers_for(provider)
    client = _get_client()

    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        prov.limiter.wait()
        try:
            resp = client.get(url, headers=headers, params=params)
            if resp.status_code in RETRYABLE_STATUS:
                raise httpx.HTTPStatusError(
                    f"retryable status {resp.status_code}", request=resp.request, response=resp
                )
            resp.raise_for_status()
            body = resp.content
            if cache_key:
                _write_cache(provider, cache_key, url, resp.status_code, body)
            return body
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            # Non-retryable HTTP errors (404 etc.) fail immediately.
            if isinstance(exc, httpx.HTTPStatusError) and status not in RETRYABLE_STATUS:
                raise
            last_exc = exc
            if attempt < MAX_RETRIES:
                delay = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]
                log.warning("GET %s failed (%s), retry in %ss", url, exc, delay)
                time.sleep(delay)
    raise last_exc  # type: ignore[misc]


def _read_fresh_cache(provider: str, cache_key: str, max_age: float | None) -> bytes | None:
    """Cached body if reuse is enabled and the entry is young enough."""
    if max_age is None:
        return None
    body_path, meta_path = _cache_paths(provider, cache_key)
    if not body_path.exists() or not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text())
        fetched_at = datetime.fromisoformat(meta["fetched_at"])
    except (json.JSONDecodeError, KeyError, ValueError):
        return None
    age = (datetime.now(UTC) - fetched_at).total_seconds()
    if age > max_age:
        return None
    log.info("cache hit %s/%s (age %.0fs)", provider, cache_key, age)
    return body_path.read_bytes()


def _write_cache(provider: str, cache_key: str, url: str, status: int, body: bytes) -> None:
    body_path, meta_path = _cache_paths(provider, cache_key)
    body_path.write_bytes(body)
    meta_path.write_text(
        json.dumps(
            {"url": url, "status": status, "fetched_at": datetime.now(UTC).isoformat()},
            indent=2,
        )
    )


def get_json(
    url: str,
    provider: str,
    cache_key: str | None = None,
    params: dict[str, str] | None = None,
    cache_max_age: float | None = None,
) -> dict:
    return json.loads(get(url, provider, cache_key=cache_key, params=params,
                          cache_max_age=cache_max_age))
