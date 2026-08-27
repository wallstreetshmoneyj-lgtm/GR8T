"""Shared HTTP client: SEC identity, rate limiting, retries, and the raw
response cache (SPEC 6, 16)."""
from __future__ import annotations

import json
import time

import httpx
import pytest

from pipelines import http_client


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(http_client.settings, "cache_dir", tmp_path, raising=False)
    yield tmp_path


@pytest.fixture(autouse=True)
def reset_cache_reuse():
    http_client.set_cache_reuse(None)
    yield
    http_client.set_cache_reuse(None)


class FakeClient:
    """Records requests and replays queued responses."""

    def __init__(self, responses: list) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, headers=None, params=None):
        self.calls.append((url, headers or {}))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        status, body = item
        request = httpx.Request("GET", url)
        return httpx.Response(status, content=body, request=request)


@pytest.fixture
def fake(monkeypatch):
    def install(responses):
        client = FakeClient(responses)
        monkeypatch.setattr(http_client, "_get_client", lambda: client)
        # Keep the rate limiter from actually sleeping through tests.
        for provider in http_client.PROVIDERS.values():
            monkeypatch.setattr(provider.limiter, "min_interval", 0)
        monkeypatch.setattr(time, "sleep", lambda _s: None)
        return client
    return install


class TestSecIdentity:
    def test_sec_requests_send_the_configured_user_agent(self, fake, cache_dir):
        client = fake([(200, b"{}")])
        http_client.get("https://data.sec.gov/x.json", "sec")
        assert client.calls[0][1]["User-Agent"] == http_client.settings.sec_user_agent

    def test_missing_user_agent_fails_loudly(self, fake, cache_dir, monkeypatch):
        fake([(200, b"{}")])
        monkeypatch.setattr(http_client.settings, "sec_user_agent", "", raising=False)
        with pytest.raises(RuntimeError, match="SEC_USER_AGENT"):
            http_client.get("https://data.sec.gov/x.json", "sec")


class TestRetries:
    def test_429_is_retried_then_succeeds(self, fake, cache_dir):
        client = fake([(429, b""), (200, b'{"ok":true}')])
        assert http_client.get("https://data.sec.gov/x.json", "sec") == b'{"ok":true}'
        assert len(client.calls) == 2

    def test_500_is_retried(self, fake, cache_dir):
        client = fake([(503, b""), (500, b""), (200, b"done")])
        assert http_client.get("https://data.sec.gov/x.json", "sec") == b"done"
        assert len(client.calls) == 3

    def test_404_is_not_retried(self, fake, cache_dir):
        client = fake([(404, b"")])
        with pytest.raises(httpx.HTTPStatusError):
            http_client.get("https://data.sec.gov/missing.json", "sec")
        assert len(client.calls) == 1

    def test_transport_errors_are_retried(self, fake, cache_dir):
        client = fake([httpx.ConnectError("boom"), (200, b"ok")])
        assert http_client.get("https://data.sec.gov/x.json", "sec") == b"ok"
        assert len(client.calls) == 2

    def test_retries_are_bounded(self, fake, cache_dir):
        client = fake([(503, b"")] * (http_client.MAX_RETRIES + 1))
        with pytest.raises(httpx.HTTPStatusError):
            http_client.get("https://data.sec.gov/x.json", "sec")
        assert len(client.calls) == http_client.MAX_RETRIES + 1


class TestRawResponseCache:
    def test_body_and_metadata_are_written_before_parsing(self, fake, cache_dir):
        fake([(200, b'{"hello":"world"}')])
        http_client.get("https://data.sec.gov/x.json", "sec", cache_key="x.json")

        body = cache_dir / "sec" / "x.json"
        meta = cache_dir / "sec" / "x.json.meta.json"
        assert body.read_bytes() == b'{"hello":"world"}'
        recorded = json.loads(meta.read_text())
        assert recorded["url"] == "https://data.sec.gov/x.json"
        assert recorded["status"] == 200
        assert recorded["fetched_at"]

    def test_cache_is_not_used_unless_reuse_is_enabled(self, fake, cache_dir):
        client = fake([(200, b"first"), (200, b"second")])
        http_client.get("https://data.sec.gov/x.json", "sec", cache_key="x.json")
        # Scheduled jobs must fetch fresh data, cache present or not.
        assert http_client.get("https://data.sec.gov/x.json", "sec", cache_key="x.json") == b"second"
        assert len(client.calls) == 2

    def test_reuse_serves_from_cache_without_a_request(self, fake, cache_dir):
        client = fake([(200, b"first")])
        http_client.get("https://data.sec.gov/x.json", "sec", cache_key="x.json")
        http_client.set_cache_reuse(3600)
        assert http_client.get("https://data.sec.gov/x.json", "sec", cache_key="x.json") == b"first"
        assert len(client.calls) == 1  # no second request

    def test_stale_cache_is_refetched(self, fake, cache_dir):
        client = fake([(200, b"first"), (200, b"second")])
        http_client.get("https://data.sec.gov/x.json", "sec", cache_key="x.json")
        http_client.set_cache_reuse(0)  # everything is immediately stale
        assert http_client.get("https://data.sec.gov/x.json", "sec", cache_key="x.json") == b"second"
        assert len(client.calls) == 2

    def test_immutable_content_is_fetched_exactly_once(self, fake, cache_dir):
        """Old EDGAR history pages never change; re-downloading them nightly
        is what the per-call max age exists to prevent."""
        client = fake([(200, b"history")])
        for _ in range(5):
            got = http_client.get("https://data.sec.gov/old.json", "sec",
                                  cache_key="old.json", cache_max_age=float("inf"))
            assert got == b"history"
        assert len(client.calls) == 1

    def test_corrupt_cache_metadata_falls_back_to_fetching(self, fake, cache_dir):
        client = fake([(200, b"first"), (200, b"second")])
        http_client.get("https://data.sec.gov/x.json", "sec", cache_key="x.json")
        (cache_dir / "sec" / "x.json.meta.json").write_text("not json{")
        http_client.set_cache_reuse(3600)
        assert http_client.get("https://data.sec.gov/x.json", "sec", cache_key="x.json") == b"second"
        assert len(client.calls) == 2


class TestRateLimiter:
    def test_all_sec_hosts_share_one_limiter(self):
        # data.sec.gov and www.sec.gov count against the same SEC budget.
        assert http_client.PROVIDERS["sec"].limiter is http_client.PROVIDERS["sec"].limiter

    def test_sec_interval_stays_under_five_per_second(self):
        assert http_client.PROVIDERS["sec"].limiter.min_interval >= 0.2

    def test_limiter_enforces_a_minimum_gap(self):
        limiter = http_client.RateLimiter(min_interval=0.05)
        start = time.monotonic()
        for _ in range(3):
            limiter.wait()
        assert time.monotonic() - start >= 0.1  # two gaps of 0.05s
