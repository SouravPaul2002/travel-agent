# GOAL.md — Travel Planner Agent

> Read this file fully before writing any code. It is the source of truth for scope, architecture and working rules.
> If something here conflicts with a request in chat, ask before proceeding.

## 1. Goal

Build a **multi-tool travel planning agent** orchestrated with a **custom LangGraph graph** (not the prebuilt `create_react_agent`).
Given a request like *"3 days in Jaipur, mid budget, I like history and food"*, it returns a **validated, structured itinerary**: day-by-day places, a hotel near those places, weather-aware ordering, and sources for every fact.

This is a **portfolio project for AI / agentic-AI engineer roles**. That means it must be:
- **Real**: it runs from a fresh clone.
- **Measured**: it has an evaluation set with numbers.
- **Deployed**: it has a live demo.
- **Explainable**: the owner must understand every node and tool well enough to defend design choices in an interview. Keep code simple and readable. Prefer clarity over cleverness.

## 2. Non-goals (do NOT build)

- No safety / risk-assessment tool.
- No live flight or hotel **prices** or availability (no free API exists; never scrape Booking.com, Google Flights, etc.).
- No user accounts or payments.
- No commercial use (the free Open-Meteo tier is non-commercial only; mention in README).
- No invented data. If a tool returns nothing, say so instead of guessing.

## 3. Tech stack

- Python 3.11+
- LangGraph + LangChain, Gemini via `langchain-google-genai` (free tier)
- Pydantic v2 for all schemas
- FastAPI (streaming endpoint) + a thin Streamlit client
- `httpx` for API calls, SQLite for cache and LangGraph checkpointer
- `pytest` (+ mocked HTTP), Docker, GitHub Actions
- Tracing: LangSmith or Langfuse
- Pin all versions in `requirements.txt`. Check current docs before using any library API; do not rely on memory for LangGraph/LangChain syntax, since it changes often.

## 4. Free APIs (keys only in `.env`; commit `.env.example` only)

| Need | API | Notes |
|---|---|---|
| Weather + geocoding | Open-Meteo | No key; non-commercial |
| Places / attractions | Geoapify Places or OpenTripMap | Free tier; key needed |
| Hotels | OpenStreetMap Overpass (`tourism=hotel`) or Geoapify | Names, coords, ratings if present; **no prices** |
| Currency (optional) | open.er-api.com | Keyless |
| LLM | Gemini free tier | Key in `.env` |

Rules: timeouts on every call, retries with backoff, cache responses (SQLite), respect each provider's usage policy (identify the app in `User-Agent` for Overpass/Nominatim, ~1 req/s for Nominatim). Verify current free-tier limits in each provider's docs.

## 5. Architecture

```
user request
   │
   ▼
[planner/router] ── parses request into a TripRequest (city, days, budget, interests)
   │
   ├──► [places_tool]  ─┐   (parallel: independent)
   └──► [weather_tool] ─┘
            │
            ▼
      [hotel_tool]        (sequential: needs places' coordinates → centroid)
            │
            ▼
   [itinerary_writer]     (groups places by proximity/day; weather-aware ordering)
            │
            ▼
      [validator]  ── fails? → back to planner/writer (max 2 retries)
            │ passes
            ▼
   final `Itinerary` (Pydantic-validated, with sources)

[web_search] = fallback only: when a tool returns nothing or the question is out of scope.
```

- Shared, **typed graph state** (`TravelState`), not passing strings between nodes.
- The LLM decides routing/planning and writes the itinerary; **tools return structured data**; the validator is deterministic code where possible.

## 6. Folder structure

```
app/
  schemas/      # Pydantic models: TripRequest, Place, Hotel, DailyWeather, TravelState, Itinerary
  tools/        # places.py, hotels.py, weather.py, web_search.py (each: client + typed function)
  graph/        # state.py, nodes.py, build.py (graph assembly), validator.py
  api/          # FastAPI app: /plan (streaming), /health
  config.py     # settings from env
ui/             # Streamlit thin client (calls the API only)
eval/           # cases.jsonl, run_eval.py, baseline.py (single ReAct agent), results.md
tests/          # unit tests (mocked HTTP) + graph integration tests
.env.example
requirements.txt
Dockerfile
README.md
GOAL.md
```

