"""Places and points of interest (POI) discovery tool using Geoapify with OSM Overpass fallback."""

import json
import logging
from typing import Any, Optional

import httpx

from app.config import settings
from app.schemas.places import Place
from app.tools._http import cached_request
from app.tools.weather import geocode_city

logger = logging.getLogger(__name__)

GEOAPIFY_PLACES_URL = "https://api.geoapify.com/v2/places"
OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"

# Map user interest keywords to Geoapify category strings
GEOAPIFY_CATEGORY_MAP: dict[str, str] = {
    "history": "heritage,tourism.sights",
    "historic": "heritage,tourism.sights",
    "food": "catering.restaurant,catering.cafe",
    "culinary": "catering.restaurant,catering.cafe",
    "nature": "natural,leisure.park",
    "outdoors": "natural,leisure.park",
    "art": "entertainment.culture,entertainment.museum",
    "culture": "entertainment.culture,heritage",
    "shopping": "commercial.shopping_mall,commercial.marketplace",
    "adventure": "leisure.park,tourism.attraction",
}

DEFAULT_GEOAPIFY_CATEGORIES = "tourism.sights,entertainment.culture,heritage"


def _build_geoapify_categories(interests: list[str]) -> str:
    """Translate user interests into comma-separated Geoapify categories."""
    selected_categories: list[str] = []
    for interest in interests:
        key = interest.lower().strip()
        if key in GEOAPIFY_CATEGORY_MAP:
            selected_categories.append(GEOAPIFY_CATEGORY_MAP[key])
    if not selected_categories:
        return DEFAULT_GEOAPIFY_CATEGORIES
    # Unique categories preserving order
    return ",".join(dict.fromkeys(selected_categories))


def _classify_indoor_outdoor(category_or_tags: str) -> bool:
    """Determine if a place is primarily outdoor (True) or indoor (False)."""
    text = category_or_tags.lower()
    indoor_keywords = ("museum", "gallery", "aquarium", "theatre", "theater", "palace_interior", "cinema", "mall")
    if any(k in text for k in indoor_keywords):
        return False
    return True


def _fetch_from_geoapify(
    lat: float,
    lon: float,
    interests: list[str],
    limit: int = 15,
    client: Optional[httpx.Client] = None,
) -> list[Place]:
    """Query Geoapify Places API v2."""
    if not settings.geoapify_api_key:
        return []

    categories = _build_geoapify_categories(interests)
    params = {
        "categories": categories,
        "filter": f"circle:{lon},{lat},15000",
        "bias": f"proximity:{lon},{lat}",
        "limit": limit,
        "apiKey": settings.geoapify_api_key,
    }

    raw = cached_request(
        method="GET",
        url=GEOAPIFY_PLACES_URL,
        params=params,
        ttl_seconds=86400.0,
        client=client,
    )
    if not raw:
        return []

    places: list[Place] = []
    try:
        data = json.loads(raw)
        features = data.get("features", [])
        for feat in features:
            props = feat.get("properties", {})
            name = props.get("name")
            if not name or not name.strip():
                continue
            p_lat = props.get("lat")
            p_lon = props.get("lon")
            if p_lat is None or p_lon is None:
                continue

            category_list = props.get("categories", ["tourism.sights"])
            category_str = category_list[0] if isinstance(category_list, list) and category_list else "tourism.sights"
            is_outdoor = _classify_indoor_outdoor(f"{category_str} {name}")
            place_id = props.get("place_id") or f"geoapify:{p_lat},{p_lon}"
            opening_hours = props.get("opening_hours")
            # Note: Geoapify Places v2 rank.confidence represents search match confidence,
            # not user review rating. Set rating=None to adhere to "never invent data".
            places.append(
                Place(
                    id=str(place_id),
                    name=name.strip(),
                    lat=float(p_lat),
                    lon=float(p_lon),
                    category=category_str,
                    rating=None,
                    opening_hours=str(opening_hours) if opening_hours else None,
                    is_outdoor=is_outdoor,
                    source="geoapify",
                )
            )
            if len(places) >= limit:
                break
        return places
    except Exception as exc:
        logger.warning(f"Error parsing Geoapify places response: {exc}")
        return []


def _fetch_from_overpass(
    lat: float,
    lon: float,
    limit: int = 15,
    client: Optional[httpx.Client] = None,
) -> list[Place]:
    """Query OpenStreetMap Overpass API for tourism and historic attractions."""
    # Search within 15km around city center
    overpass_query = f"""
    [out:json][timeout:25];
    (
      node["tourism"~"attraction|museum|viewpoint|gallery|theme_park"](around:15000,{lat},{lon});
      way["tourism"~"attraction|museum|viewpoint|gallery|theme_park"](around:15000,{lat},{lon});
      node["historic"~"monument|castle|memorial|ruins|archaeological_site"](around:15000,{lat},{lon});
      way["historic"~"monument|castle|memorial|ruins|archaeological_site"](around:15000,{lat},{lon});
    );
    out center tags {limit * 2};
    """

    raw = cached_request(
        method="POST",
        url=OVERPASS_API_URL,
        data={"data": overpass_query},
        ttl_seconds=86400.0,
        client=client,
    )
    if not raw:
        logger.warning("Overpass API returned no response or failed.")
        return []

    places: list[Place] = []
    seen_names: set[str] = set()

    try:
        data = json.loads(raw)
        elements = data.get("elements", [])
        for el in elements:
            tags = el.get("tags", {})
            name = tags.get("name:en") or tags.get("name")
            if not name or not name.strip():
                continue
            cleaned_name = name.strip()
            if cleaned_name.lower() in seen_names:
                continue
            seen_names.add(cleaned_name.lower())

            # Coordinates for nodes vs way centers
            p_lat = el.get("lat") or el.get("center", {}).get("lat")
            p_lon = el.get("lon") or el.get("center", {}).get("lon")
            if p_lat is None or p_lon is None:
                continue

            category = tags.get("tourism") or tags.get("historic") or "attraction"
            is_outdoor = _classify_indoor_outdoor(f"{category} {cleaned_name}")
            place_id = f"osm:{el.get('type')}/{el.get('id')}"
            opening_hours = tags.get("opening_hours")

            places.append(
                Place(
                    id=place_id,
                    name=cleaned_name,
                    lat=float(p_lat),
                    lon=float(p_lon),
                    category=category,
                    rating=None,  # OSM does not typically carry reliable ratings
                    opening_hours=opening_hours,
                    is_outdoor=is_outdoor,
                    source="osm-overpass",
                )
            )
            if len(places) >= limit:
                break
        return places
    except Exception as exc:
        logger.warning(f"Error parsing OSM Overpass response: {exc}")
        return []


def places_tool(
    city: str,
    interests: list[str],
    limit: int = 15,
    client: Optional[httpx.Client] = None,
) -> list[Place]:
    """Discover attractions and POIs for a city. Uses Geoapify if configured, falling back to OSM Overpass."""
    coords = geocode_city(city, client=client)
    if not coords:
        logger.warning(f"Could not resolve geocoding for city: {city}. Returning empty places list.")
        return []

    lat, lon = coords

    # Try Geoapify first if API key is provided
    if settings.geoapify_api_key:
        places = _fetch_from_geoapify(lat, lon, interests=interests, limit=limit, client=client)
        if places:
            return places
        logger.info("Geoapify returned 0 places or failed. Falling back to OSM Overpass.")

    # Fallback to OSM Overpass
    places = _fetch_from_overpass(lat, lon, limit=limit, client=client)
    if not places:
        logger.warning(f"No places found for city: {city} via any provider.")
        return []
    return places
