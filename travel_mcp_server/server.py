"""Travel tools exposed over an MCP server using FastMCP (HTTP transport).

Same four tools as the in-process travel agent, but in a standalone server any MCP client can use.
Depends only on `fastmcp` + the standard library + `python-dotenv` (no LangChain).

Each parameter carries a description with an EXAMPLE (via `Annotated[..., Field(...)]`) so the schema is
self-explanatory in the MCP Inspector. Tools return STRUCTURED data (dicts/lists), which the Inspector
renders as a navigable JSON tree instead of one long text blob.

Run it:
    uv run python travel_mcp_server/server.py      # or:  just mcp
    # serves at http://127.0.0.1:8000/mcp/

Inspect it:
    npx @modelcontextprotocol/inspector
    # connect to  http://127.0.0.1:8000/mcp/  (Streamable HTTP)
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Annotated

from dotenv import load_dotenv
from fastmcp import FastMCP
from pydantic import Field

load_dotenv()  # reads TAVILY_API_KEY / SERPAPI_API_KEY from .env

mcp = FastMCP("travel-tools")


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=20) as resp:
        return json.load(resp)


def _post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def _serpapi(params: dict) -> dict:
    """Call SerpApi, returning {'error': ...} on any failure instead of raising."""
    key = os.getenv("SERPAPI_API_KEY")
    if not key:
        return {"error": "SERPAPI_API_KEY is not set on the server."}
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


@mcp.tool
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
) -> dict:
    """Daily weather forecast for a city (1-7 days). Uses Open-Meteo (free, no key)."""
    try:
        q = urllib.parse.quote(city)
        geo = _get_json(
            f"https://geocoding-api.open-meteo.com/v1/search?name={q}&count=1&language=en&format=json"
        )
        if not geo.get("results"):
            return {"error": f"Could not find '{city}'. Try adding a country, e.g. 'Paris, France'."}
        loc = geo["results"][0]
        fc = _get_json(
            f"https://api.open-meteo.com/v1/forecast?latitude={loc['latitude']}&longitude={loc['longitude']}"
            f"&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max"
            f"&forecast_days={days}&timezone=auto"
        )
        d = fc["daily"]
        return {
            "location": f"{loc['name']}, {loc.get('country', '')}".strip(", "),
            "forecast": [
                {
                    "date": d["time"][i],
                    "low_c": d["temperature_2m_min"][i],
                    "high_c": d["temperature_2m_max"][i],
                    "rain_chance_pct": d["precipitation_probability_max"][i],
                }
                for i in range(len(d["time"]))
            ],
        }
    except Exception as e:
        return {"error": f"Could not fetch weather for '{city}': {e}"}


@mcp.tool
def web_search(
    query: Annotated[
        str,
        Field(description="A focused search query. "
                          "Examples: 'best vegetarian restaurants in Kyoto', 'visa requirements for Japan'."),
    ],
) -> dict:
    """Search the web for travel info: attractions, restaurants, visas, tips. Uses Tavily."""
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        return {"error": "TAVILY_API_KEY is not set on the server."}
    try:
        data = _post_json(
            "https://api.tavily.com/search",
            {"api_key": key, "query": query, "max_results": 4},
        )
        return {
            "query": query,
            "results": [
                {
                    "title": h.get("title", "").strip(),
                    "url": h.get("url", ""),
                    "snippet": (h.get("content", "") or "").strip().replace("\n", " ")[:240],
                }
                for h in data.get("results", [])
            ],
        }
    except Exception as e:
        return {"error": f"Web search failed for '{query}': {e}"}


@mcp.tool
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
        Field(description="Departure date in YYYY-MM-DD format. Example: '2026-07-10'."),
    ],
    return_date: Annotated[
        str,
        Field(description="Optional return date in YYYY-MM-DD for a round trip. "
                          "Leave empty ('') for one-way. Example: '2026-07-17'."),
    ] = "",
) -> dict:
    """Search flights between two airports. Uses SerpApi's Google Flights engine."""
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
        return data
    options = data.get("best_flights") or data.get("other_flights") or []
    return {
        "route": f"{origin} -> {destination}",
        "date": outbound_date,
        "trip_type": "round-trip" if return_date else "one-way",
        "options": [
            {
                "price_usd": opt.get("price"),
                "airlines": sorted({s.get("airline", "?") for s in opt.get("flights", [])}),
                "stops": max(len(opt.get("flights", [])) - 1, 0),
                "duration": f"{opt.get('total_duration', 0) // 60}h{opt.get('total_duration', 0) % 60:02d}m",
            }
            for opt in options[:4]
        ],
    }


@mcp.tool
def search_hotels(
    location: Annotated[
        str,
        Field(description="City or area to search hotels in. "
                          "Examples: 'Paris', 'Lisbon city center', 'Shibuya, Tokyo'."),
    ],
    check_in_date: Annotated[
        str,
        Field(description="Check-in date in YYYY-MM-DD format. Example: '2026-07-10'."),
    ],
    check_out_date: Annotated[
        str,
        Field(description="Check-out date in YYYY-MM-DD format. Example: '2026-07-13'."),
    ],
    adults: Annotated[
        int,
        Field(description="Number of adults. Example: 2.", ge=1),
    ] = 2,
) -> dict:
    """Search hotels in a location for given dates. Uses SerpApi's Google Hotels engine."""
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
        return data
    return {
        "location": location,
        "check_in": check_in_date,
        "check_out": check_out_date,
        "hotels": [
            {
                "name": p.get("name", "?"),
                "price_per_night": (p.get("rate_per_night") or {}).get("lowest", "?"),
                "rating": p.get("overall_rating", "?"),
                "class": p.get("hotel_class", ""),
            }
            for p in data.get("properties", [])[:4]
        ],
    }


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8000)
