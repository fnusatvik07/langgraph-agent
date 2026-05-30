"""The Travel Agent - tools loaded from an MCP server instead of defined in-process.

Compare this with `travel_agent/agent.py`:
- there, tools were Python functions passed straight to create_agent.
- here, the tools live in a separate MCP server; we connect over HTTP and load them at runtime.

The agent itself is identical - create_agent doesn't care where the tools came from. Loading MCP tools
is async, so `build_agent()` is a coroutine.
"""
from __future__ import annotations

import os
from datetime import date

from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

# where the FastMCP server is listening (see travel_mcp_server/server.py)
MCP_URL = os.getenv("TRAVEL_MCP_URL", "http://127.0.0.1:8000/mcp/")


def system_prompt() -> str:
    today = date.today()
    return f"""You are "Wanderlust", a friendly, practical travel-planning assistant.

Today's date is {today:%A, %B %d, %Y} (i.e. {today:%Y-%m-%d}). Always plan for FUTURE dates:
- If the user gives a month/season with no year, use the next upcoming occurrence; never a past date.
- Always pass dates to tools in YYYY-MM-DD format.

Tools: get_weather (real forecast, only next 7 days - otherwise give seasonal weather and say so),
web_search (attractions/food/visas/tips), search_flights (needs 3-letter IATA codes - infer them from
the city, e.g. Chicago -> ORD, Tokyo -> NRT), search_hotels (place + check-in/out dates).

Be self-correcting: if a tool reply starts with "Sorry" / "Could not", fix the arguments (past date ->
future, bad airport code) and try again. Make reasonable assumptions for minor missing details and
state them; respect any budget. Be concise and concrete, and end a trip plan with a day-by-day itinerary."""


def make_client() -> MultiServerMCPClient:
    return MultiServerMCPClient(
        {"travel": {"url": MCP_URL, "transport": "streamable_http"}}
    )


async def build_agent():
    """Connect to the MCP server, load its tools, and build the agent."""
    client = make_client()
    tools = await client.get_tools()  # <- the only real difference from the in-process version
    return create_agent(
        model="openai:gpt-4o-mini",
        tools=tools,
        system_prompt=system_prompt(),
    )
