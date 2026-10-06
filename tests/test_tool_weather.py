"""Unit tests for Open-Meteo weather and geocoding tool with mocked network calls."""

import httpx
import respx

from app.tools.weather import (
    FORECAST_API_URL,
    GEOCODING_API_URL,
    geocode_city,
    parse_weather_code,
    weather_tool,
)


@respx.mock
def test_geocode_city_success():
    """Verify city name resolves to latitude and longitude."""
    mock_payload = {
        "results": [
            {
                "id": 1269515,
                "name": "Jaipur",
                "latitude": 26.9196,
                "longitude": 75.7878,
                "country": "India",
            }
        ]
    }
    respx.get(GEOCODING_API_URL).respond(200, json=mock_payload)

    with httpx.Client() as client:
        coords = geocode_city("Jaipur", client=client)
        assert coords is not None
        lat, lon = coords
        assert round(lat, 2) == 26.92
        assert round(lon, 2) == 75.79


@respx.mock
def test_geocode_city_not_found():
    """Verify unknown city gracefully returns None."""
    respx.get(GEOCODING_API_URL).respond(200, json={"generationtime_ms": 0.1})

    with httpx.Client() as client:
        coords = geocode_city("UnknownNonExistentCity12345", client=client)
        assert coords is None


@respx.mock
def test_weather_tool_success():
    """Verify 3-day weather forecast parses into DailyWeather objects."""
    mock_payload = {
        "daily": {
            "time": ["2026-10-10", "2026-10-11", "2026-10-12"],
            "temperature_2m_max": [32.5, 31.0, 29.8],
            "temperature_2m_min": [21.0, 20.2, 19.5],
            "precipitation_probability_max": [10.0, 65.0, 0.0],
            "weather_code": [0, 61, 2],
        }
    }
    respx.get(FORECAST_API_URL).respond(200, json=mock_payload)

    with httpx.Client() as client:
        forecast = weather_tool(lat=26.92, lon=75.79, start_date="2026-10-10", days=3, client=client)
        assert len(forecast) == 3
        assert forecast[0].date == "2026-10-10"
        assert forecast[0].temp_max == 32.5
        assert forecast[0].temp_min == 21.0
        assert forecast[0].summary == "Clear sky"
        assert forecast[0].source == "open-meteo"

        assert forecast[1].summary == "Slight rain"
        assert forecast[1].precipitation_prob == 65.0


@respx.mock
def test_weather_tool_api_failure_returns_empty():
    """Verify HTTP failures return an empty list without raising."""
    respx.get(FORECAST_API_URL).respond(500, text="Internal Server Error")

    with httpx.Client() as client:
        forecast = weather_tool(lat=26.92, lon=75.79, days=3, client=client)
        assert forecast == []


@respx.mock
def test_weather_tool_malformed_json_returns_empty():
    """Verify corrupt or malformed payload returns an empty list without raising."""
    respx.get(FORECAST_API_URL).respond(200, text="not a json payload")

    with httpx.Client() as client:
        forecast = weather_tool(lat=26.92, lon=75.79, days=3, client=client)
        assert forecast == []


def test_parse_weather_code_mapping():
    """Verify WMO weather codes map to expected descriptions."""
    assert parse_weather_code(0) == "Clear sky"
    assert parse_weather_code(95) == "Thunderstorm"
    assert parse_weather_code(9999) == "Moderate conditions"
    assert parse_weather_code(None) == "Pleasant"
