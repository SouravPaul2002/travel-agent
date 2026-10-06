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


def test_parse_stars_ignores_building_levels():
    """Verify that building:levels (physical floor count) is ignored and only stars tag is used."""
    from app.tools.hotels import _parse_stars

    assert _parse_stars({"building:levels": "3"}) is None
    assert _parse_stars({"building:levels": "5", "name": "5 Story Motel"}) is None
    assert _parse_stars({"stars": "4"}) == 4.0
    assert _parse_stars({"stars": "3 stars"}) == 3.0


@respx.mock
def test_hotel_tool_budget_level_filtering(sample_places):
    """Verify hotel_tool uses budget_level to filter and rank hotels appropriately."""
    mock_hotel_data = {
        "elements": [
            {
                "type": "node",
                "id": 201,
                "lat": 26.9250,  # Closest
                "lon": 75.8250,
                "tags": {"name": "Backpacker Hostel", "stars": "2"},
            },
            {
                "type": "node",
                "id": 202,
                "lat": 26.9300,  # Slightly further
                "lon": 75.8300,
                "tags": {"name": "Grand Luxury Palace", "stars": "5"},
            },
        ]
    }
    respx.post(OVERPASS_API_URL).respond(200, json=mock_hotel_data)

    with httpx.Client() as client:
        # Luxury budget should rank Grand Luxury Palace first
        luxury_hotels = hotel_tool(sample_places, budget_level=BudgetLevel.LUXURY, client=client)
        assert len(luxury_hotels) == 2
        assert luxury_hotels[0].name == "Grand Luxury Palace"
        assert luxury_hotels[0].rating == 5.0

        # Budget level should rank Backpacker Hostel first
        budget_hotels = hotel_tool(sample_places, budget_level=BudgetLevel.BUDGET, client=client)
        assert len(budget_hotels) == 2
        assert budget_hotels[0].name == "Backpacker Hostel"
        assert budget_hotels[0].rating == 2.0


def test_budget_tier_boundaries_are_mutually_exclusive():
    """Verify tier boundaries do not overlap: mid is strictly > 2.5 and < 4.0."""
    from app.tools.hotels import _matches_budget

    # 2.5 stars: matches budget, NOT mid or luxury
    assert _matches_budget(2.5, BudgetLevel.BUDGET) is True
    assert _matches_budget(2.5, BudgetLevel.MID) is False
    assert _matches_budget(2.5, BudgetLevel.LUXURY) is False

    # 3.0 stars: matches mid, NOT budget or luxury
    assert _matches_budget(3.0, BudgetLevel.BUDGET) is False
    assert _matches_budget(3.0, BudgetLevel.MID) is True
    assert _matches_budget(3.0, BudgetLevel.LUXURY) is False

    # 4.0 stars: matches luxury, NOT mid or budget
    assert _matches_budget(4.0, BudgetLevel.BUDGET) is False
    assert _matches_budget(4.0, BudgetLevel.MID) is False
    assert _matches_budget(4.0, BudgetLevel.LUXURY) is True


@respx.mock
def test_hotel_ranking_favours_close_unrated_over_far_rated(sample_places):
    """Verify an unrated hotel 300m away ranks above a rated hotel 8km away."""
    mock_hotel_data = {
        "elements": [
            {
                "type": "node",
                "id": 301,
                "lat": 26.9275,  # ~300m from centroid
                "lon": 75.8260,
                "tags": {"name": "Close Unrated Inn"},
            },
            {
                "type": "node",
                "id": 302,
                "lat": 26.9950,  # ~8km from centroid
                "lon": 75.8300,
                "tags": {"name": "Far 3-Star Hotel", "stars": "3"},
            },
        ]
    }
    respx.post(OVERPASS_API_URL).respond(200, json=mock_hotel_data)

    with httpx.Client() as client:
        ranked = hotel_tool(sample_places, budget_level=BudgetLevel.MID, client=client)
        assert len(ranked) == 2
        # The 300m unrated hotel should beat the 8km rated hotel!
        assert ranked[0].name == "Close Unrated Inn"
        assert ranked[1].name == "Far 3-Star Hotel"


