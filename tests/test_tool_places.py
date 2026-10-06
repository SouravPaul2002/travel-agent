"""Unit tests for places discovery tool (Geoapify and OSM Overpass)."""

import httpx
import pytest
import respx

from app.config import settings
from app.tools.places import GEOAPIFY_PLACES_URL, OVERPASS_API_URL, places_tool
from app.tools.weather import GEOCODING_API_URL


@pytest.fixture(autouse=True)
def mock_geocoding():
    """Ensure city geocoding succeeds in tests."""
    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.get(GEOCODING_API_URL).respond(
            200,
            json={"results": [{"latitude": 26.9196, "longitude": 75.7878, "name": "Jaipur"}]},
        )
        yield respx_mock


@respx.mock
def test_places_tool_geoapify_success(monkeypatch):
    """Verify Geoapify queries and parsing when API key is present."""
    monkeypatch.setattr(settings, "geoapify_api_key", "mock_key_123")

    mock_geoapify_data = {
        "features": [
            {
                "properties": {
                    "place_id": "51a8f6d782",
                    "name": "Hawa Mahal",
                    "lat": 26.9239,
                    "lon": 75.8267,
                    "categories": ["tourism.sights", "heritage"],
                    "opening_hours": "09:00-17:00",
                }
            },
            {
                "properties": {
                    "place_id": "89c2e4f",
                    "name": "Albert Hall Museum",
                    "lat": 26.9116,
                    "lon": 75.8195,
                    "categories": ["entertainment.museum"],
                }
            },
        ]
    }
    respx.get(GEOAPIFY_PLACES_URL).respond(200, json=mock_geoapify_data)

    with httpx.Client() as client:
        places = places_tool("Jaipur", interests=["history"], limit=5, client=client)
        assert len(places) == 2
        p1, p2 = places
        assert p1.name == "Hawa Mahal"
        assert p1.source == "geoapify"
        assert p1.is_outdoor is True  # sight

        assert p2.name == "Albert Hall Museum"
        assert p2.is_outdoor is False  # museum flagged indoor


@respx.mock
def test_places_tool_fallback_to_overpass(monkeypatch):
    """Verify OSM Overpass fallback when Geoapify API key is absent."""
    monkeypatch.setattr(settings, "geoapify_api_key", None)

    mock_overpass_data = {
        "elements": [
            {
                "type": "way",
                "id": 123456,
                "center": {"lat": 26.9855, "lon": 75.8513},
                "tags": {
                    "name": "Amber Fort",
                    "tourism": "attraction",
                    "historic": "fort",
                },
            },
            {
                "type": "node",
                "id": 789012,
                "lat": 26.9242,
                "lon": 75.8242,
                "tags": {
                    "name:en": "Jantar Mantar",
                    "tourism": "attraction",
                },
            },
        ]
    }
    respx.post(OVERPASS_API_URL).respond(200, json=mock_overpass_data)

    with httpx.Client() as client:
        places = places_tool("Jaipur", interests=["history"], limit=5, client=client)
        assert len(places) == 2
        assert places[0].name == "Amber Fort"
        assert places[0].source == "osm-overpass"
        assert places[0].id == "osm:way/123456"

        assert places[1].name == "Jantar Mantar"
        assert places[1].source == "osm-overpass"


@respx.mock
def test_places_tool_all_providers_fail(monkeypatch):
    """Verify tool returns empty list if Overpass fails."""
    monkeypatch.setattr(settings, "geoapify_api_key", None)
    respx.post(OVERPASS_API_URL).respond(500, text="Overpass Busy")

    with httpx.Client() as client:
        places = places_tool("Jaipur", interests=["history"], limit=5, client=client)
        assert places == []
