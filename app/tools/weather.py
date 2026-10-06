"""Open-Meteo weather forecast and geocoding tool."""

from datetime import date, datetime, timedelta
import json
import logging
from typing import Any, Optional

import httpx

from app.schemas.weather import DailyWeather
from app.tools._http import cached_request

logger = logging.getLogger(__name__)

GEOCODING_API_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_API_URL = "https://api.open-meteo.com/v1/forecast"

# WMO Weather interpretation codes
WMO_CODE_MAP: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def parse_weather_code(code: Optional[int]) -> str:
    """Map WMO integer weather code to human-readable condition summary."""
    if code is None:
        return "Pleasant"
    return WMO_CODE_MAP.get(code, "Moderate conditions")


def geocode_city(city: str, client: Optional[httpx.Client] = None) -> Optional[tuple[float, float]]:
    """Resolve a city name to (latitude, longitude) using Open-Meteo Geocoding API."""
    cleaned_city = city.strip()
    if not cleaned_city:
        return None

    params = {"name": cleaned_city, "count": 1, "language": "en", "format": "json"}
    # Cache geocoding for 7 days (coordinates are static)
    raw_response = cached_request(
        method="GET",
        url=GEOCODING_API_URL,
        params=params,
        ttl_seconds=604800.0,
        client=client,
    )
    if not raw_response:
        logger.warning(f"Geocoding request failed for city: {city}")
        return None

    try:
        data = json.loads(raw_response)
        results = data.get("results")
        if not results or not isinstance(results, list):
            logger.warning(f"No geocoding results found for city: {city}")
            return None
        first = results[0]
        lat = float(first["latitude"])
        lon = float(first["longitude"])
        return lat, lon
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        logger.warning(f"Failed to parse geocoding response for {city}: {exc}")
        return None


def weather_tool(
    lat: float,
    lon: float,
    start_date: Optional[str] = None,
    days: int = 3,
    client: Optional[httpx.Client] = None,
) -> list[DailyWeather]:
    """Fetch daily weather forecast from Open-Meteo API. Returns a list of DailyWeather schemas."""
    if days < 1:
        days = 1
    # Cap days at 14 per schema rules
    days = min(days, 14)

    # Determine date window
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            logger.warning(f"Invalid start_date '{start_date}'. Defaulting to today.")
            start_dt = date.today()
    else:
        start_dt = date.today()

    end_dt = start_dt + timedelta(days=days - 1)

    params: dict[str, Any] = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
        "timezone": "auto",
        "start_date": start_dt.isoformat(),
        "end_date": end_dt.isoformat(),
    }

    # Weather cache TTL: 3600 seconds (1 hour)
    raw_response = cached_request(
        method="GET",
        url=FORECAST_API_URL,
        params=params,
        ttl_seconds=3600.0,
        client=client,
    )
    if not raw_response:
        logger.warning(f"Weather forecast request failed for coords ({lat}, {lon})")
        return []

    try:
        data = json.loads(raw_response)
        daily = data.get("daily")
        if not daily:
            logger.warning("Weather API returned no 'daily' block in response.")
            return []

        dates = daily.get("time", [])
        max_temps = daily.get("temperature_2m_max", [])
        min_temps = daily.get("temperature_2m_min", [])
        precip_probs = daily.get("precipitation_probability_max", [])
        weather_codes = daily.get("weather_code", [])

        forecasts: list[DailyWeather] = []
        for i, dt_str in enumerate(dates):
            if i >= days:
                break
            temp_max = float(max_temps[i]) if i < len(max_temps) and max_temps[i] is not None else 25.0
            temp_min = float(min_temps[i]) if i < len(min_temps) and min_temps[i] is not None else 18.0
            precip = float(precip_probs[i]) if i < len(precip_probs) and precip_probs[i] is not None else 0.0
            # Ensure precip is bounded [0, 100]
            precip = max(0.0, min(100.0, precip))
            code = int(weather_codes[i]) if i < len(weather_codes) and weather_codes[i] is not None else None
            summary = parse_weather_code(code)

            forecasts.append(
                DailyWeather(
                    date=dt_str,
                    temp_min=temp_min,
                    temp_max=temp_max,
                    precipitation_prob=precip,
                    summary=summary,
                    source="open-meteo",
                )
            )
        return forecasts
    except Exception as exc:
        logger.warning(f"Error parsing Open-Meteo weather data: {exc}")
        return []
