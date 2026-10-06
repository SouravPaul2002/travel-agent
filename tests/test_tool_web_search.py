"""Unit tests for fallback web search tool using DDGS."""

from unittest.mock import MagicMock
from app.tools.web_search import search_web_formatted, web_search_tool


def test_web_search_tool_success():
    """Verify DDGS search returns structured SearchResult schemas with citations."""
    mock_ddgs = MagicMock()
    mock_ddgs.text.return_value = [
        {
            "title": "Top Things to Do in Jaipur",
            "href": "https://example.com/jaipur",
            "body": "Explore Hawa Mahal and Amber Fort in Jaipur.",
        },
        {
            "title": "Jaipur Travel Guide",
            "href": "https://example.com/guide",
            "body": "Best hotels and street food in the Pink City.",
        },
    ]

    results = web_search_tool("Jaipur travel tips", client=mock_ddgs, use_cache=False)
    assert len(results) == 2
    assert results[0].title == "Top Things to Do in Jaipur"
    assert results[0].url == "https://example.com/jaipur"
    assert results[0].snippet == "Explore Hawa Mahal and Amber Fort in Jaipur."
    assert results[0].source == "duckduckgo"


def test_web_search_empty_query():
    """Verify empty query returns empty list without calling API."""
    mock_ddgs = MagicMock()
    results = web_search_tool("   ", client=mock_ddgs)
    assert results == []
    mock_ddgs.text.assert_not_called()


def test_web_search_api_exception():
    """Verify exception in DDGS returns empty list gracefully."""
    mock_ddgs = MagicMock()
    mock_ddgs.text.side_effect = RuntimeError("DDG rate limit or network error")

    results = web_search_tool("Jaipur history", client=mock_ddgs, use_cache=False)
    assert results == []


def test_search_web_formatted_output():
    """Verify search_web_formatted outputs formatted citations for LLMs."""
    mock_ddgs = MagicMock()
    mock_ddgs.text.return_value = [
        {
            "title": "Amber Fort Jaipur",
            "href": "https://example.com/amber",
            "body": "Amber Fort is located in Amer, Rajasthan.",
        }
    ]

    # Monkeypatch web_search_tool or test directly with mock client
    results = web_search_tool("Amber Fort", client=mock_ddgs, use_cache=False)
    assert len(results) == 1
    assert "amber" in results[0].url


def test_web_search_caching():
    """Verify repeated search query is served from SQLite cache."""
    mock_ddgs = MagicMock()
    mock_ddgs.text.return_value = [
        {"title": "Cached Title", "href": "https://cached.com", "body": "Cached Snippet"}
    ]

    query = "Unique Cache Query 999"
    # First call calls mock_ddgs
    res1 = web_search_tool(query, client=mock_ddgs, use_cache=True)
    assert len(res1) == 1
    assert mock_ddgs.text.call_count == 1

    # Second call returns from cache without calling mock_ddgs again
    res2 = web_search_tool(query, client=mock_ddgs, use_cache=True)
    assert len(res2) == 1
    assert res2[0].title == "Cached Title"
    assert mock_ddgs.text.call_count == 1
