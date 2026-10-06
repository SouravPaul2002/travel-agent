"""Unit tests for hotel recommendation tool."""

import httpx
import pytest
import respx

from app.schemas.places import Place
from app.schemas.trip import BudgetLevel
from app.tools.hotels import (
    OVERPASS_API_URL,
    compute_centroid,
    haversine_distance,
    hotel_tool,
)


@pytest.fixture
def sample_places():
    return [
        Place(
            name="Hawa Mahal",
            lat=26.9239,
            lon=75.8267,
            category="sight",
            source="osm",
        ),
        Place(
            name="City Palace",
            lat=26.9258,
            lon=75.8236,
            category="palace",
            source="osm",
        ),
    ]


def test_haversine_distance():
    """Verify haversine distance gives accurate distance in km."""
    # Paris (48.8566, 2.3522) to London (51.5074, -0.1278) ~ 343-344 km
    dist = haversine_distance(48.8566, 2.3522, 51.5074, -0.1278)
    assert 340.0 <= dist <= 346.0

    # Same location distance is 0
    assert haversine_distance(26.9, 75.8, 26.9, 75.8) == 0.0


def test_compute_centroid(sample_places):
    """Verify arithmetic centroid of input places."""
    centroid = compute_centroid(sample_places)
    assert centroid is not None
    lat, lon = centroid
    expected_lat = round((26.9239 + 26.9258) / 2.0, 6)
    expected_lon = round((75.8267 + 75.8236) / 2.0, 6)
    assert lat == expected_lat
    assert lon == expected_lon

    # Empty list returns None
    assert compute_centroid([]) is None


@respx.mock
def test_hotel_tool_success_and_ranking(sample_places):
    """Verify hotels are fetched, distances computed, and sorted by proximity."""
    # Centroid is ~(26.92485, 75.82515)
    mock_hotel_data = {
        "elements": [
            {
                "type": "node",
                "id": 101,
                "lat": 26.9500,  # Further away
                "lon": 75.8300,
                "tags": {"name": "Far Resort", "stars": "4"},
            },
            {
                "type": "node",
                "id": 102,
                "lat": 26.9260,  # Very close to centroid
                "lon": 75.8260,
                "tags": {"name": "Close Heritage Hotel", "stars": "3"},
            },
        ]
    }
    respx.post(OVERPASS_API_URL).respond(200, json=mock_hotel_data)

    with httpx.Client() as client:
        hotels = hotel_tool(sample_places, budget_level=BudgetLevel.MID, limit=5, client=client)
        assert len(hotels) == 2
        # Nearest hotel should be first
        assert hotels[0].name == "Close Heritage Hotel"
        assert hotels[0].distance_km < hotels[1].distance_km
        assert hotels[0].source == "osm-overpass"
        # Confirm no prices
        assert not hasattr(hotels[0], "price")


def test_hotel_tool_empty_places_returns_empty():
    """Verify passing empty places returns an empty hotel list."""
    hotels = hotel_tool([])
    assert hotels == []


@respx.mock
def test_hotel_tool_api_failure_returns_empty(sample_places):
    """Verify network error returns empty list gracefully."""
    respx.post(OVERPASS_API_URL).respond(500, text="Overpass Timeout")

    with httpx.Client() as client:
        hotels = hotel_tool(sample_places, client=client)
        assert hotels == []
