"""Shared HTTP client with SQLite caching, exponential backoff retries, and User-Agent compliance."""

import hashlib
import json
import logging
import sqlite3
import time
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Global reusable client instance
_http_client: Optional[httpx.Client] = None


def get_http_client() -> httpx.Client:
    """Return a shared httpx.Client configured with default timeout and User-Agent."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.Client(
            timeout=httpx.Timeout(settings.request_timeout_seconds),
            headers={"User-Agent": settings.user_agent},
        )
    return _http_client


def close_http_client() -> None:
    """Close the global client if open."""
    global _http_client
    if _http_client is not None and not _http_client.is_closed:
        _http_client.close()
        _http_client = None


def init_cache_db(db_path: Optional[str] = None) -> None:
    """Ensure the SQLite cache table exists."""
    path = db_path or settings.cache_db_path
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS http_cache (
                cache_key TEXT PRIMARY KEY,
                status_code INTEGER,
                body_text TEXT,
                created_at REAL,
                ttl_seconds REAL
            )
            """
        )
        conn.commit()


def make_cache_key(method: str, url: str, params: Optional[dict[str, Any]] = None, data: Optional[dict[str, Any]] = None) -> str:
    """Generate a deterministic SHA256 key from request method, URL, and sorted parameters."""
    normalized_params = json.dumps(sorted((params or {}).items()))
    normalized_data = json.dumps(sorted((data or {}).items()))
    payload = f"{method.upper()}:{url}:{normalized_params}:{normalized_data}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_cached_response(cache_key: str, db_path: Optional[str] = None) -> Optional[tuple[int, str]]:
    """Retrieve response from cache if present and unexpired. Returns (status_code, body_text) or None."""
    path = db_path or settings.cache_db_path
    init_cache_db(path)
    now = time.time()
    try:
        with sqlite3.connect(path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT status_code, body_text, created_at, ttl_seconds FROM http_cache WHERE cache_key = ?",
                (cache_key,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            status_code, body_text, created_at, ttl_seconds = row
            if now - created_at < ttl_seconds:
                logger.debug(f"Cache HIT for key {cache_key}")
                return status_code, body_text
            # Expired: delete entry
            cursor.execute("DELETE FROM http_cache WHERE cache_key = ?", (cache_key,))
            conn.commit()
            return None
    except Exception as e:
        logger.warning(f"Error reading HTTP cache: {e}")
        return None


def set_cached_response(cache_key: str, status_code: int, body_text: str, ttl_seconds: float, db_path: Optional[str] = None) -> None:
    """Store an HTTP response in the SQLite cache."""
    path = db_path or settings.cache_db_path
    init_cache_db(path)
    now = time.time()
    try:
        with sqlite3.connect(path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO http_cache (cache_key, status_code, body_text, created_at, ttl_seconds)
                VALUES (?, ?, ?, ?, ?)
                """,
                (cache_key, status_code, body_text, now, ttl_seconds),
            )
            conn.commit()
    except Exception as e:
        logger.warning(f"Error writing to HTTP cache: {e}")


def request_with_retry(
    method: str,
    url: str,
    params: Optional[dict[str, Any]] = None,
    data: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
    max_retries: int = 3,
    backoff_factor: float = 0.5,
    client: Optional[httpx.Client] = None,
) -> httpx.Response:
    """Execute an HTTP request with exponential backoff on transport errors, 429, and 5xx."""
    active_client = client or get_http_client()
    merged_headers = {"User-Agent": settings.user_agent}
    if headers:
        merged_headers.update(headers)

    last_exception: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            response = active_client.request(
                method=method,
                url=url,
                params=params,
                data=data,
                headers=merged_headers,
            )
            # If 429 or 5xx server error, retry if attempts remain
            if response.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                retry_after = response.headers.get("Retry-After")
                sleep_time = float(retry_after) if retry_after and retry_after.isdigit() else backoff_factor * (2**attempt)
                logger.warning(
                    f"HTTP {response.status_code} on {method} {url}. Retrying in {sleep_time:.2f}s (attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(sleep_time)
                continue
            return response
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            last_exception = exc
            if attempt < max_retries:
                sleep_time = backoff_factor * (2**attempt)
                logger.warning(
                    f"Network error on {method} {url}: {exc}. Retrying in {sleep_time:.2f}s (attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(sleep_time)
            else:
                logger.error(f"Request failed after {max_retries} retries: {exc}")
                raise exc

    if last_exception:
        raise last_exception
    raise RuntimeError(f"Unexpected termination in request_with_retry for {url}")


def cached_request(
    method: str,
    url: str,
    params: Optional[dict[str, Any]] = None,
    data: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
    ttl_seconds: float = 86400.0,
    use_cache: bool = True,
    client: Optional[httpx.Client] = None,
    db_path: Optional[str] = None,
) -> Optional[str]:
    """Execute request with caching. Returns response body text or None on failure."""
    cache_key = make_cache_key(method, url, params, data)
    if use_cache:
        cached = get_cached_response(cache_key, db_path=db_path)
        if cached is not None:
            status_code, body_text = cached
            if status_code == 200:
                return body_text

    try:
        response = request_with_retry(
            method=method,
            url=url,
            params=params,
            data=data,
            headers=headers,
            client=client,
        )
        if response.status_code == 200:
            if use_cache:
                set_cached_response(cache_key, response.status_code, response.text, ttl_seconds, db_path=db_path)
            return response.text
        logger.warning(f"Request to {url} returned non-200 status {response.status_code}: {response.text[:200]}")
        return None
    except Exception as e:
        logger.warning(f"HTTP request failed for {url}: {e}")
        return None
