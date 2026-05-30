"""Tools for the Travel Agent.

- get_weather   : forecast for any city via Open-Meteo (FREE, no key).
- web_search    : attractions / food / tips via Tavily (TAVILY_API_KEY).
- search_flights: flights via SerpApi Google Flights engine (SERPAPI_API_KEY).
- search_hotels : hotels via SerpApi Google Hotels engine  (SERPAPI_API_KEY).

Every parameter carries a description with an EXAMPLE (via `Annotated[..., Field(...)]`) so the model
fills arguments correctly (IATA codes, YYYY-MM-DD dates, etc.).

Each tool catches its own errors and returns a friendly message, so a bad date or a flaky API never
crashes the agent - the model reads the message and can recover or tell the user.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Annotated

from langchain.tools import tool
from langchain_tavily import TavilySearch
from pydantic import Field


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=20) as resp:
        return json.load(resp)


def _serpapi(params: dict) -> dict:
    """Call SerpApi, returning {'error': ...} on any failure instead of raising."""
    key = os.getenv("SERPAPI_API_KEY")
    if not key:
        return {"error": "SERPAPI_API_KEY is not set. Add it to your .env to enable this tool."}
    params = {**params, "api_key": key}
    url = "https://serpapi.com/search.json?" + urllib.parse.urlencode(params)
    try:
        return _get_json(url)
    except urllib.error.HTTPError as e:
        try:
            return {"error": json.loads(e.read().decode()).get("error", f"SerpApi error (HTTP {e.code}).")}
        except Exception:
            return {"error": f"SerpApi request failed (HTTP {e.code})."}
    except Exception as e:
        return {"error": f"SerpApi request failed: {e}"}


@tool
def get_weather(
    city: Annotated[
        str,
        Field(description="City name, optionally with country to disambiguate. "
                          "Examples: 'Kyoto', 'Paris, France', 'Springfield, US'."),
    ],
    days: Annotated[
        int,
        Field(description="Number of forecast days, from 1 to 7. Example: 3.", ge=1, le=7),
    ] = 3,
) -> str:
    """Get the daily weather forecast for a city. Uses Open-Meteo (free, no key)."""
    try:
        days = max(1, min(int(days), 7))
        q = urllib.parse.quote(city)
        geo = _get_json(
            f"https://geocoding-api.open-meteo.com/v1/search?name={q}&count=1&language=en&format=json"
        )
        if not geo.get("results"):
            return f"Could not find '{city}'. Try adding a country, e.g. 'Paris, France'."
        loc = geo["results"][0]
        lat, lon = loc["latitude"], loc["longitude"]
        place = f"{loc['name']}, {loc.get('country', '')}".strip(", ")
        fc = _get_json(
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max"
            f"&forecast_days={days}&timezone=auto"
        )
        d = fc["daily"]
        lines = [f"Weather for {place} (next {days} day(s)):"]
        for i, date in enumerate(d["time"]):
            lines.append(
                f"  {date}: {d['temperature_2m_min'][i]:.0f}-{d['temperature_2m_max'][i]:.0f}C, "
                f"rain chance {d['precipitation_probability_max'][i]}%"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Sorry, couldn't fetch the weather for '{city}': {e}"


@tool
def web_search(
    query: Annotated[
        str,
        Field(description="A focused search query. "
                          "Examples: 'best vegetarian restaurants in Kyoto', 'visa requirements for Japan'."),
    ],
) -> str:
    """Search the web for travel info: attractions, restaurants, neighborhoods, visas, tips. Uses Tavily."""
    try:
        result = TavilySearch(max_results=4).invoke({"query": query})
        hits = result.get("results", []) if isinstance(result, dict) else []
        if not hits:
            return f"No results for '{query}'."
        out = [f"Top results for '{query}':"]
        for h in hits:
            content = (h.get("content", "") or "").strip().replace("\n", " ")
            out.append(f"- {h.get('title', '').strip()}: {content[:200]} ({h.get('url', '')})")
        return "\n".join(out)
    except Exception as e:
        return f"Sorry, web search failed for '{query}': {e}"


@tool
def search_flights(
    origin: Annotated[
        str,
        Field(description="Departure airport as a 3-letter IATA code. "
                          "Examples: 'JFK' (New York), 'LHR' (London), 'DEL' (Delhi)."),
    ],
    destination: Annotated[
        str,
        Field(description="Arrival airport as a 3-letter IATA code. "
                          "Examples: 'CDG' (Paris), 'NRT' (Tokyo), 'SFO' (San Francisco)."),
    ],
    outbound_date: Annotated[
        str,
        Field(description="Departure date in YYYY-MM-DD format. Must be in the future. Example: '2026-07-10'."),
    ],
    return_date: Annotated[
        str,
        Field(description="Optional return date in YYYY-MM-DD for a round trip. "
                          "Leave empty ('') for one-way. Example: '2026-07-17'."),
    ] = "",
) -> str:
    """Search for flights between two airports. Uses SerpApi's Google Flights engine."""
    try:
        params = {
            "engine": "google_flights",
            "departure_id": origin,
            "arrival_id": destination,
            "outbound_date": outbound_date,
            "currency": "USD",
            "hl": "en",
            "type": "1" if return_date else "2",
        }
        if return_date:
            params["return_date"] = return_date
        data = _serpapi(params)
        if "error" in data:
            return f"Could not search flights: {data['error']} (Tip: dates must be in the future, format YYYY-MM-DD.)"
        options = data.get("best_flights") or data.get("other_flights") or []
        if not options:
            return f"No flights found {origin} -> {destination} on {outbound_date}."
        lines = [f"Flights {origin} -> {destination} on {outbound_date}:"]
        for opt in options[:4]:
            segs = opt.get("flights", [])
            airlines = ", ".join(sorted({s.get("airline", "?") for s in segs}))
            stops = max(len(segs) - 1, 0)
            mins = opt.get("total_duration", 0)
            lines.append(f"  ${opt.get('price', '?')} | {airlines} | {stops} stop(s) | {mins // 60}h{mins % 60:02d}m")
        return "\n".join(lines)
    except Exception as e:
        return f"Sorry, flight search failed: {e}"


