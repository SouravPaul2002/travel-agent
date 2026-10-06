"""Unit tests for the shared HTTP client and SQLite cache helper."""

import time
import httpx
import pytest
import respx

from app.tools._http import (
    cached_request,
    get_cached_response,
    init_cache_db,
    make_cache_key,
    request_with_retry,
    set_cached_response,
)


@pytest.fixture
def temp_cache_db(tmp_path):
    """Provide a temporary SQLite database path for isolated cache testing."""
    db_file = str(tmp_path / "test_cache.db")
    init_cache_db(db_file)
    return db_file


def test_make_cache_key_deterministic():
    """Verify cache keys are identical regardless of parameter dict ordering."""
    k1 = make_cache_key("GET", "https://api.example.com/test", params={"b": 2, "a": 1})
    k2 = make_cache_key("GET", "https://api.example.com/test", params={"a": 1, "b": 2})
    assert k1 == k2


def test_cache_set_and_get(temp_cache_db):
    """Verify storing and retrieving items in SQLite cache."""
    key = "test_key_123"
    set_cached_response(key, 200, '{"result": "ok"}', ttl_seconds=3600.0, db_path=temp_cache_db)
    cached = get_cached_response(key, db_path=temp_cache_db)
    assert cached is not None
    status, body = cached
    assert status == 200
    assert body == '{"result": "ok"}'


def test_cache_ttl_expiration(temp_cache_db):
    """Verify that expired cache entries return None."""
    key = "expiring_key"
    # Store with negative TTL so it is immediately expired
    set_cached_response(key, 200, "data", ttl_seconds=-1.0, db_path=temp_cache_db)
    cached = get_cached_response(key, db_path=temp_cache_db)
    assert cached is None


@respx.mock
def test_cached_request_hits_cache(temp_cache_db):
    """Verify second request retrieves data from SQLite without hitting network."""
    url = "https://api.test.com/data"
    route = respx.get(url).respond(200, text='{"count": 42}')

    with httpx.Client() as client:
        # First call: hits network and stores in cache
        res1 = cached_request("GET", url, client=client, db_path=temp_cache_db)
        assert res1 == '{"count": 42}'
        assert route.call_count == 1

        # Second call: served from cache, network route is NOT called again
        res2 = cached_request("GET", url, client=client, db_path=temp_cache_db)
        assert res2 == '{"count": 42}'
        assert route.call_count == 1


@respx.mock
def test_request_retry_on_500():
    """Verify that 500 errors trigger retries with exponential backoff."""
    url = "https://api.test.com/flaky"
    # First attempt fails with 500, second succeeds with 200
    route = respx.get(url)
    route.side_effect = [
        httpx.Response(500, text="Internal Error"),
        httpx.Response(200, text="Recovered"),
    ]

    with httpx.Client() as client:
        resp = request_with_retry("GET", url, max_retries=2, backoff_factor=0.01, client=client)
        assert resp.status_code == 200
        assert resp.text == "Recovered"
        assert route.call_count == 2


@respx.mock
def test_request_retry_on_429():
    """Verify that 429 rate limit triggers retry."""
    url = "https://api.test.com/limited"
    route = respx.get(url)
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "0.01"}, text="Too Many Requests"),
        httpx.Response(200, text="OK"),
    ]

    with httpx.Client() as client:
        resp = request_with_retry("GET", url, max_retries=2, backoff_factor=0.01, client=client)
        assert resp.status_code == 200
        assert resp.text == "OK"


@respx.mock
def test_request_failure_after_max_retries():
    """Verify failed request returns non-200 or raises when retries are exhausted."""
    url = "https://api.test.com/down"
    respx.get(url).respond(503, text="Service Unavailable")

    with httpx.Client() as client:
        resp = request_with_retry("GET", url, max_retries=1, backoff_factor=0.01, client=client)
        assert resp.status_code == 503
