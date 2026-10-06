"""Hotel recommendation tool ranking accommodations near the centroid of planned attractions."""

import json
import logging
import math
from typing import Optional

import httpx

from app.schemas.hotel import Hotel
from app.schemas.places import Place
from app.schemas.trip import BudgetLevel
from app.tools._http import cached_request

logger = logging.getLogger(__name__)

OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"
EARTH_RADIUS_KM = 6371.0


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance between two GPS points in kilometers using Haversine formula."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(EARTH_RADIUS_KM * c, 2)


def compute_centroid(places: list[Place]) -> Optional[tuple[float, float]]:
    """Compute arithmetic mean latitude and longitude of a list of places."""
    if not places:
        return None
    mean_lat = sum(p.lat for p in places) / len(places)
    mean_lon = sum(p.lon for p in places) / len(places)
    return round(mean_lat, 6), round(mean_lon, 6)


def _parse_stars(tags: dict[str, str]) -> Optional[float]:
    """Extract hotel star rating if annotated in OSM tags."""
    stars_str = tags.get("stars") or tags.get("building:levels")
    if stars_str:
        try:
            val = float(stars_str.replace("star", "").strip())
            if 1.0 <= val <= 5.0:
                return val
        except ValueError:
            pass
    return None


def hotel_tool(
    places: list[Place],
    budget_level: BudgetLevel = BudgetLevel.MID,
    limit: int = 5,
    client: Optional[httpx.Client] = None,
) -> list[Hotel]:
    """Find and rank hotels closest to the geographic centroid of the planned places."""
    centroid = compute_centroid(places)
    if not centroid:
        logger.warning("hotel_tool called with empty places list; cannot compute centroid.")
        return []

    c_lat, c_lon = centroid

    # Search within 10km around centroid
    overpass_query = f"""
    [out:json][timeout:25];
    (
      node["tourism"="hotel"](around:10000,{c_lat},{c_lon});
      way["tourism"="hotel"](around:10000,{c_lat},{c_lon});
    );
    out center tags 40;
    """

    raw = cached_request(
        method="POST",
        url=OVERPASS_API_URL,
        data={"data": overpass_query},
        ttl_seconds=86400.0,
        client=client,
    )
    if not raw:
        logger.warning(f"Overpass hotel query returned no response for centroid ({c_lat}, {c_lon})")
        return []

    hotels: list[Hotel] = []
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

            h_lat = el.get("lat") or el.get("center", {}).get("lat")
            h_lon = el.get("lon") or el.get("center", {}).get("lon")
            if h_lat is None or h_lon is None:
                continue

            dist = haversine_distance(c_lat, c_lon, float(h_lat), float(h_lon))
            rating = _parse_stars(tags)
            hotel_id = f"osm:{el.get('type')}/{el.get('id')}"

            hotels.append(
                Hotel(
                    id=hotel_id,
                    name=cleaned_name,
                    lat=float(h_lat),
                    lon=float(h_lon),
                    distance_km=dist,
                    rating=rating,
                    source="osm-overpass",
                )
            )

        # Sort primarily by distance_km ascending, then rating descending
        hotels.sort(key=lambda h: (h.distance_km, -(h.rating or 0.0)))
        return hotels[:limit]
    except Exception as exc:
        logger.warning(f"Error parsing hotel data from Overpass: {exc}")
        return []