@tool
def search_hotels(
    location: Annotated[
        str,
        Field(description="City or area to search hotels in. "
                          "Examples: 'Paris', 'Lisbon city center', 'Shibuya, Tokyo'."),
    ],
    check_in_date: Annotated[
        str,
        Field(description="Check-in date in YYYY-MM-DD format. Must be in the future. Example: '2026-07-10'."),
    ],
    check_out_date: Annotated[
        str,
        Field(description="Check-out date in YYYY-MM-DD format. Example: '2026-07-13'."),
    ],
    adults: Annotated[
        int,
        Field(description="Number of adults. Example: 2.", ge=1),
    ] = 2,
) -> str:
    """Search for hotels in a location for given dates. Uses SerpApi's Google Hotels engine."""
    try:
        data = _serpapi(
            {
                "engine": "google_hotels",
                "q": location,
                "check_in_date": check_in_date,
                "check_out_date": check_out_date,
                "adults": adults,
                "currency": "USD",
                "hl": "en",
            }
        )
        if "error" in data:
            return f"Could not search hotels: {data['error']} (Tip: dates must be in the future, format YYYY-MM-DD.)"
        props = data.get("properties", [])
        if not props:
            return f"No hotels found in {location} for {check_in_date} to {check_out_date}."
        lines = [f"Hotels in {location} ({check_in_date} to {check_out_date}):"]
        for p in props[:4]:
            rate = (p.get("rate_per_night") or {}).get("lowest", "?")
            lines.append(
                f"  {p.get('name', '?')} | {rate}/night | rating {p.get('overall_rating', '?')} | {p.get('hotel_class', '')}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Sorry, hotel search failed: {e}"


TOOLS = [get_weather, web_search, search_flights, search_hotels]