## 7. Tool specs

Every tool: typed input and output (Pydantic), timeout, retry, cache, and a unit test with mocked HTTP.

1. **places_tool(city, interests, limit)** → `list[Place]` (name, lat, lon, category, rating?, opening_hours?, source)
2. **hotel_tool(places, budget_level)** → `list[Hotel]` ranked by distance to the centroid of the chosen places, then rating (name, lat, lon, distance_km, rating?, source). No prices.
3. **weather_tool(lat, lon, start_date, days)** → `list[DailyWeather]` (date, temp_min/max, precipitation_prob, summary)
4. **web_search_tool(query)** → fallback only (use `ddgs`); results must be cited.

## 8. Validator rules (deterministic checks)

- Number of days matches the request.
- Every place and hotel in the itinerary came from a tool result (no invented entries).
- Outdoor-heavy days are not placed on high-precipitation days when an alternative exists.
- Stops fall within opening hours when hours are known.
- Hotel is within a reasonable distance of the day's centroid.
- Every claim carries a `source`.
On failure: return specific reasons and re-plan, **max 2 retries**, then return the best itinerary with a warning list.

## 9. Evaluation (a core deliverable)

- `eval/cases.jsonl`: 20–30 trip requests with checkable constraints.
- Compare **baseline** (single prebuilt ReAct agent with the same tools) vs **orchestrated graph**.
- Metrics: constraint satisfaction rate, tool-selection correctness, groundedness (no invented places), latency (median/p95), tokens/cost per request.
- Output a results table to `eval/results.md`. Never write resume numbers before this runs.
- Add tracing and use traces to find failures.

## 10. API

- `POST /plan` → streams progress events, ends with the final `Itinerary` JSON.
- `GET /health`.
- Session memory via LangGraph checkpointer (SQLite) keyed by `thread_id`.

## 11. Milestones (build ONE at a time; stop and wait for review after each)

1. **Repo + schemas**: structure, `requirements.txt` (pinned, includes `langgraph`, `ddgs`), `.env.example`, all Pydantic schemas. *Done when:* a fresh clone installs and imports cleanly.
2. **Tools**: places, weather, hotels, web search, each with tests. *Done when:* each works alone and returns valid schema objects.
3. **Graph**: planner → (places ∥ weather) → hotels → writer. *Done when:* one request yields a valid `Itinerary`.
4. **Validator + retry loop**. *Done when:* a bad plan is caught and fixed.
5. **Evaluation + baseline**. *Done when:* `eval/results.md` has a comparison table.
6. **Tracing**.
7. **FastAPI + streaming + memory**; Streamlit thin client.
8. **Tests, CI, Docker**.
9. **Deploy + README** (architecture diagram, setup, demo GIF, eval results, limits/non-commercial note).
10. *(Optional)* Budget estimator, route/travel-time tool.

## 12. Working rules for the AI coding assistant

- Work on **one milestone at a time**. After finishing, summarize what changed and **stop**; wait for approval.
- Before each milestone, state a short plan (files to create or change).
- **Do not delete or overwrite files outside the current milestone's scope.** Never delete the git history. Never touch `.env`.
- **Never hard-code or print secrets.** Read keys from environment variables.
- Check current official docs for LangGraph/LangChain/FastAPI/API providers before using them; do not guess APIs.
- Keep code small, typed, and commented where the *why* is not obvious. Explain non-trivial design choices briefly so the owner can learn them.
- Every tool and node gets a test. Mock all network calls in tests.
- Make small, logical commits with clear messages (one per step), on a feature branch.
- If requirements are ambiguous or an API behaves differently than expected, **ask instead of assuming**.
- Never fabricate results, metrics or sources, in code, docs or README.
