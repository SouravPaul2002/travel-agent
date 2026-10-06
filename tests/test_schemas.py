"""Unit tests for all Pydantic schemas."""

import pytest
from pydantic import ValidationError

from app.schemas import (
    BudgetLevel,
    DailyWeather,
    DayPlan,
    GeocodedLocation,
    Hotel,
    Itinerary,
    Place,
    TravelStateModel,
    TripRequest,
    ValidationResult,
)


def test_trip_request_valid():
    """Verify TripRequest validation, normalization, and defaults."""
    req = TripRequest(
        city=" jaipur ",
        days=3,
        budget=BudgetLevel.MID,
        interests=[" History ", "FOOD "],
    )
    assert req.city == "Jaipur"
    assert req.days == 3
    assert req.budget == BudgetLevel.MID
    assert req.interests == ["history", "food"]


def test_trip_request_invalid_days():
    """Verify TripRequest rejects out-of-range day values."""
    with pytest.raises(ValidationError):
        TripRequest(city="Jaipur", days=0)

    with pytest.raises(ValidationError):
        TripRequest(city="Jaipur", days=15)


def test_trip_request_blank_city():
    """Verify TripRequest rejects empty or whitespace-only city names."""
    with pytest.raises(ValidationError):
        TripRequest(city="   ", days=3)


def test_place_valid():
    """Verify Place model attributes and bounds."""
    place = Place(
        name="Hawa Mahal",
        lat=26.9239,
        lon=75.8267,
        category="history",
        rating=4.5,
        opening_hours="09:00 - 17:00",
        source="osm",
    )
    assert place.name == "Hawa Mahal"
    assert place.rating == 4.5
    assert place.source == "osm"
    assert place.is_outdoor is None


def test_place_invalid_coords():
    """Verify Place rejects invalid latitude/longitude."""
    with pytest.raises(ValidationError):
        Place(name="Invalid", lat=95.0, lon=75.0, source="osm")

    with pytest.raises(ValidationError):
        Place(name="Invalid", lat=26.0, lon=195.0, source="osm")


def test_hotel_valid_no_prices():
    """Verify Hotel model conforms to spec without price fields."""
    hotel = Hotel(
        name="Heritage Palace Hotel",
        lat=26.9200,
        lon=75.8200,
        distance_km=1.2,
        rating=4.2,
        source="osm",
    )
    assert hotel.name == "Heritage Palace Hotel"
    assert hotel.distance_km == 1.2
    # Ensure no prices field exists per GOAL.md non-goals
    assert not hasattr(hotel, "price")


def test_daily_weather_valid():
    """Verify DailyWeather validation and precipitation bounds."""
    weather = DailyWeather(
        date="2026-10-10",
        temp_min=20.5,
        temp_max=32.0,
        precipitation_prob=15.0,
        summary="Clear and Sunny",
    )
    assert weather.source == "open-meteo"
    assert weather.precipitation_prob == 15.0

    with pytest.raises(ValidationError):
        DailyWeather(
            date="2026-10-10",
            temp_min=20.0,
            temp_max=30.0,
            precipitation_prob=150.0,  # Invalid: > 100%
            summary="Sunny",
        )


def test_daily_weather_optional_fields():
    """Verify DailyWeather accepts None for omitted/missing metrics to prevent data invention."""
    weather = DailyWeather(
        date="2026-10-10",
        temp_min=None,
        temp_max=None,
        precipitation_prob=None,
        summary=None,
    )
    assert weather.date == "2026-10-10"
    assert weather.temp_min is None
    assert weather.temp_max is None
    assert weather.precipitation_prob is None
    assert weather.summary is None
    assert weather.source == "open-meteo"


def test_itinerary_full_assembly():
    """Verify complete Itinerary assembly with nested DayPlans and validation."""
    request = TripRequest(city="Jaipur", days=1, interests=["history"])
    hotel = Hotel(
        name="Jaipur Central Hotel",
        lat=26.9200,
        lon=75.8200,
        distance_km=0.8,
        source="osm",
    )
    place = Place(
        name="Amber Fort",
        lat=26.9855,
        lon=75.8513,
        category="history",
        source="osm",
    )
    day1 = DayPlan(
        day_number=1,
        places=[place],
        weather_summary="Sunny, 30°C",
        theme_or_notes="Historic forts exploration",
    )
    validation = ValidationResult(is_valid=True, errors=[], warnings=[])

    itinerary = Itinerary(
        request=request,
        hotel=hotel,
        days=[day1],
        sources=["osm", "open-meteo"],
        validation=validation,
    )

    assert len(itinerary.days) == 1
    assert itinerary.days[0].places[0].name == "Amber Fort"
    assert itinerary.validation.is_valid is True
    assert "osm" in itinerary.sources


def test_travel_state_model():
    """Verify TravelStateModel handles partial states and serialization."""
    state = TravelStateModel(
        trip_request=TripRequest(city="Jaipur", days=2),
        retry_count=1,
        errors=["Hotel too far from centroid"],
    )
    assert state.trip_request.city == "Jaipur"
    assert state.retry_count == 1
    assert len(state.errors) == 1


def test_geocoded_location_coords_and_dict_conversion():
    """Verify GeocodedLocation supports coords property and converts to dict without TypeError."""
    loc = GeocodedLocation(
        name="Jaipur",
        lat=26.9196,
        lon=75.7878,
        country="India",
        country_code="IN",
        admin1="Rajasthan",
    )
    # Coords property
    assert loc.coords == (26.9196, 75.7878)

    # Standard dict(model) must NOT raise TypeError
    d = dict(loc)
    assert d["name"] == "Jaipur"
    assert d["lat"] == 26.9196
    assert d["lon"] == 75.7878
    assert d["country"] == "India"

