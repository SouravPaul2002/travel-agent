"""Open-Meteo weather forecast and geocoding tool."""

from datetime import date, datetime, timedelta
import json
import logging
from typing import Any, Optional

import httpx

from app.schemas.trip import GeocodedLocation
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


def parse_weather_code(code: Optional[int]) -> Optional[str]:
    """Map WMO integer weather code to human-readable condition summary."""
    if code is None:
        return None
    if code in WMO_CODE_MAP:
        return WMO_CODE_MAP[code]
    return f"Unknown (code {code})"


def geocode_city(
    city: str,
    country: Optional[str] = None,
    client: Optional[httpx.Client] = None,
) -> Optional[GeocodedLocation]:
    """Resolve a city name to GeocodedLocation with coordinates, country, and admin area.

    Uses Open-Meteo Geocoding API. If country is provided, filters candidate results
    to match the specified country (case-insensitive on country or country_code).
    Supports tuple unpacking: lat, lon = geocode_city("Paris").
    """
    cleaned_city = city.strip()
    if not cleaned_city:
        return None

    params = {"name": cleaned_city, "count": 5, "language": "en", "format": "json"}
    # Cache geocoding for 7 days (coordinates and locations are static)
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

        # Filter by country if specified
        if country:
            country_clean = country.strip().lower()
            target_item = None
            for item in results:
                c_name = (item.get("country") or "").lower()
                c_code = (item.get("country_code") or "").lower()
                if country_clean in (c_name, c_code):
                    target_item = item
                    break

            if target_item is None:
                logger.warning(
                    f"City '{cleaned_city}' was found, but none of the candidate results matched the specified country '{country}'."
                )
                return None
        else:
            target_item = results[0]

        return GeocodedLocation(
            name=target_item.get("name", cleaned_city),
            lat=float(target_item["latitude"]),
            lon=float(target_item["longitude"]),
            country=target_item.get("country"),
            country_code=target_item.get("country_code"),
            admin1=target_item.get("admin1"),
            timezone=target_item.get("timezone"),
        )
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
            raw_max = max_temps[i] if i < len(max_temps) else None
            raw_min = min_temps[i] if i < len(min_temps) else None
            raw_precip = precip_probs[i] if i < len(precip_probs) else None
            raw_code = weather_codes[i] if i < len(weather_codes) else None

            # If all core forecast metrics are omitted for this date, drop the day
            if raw_max is None and raw_min is None and raw_precip is None and raw_code is None:
                logger.warning(f"Omitting forecast for {dt_str}: all weather metrics missing from Open-Meteo.")
                continue

            temp_max = float(raw_max) if raw_max is not None else None
            temp_min = float(raw_min) if raw_min is not None else None
            precip = float(raw_precip) if raw_precip is not None else None
            if precip is not None:
                precip = max(0.0, min(100.0, precip))
            code = int(raw_code) if raw_code is not None else None
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
