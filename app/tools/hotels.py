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

    Budget tiers:
    - BUDGET: <= 2.5 stars
    - MID: 2.5 to 4.0 stars
    - LUXURY: >= 4.0 stars
    Unrated accommodations (rating is None) return True so they can serve as
    fallbacks when OSM nodes lack explicit star tags.
    """
    if rating is None:
        return True
    if budget_level == BudgetLevel.BUDGET:
        return rating <= 2.5
    elif budget_level == BudgetLevel.MID:
        return 2.5 <= rating <= 4.0
    elif budget_level == BudgetLevel.LUXURY:
        return rating >= 4.0
    return True


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

        # Filter candidates according to budget tier
        budget_matched = [h for h in hotels if _matches_budget(h.rating, budget_level)]
        # If strict filtering left no candidates, fall back to all hotels
        candidates = budget_matched if budget_matched else hotels

        # Ranking criteria:
        # 1. Explicit matches for requested budget tier first (0 vs 1)
        # 2. Distance to centroid ascending
        # 3. For LUXURY/MID prefer higher rating; for BUDGET prefer lower rating
        def sort_key(h: Hotel):
            has_explicit_budget_match = 0 if (h.rating is not None and _matches_budget(h.rating, budget_level)) else 1
            rating_order = -(h.rating or 0.0) if budget_level != BudgetLevel.BUDGET else (h.rating or 99.0)
            return (has_explicit_budget_match, h.distance_km, rating_order)

        candidates.sort(key=sort_key)
        return candidates[:limit]
    except Exception as exc:
        logger.warning(f"Error parsing hotel data from Overpass: {exc}")
        return []
