"""Manual smoke test script calling live APIs for each tool on Jaipur.

Run manually with:
    python scripts/smoke_tools.py
"""

import sys
from dotenv import load_dotenv

# Load local environment if present
load_dotenv()

from app.schemas.trip import BudgetLevel
from app.tools import (
    geocode_city,
    hotel_tool,
    places_tool,
    weather_tool,
    web_search_tool,
)


def run_smoke_test(city: str = "Jaipur") -> None:
    print("=" * 60)
    print(f"TRAVEL PLANNER AGENT — LIVE SMOKE TEST FOR '{city}'")
    print("=" * 60)

    # 1. Geocoding & Weather
    print("\n[1/4] Testing Geocoding & Weather (Open-Meteo)...")
    coords = geocode_city(city)
    if not coords:
        print(f"  [FAIL] Could not geocode city: {city}")
        return
    lat, lon = coords
    print(f"  [OK] Resolved coordinates: lat={lat:.4f}, lon={lon:.4f}")

    forecast = weather_tool(lat, lon, days=3)
    if forecast:
        print(f"  [OK] Fetched {len(forecast)} days of forecast:")
        for w in forecast:
            print(f"       - {w.date}: {w.temp_min}°C to {w.temp_max}°C | Rain: {w.precipitation_prob}% | {w.summary} (src: {w.source})")
    else:
        print("  [WARN] Weather forecast returned 0 items.")

    # 2. Places Discovery
    print(f"\n[2/4] Testing Places Discovery (Geoapify / Overpass) for '{city}'...")
    places = places_tool(city, interests=["history", "culture"], limit=5)
    if places:
        print(f"  [OK] Found {len(places)} attractions:")
        for idx, p in enumerate(places, start=1):
            env_type = "Outdoor" if p.is_outdoor else "Indoor"
            print(f"       {idx}. {p.name} [{p.category}] ({env_type}) — src: {p.source}")
    else:
        print("  [WARN] No places returned.")

    # 3. Hotel Recommendations
    print("\n[3/4] Testing Hotel Recommendations near attractions centroid...")
    if places:
        hotels = hotel_tool(places, budget_level=BudgetLevel.MID, limit=3)
        if hotels:
            print(f"  [OK] Found {len(hotels)} hotels ranked by proximity to centroid:")
            for idx, h in enumerate(hotels, start=1):
                stars = f"{h.rating}★" if h.rating else "unrated"
                print(f"       {idx}. {h.name} — {h.distance_km:.2f} km away [{stars}] — src: {h.source}")
        else:
            print("  [WARN] No hotels returned near centroid.")
    else:
        print("  [SKIP] Skipping hotels (no places available to compute centroid).")

    # 4. Fallback Web Search
    print("\n[4/4] Testing Fallback Web Search (DuckDuckGo)...")
    query = f"{city} local street food specialties"
    results = web_search_tool(query, max_results=2)
    if results:
        print(f"  [OK] Web search returned {len(results)} results:")
        for idx, r in enumerate(results, start=1):
            print(f"       {idx}. {r.title}")
            print(f"          URL: {r.url}")
            print(f"          Snippet: {r.snippet[:120]}...")
    else:
        print("  [WARN] Web search returned 0 items.")

    print("\n" + "=" * 60)
    print("SMOKE TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    target_city = sys.argv[1] if len(sys.argv) > 1 else "Jaipur"
    run_smoke_test(target_city)
