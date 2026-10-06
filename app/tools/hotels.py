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
    """Extract hotel star rating if annotated in OSM tags.

    Only uses the 'stars' tag. Never uses 'building:levels' (which indicates building
    height/floors, not star quality).
    """
    stars_str = tags.get("stars")
    if stars_str:
        try:
            val = float(stars_str.lower().replace("stars", "").replace("star", "").strip())
            if 1.0 <= val <= 5.0:
                return val
        except ValueError:
            pass
    return None


def _matches_budget(rating: Optional[float], budget_level: BudgetLevel) -> bool:
    """Determine if a star rating aligns with the target budget tier.

    Budget tiers (mutually exclusive boundaries):
    - BUDGET: <= 2.5 stars
    - MID: > 2.5 and < 4.0 stars
    - LUXURY: >= 4.0 stars
    Unrated accommodations (rating is None) return True so they can serve as
    fallbacks when OSM nodes lack explicit star tags.
    """
    if rating is None:
        return True
    if budget_level == BudgetLevel.BUDGET:
        return rating <= 2.5
    elif budget_level == BudgetLevel.MID:
        return 2.5 < rating < 4.0
    elif budget_level == BudgetLevel.LUXURY:
        return rating >= 4.0
    return True


def _compute_hotel_score(hotel: Hotel, budget_level: BudgetLevel) -> float:
    """Rank by a combined score: distance first, with a small bonus for a budget match.

    Lower score is better.
    - Base score: physical distance to centroid in km.
    - Matching budget tier: -1.5 km bonus (with small boost for higher rating in tier).
    - Unrated: 0.0 km adjustment (evaluated purely on distance).
    - Mismatched budget tier: +4.0 km penalty.
    """
    score = hotel.distance_km
    if hotel.rating is None:
        return score

    if _matches_budget(hotel.rating, budget_level):
        score -= 1.5
        if budget_level in (BudgetLevel.MID, BudgetLevel.LUXURY):
            score -= (hotel.rating - 2.5) * 0.2
    else:
        score += 4.0
    return score


def _fetch_overpass_hotels_for_radius(
    c_lat: float,
    c_lon: float,
    radius_meters: int,
    client: Optional[httpx.Client] = None,
) -> list[Hotel]:
    """Query Overpass API for hotels within a specific radius around centroid."""
    overpass_query = f"""
    [out:json][timeout:25];
    (
      node["tourism"="hotel"](around:{radius_meters},{c_lat},{c_lon});
      way["tourism"="hotel"](around:{radius_meters},{c_lat},{c_lon});
    );
    out center tags 50;
    """
    raw = cached_request(
        method="POST",
        url=OVERPASS_API_URL,
        data={"data": overpass_query},
        ttl_seconds=86400.0,
        client=client,
    )
    if not raw:
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
        return hotels
    except Exception as exc:
        logger.warning(f"Error parsing hotel data from Overpass: {exc}")
        return []


def hotel_tool(
    places: list[Place],
    budget_level: BudgetLevel = BudgetLevel.MID,
    limit: int = 5,
    client: Optional[httpx.Client] = None,
) -> list[Hotel]:
    """Find and rank hotels closest to the geographic centroid of the planned places.

    Searches a tight radius first (3 km), widening to 8 km if too few hotels are found.
    Ranks using a combined score (distance first, with a bonus for matching budget tier).
    """
    centroid = compute_centroid(places)
    if not centroid:
        logger.warning("hotel_tool called with empty places list; cannot compute centroid.")
        return []

    c_lat, c_lon = centroid

    # Progressive radius expansion: search tight 3 km radius first, widen if too few results
    hotels = _fetch_overpass_hotels_for_radius(c_lat, c_lon, radius_meters=3000, client=client)
    if len(hotels) < limit:
        wider_hotels = _fetch_overpass_hotels_for_radius(c_lat, c_lon, radius_meters=8000, client=client)
        existing_names = {h.name.lower() for h in hotels}
        for h in wider_hotels:
            if h.name.lower() not in existing_names:
                hotels.append(h)
                existing_names.add(h.name.lower())

    if not hotels:
        return []

    # Combined score ranking: distance first, adjusted by budget alignment bonus/penalty
    hotels.sort(key=lambda h: (_compute_hotel_score(h, budget_level), h.distance_km))
    return hotels[:limit]
