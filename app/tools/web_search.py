"""Fallback web search tool using DDGS with SQLite caching and structured citations."""

import json
import logging
from typing import Optional

from ddgs import DDGS
from pydantic import BaseModel, Field

from app.tools._http import get_cached_response, make_cache_key, set_cached_response

logger = logging.getLogger(__name__)


class SearchResult(BaseModel):
    """Structured search snippet from fallback web search."""

    title: str = Field(..., description="Page title")
    url: str = Field(..., description="Target webpage URL")
    snippet: str = Field(..., description="Summary excerpt or snippet")
    source: str = Field(default="duckduckgo", description="Data provider citation")


def web_search_tool(
    query: str,
    max_results: int = 5,
    use_cache: bool = True,
    client: Optional[DDGS] = None,
) -> list[SearchResult]:
    """Fallback web search using DuckDuckGo. Used when structured APIs return no results.

    Returns a list of structured SearchResult objects with citations.
    """
    cleaned_query = query.strip()
    if not cleaned_query:
        return []

    cache_key = make_cache_key("DDG", "https://html.duckduckgo.com/html", params={"q": cleaned_query, "n": max_results})
    if use_cache:
        cached = get_cached_response(cache_key)
        if cached is not None:
            status_code, body_text = cached
            if status_code == 200:
                try:
                    data = json.loads(body_text)
                    return [SearchResult(**item) for item in data]
                except Exception as exc:
                    logger.warning(f"Error parsing cached search results: {exc}")

    ddgs_instance = client or DDGS()
    try:
        raw_results = ddgs_instance.text(cleaned_query, max_results=max_results)
        if not raw_results:
            logger.info(f"DuckDuckGo returned 0 results for query: '{cleaned_query}'")
            return []

        results: list[SearchResult] = []
        for r in raw_results:
            title = r.get("title") or "No Title"
            url = r.get("href") or r.get("link") or ""
            body = r.get("body") or r.get("snippet") or ""

            results.append(
                SearchResult(
                    title=title.strip(),
                    url=url.strip(),
                    snippet=body.strip(),
                    source="duckduckgo",
                )
            )

        if use_cache and results:
            json_blob = json.dumps([r.model_dump() for r in results])
            set_cached_response(cache_key, 200, json_blob, ttl_seconds=86400.0)

        return results
    except Exception as exc:
        logger.warning(f"DuckDuckGo search error for query '{cleaned_query}': {exc}")
        return []


def search_web_formatted(query: str, max_results: int = 5) -> str:
    """Format search results into a clean string with numbered citations for LLM context."""
    results = web_search_tool(query, max_results=max_results)
    if not results:
        return "No web search results found."

    formatted: list[str] = []
    for idx, item in enumerate(results, start=1):
        formatted.append(f"[{idx}] Title: {item.title}\nURL: {item.url}\nSnippet: {item.snippet}\nSource: {item.source}")
    return "\n\n---\n\n".join(formatted)
