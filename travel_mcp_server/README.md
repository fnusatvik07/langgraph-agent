# Travel MCP Server

The four travel tools (`get_weather`, `web_search`, `search_flights`, `search_hotels`) exposed over an
**MCP server** using [FastMCP](https://github.com/jlowin/fastmcp), served over **HTTP** (Streamable
HTTP transport - not stdio).

This file depends only on `fastmcp` + the standard library + `python-dotenv` (no LangChain) - the point
of MCP is that the tools are framework-agnostic and any client can use them.

## Run it

```bash
uv run python travel_mcp_server/server.py
# serves at  http://127.0.0.1:8000/mcp/
```

Keys (`TAVILY_API_KEY`, `SERPAPI_API_KEY`) are read from the repo-root `.env`. `get_weather` needs no key.

## Inspect it

In another terminal, open the official MCP Inspector and connect to the running server:

```bash
npx @modelcontextprotocol/inspector
```

- Transport: **Streamable HTTP**
- URL: **`http://127.0.0.1:8000/mcp/`**

You'll see the four tools with their schemas and can call them by hand.

## Use it from an agent

See `../travel_agent_mcp/` - the same travel agent, but it loads these tools over MCP instead of
defining them in-process. Notebook `../03_travel_agent_mcp.ipynb` walks through it.
