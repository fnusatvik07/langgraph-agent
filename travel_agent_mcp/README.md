# Wanderlust over MCP

The same travel agent as `../travel_agent/`, except the tools are **loaded from the MCP server** at
`../travel_mcp_server/` over HTTP instead of being defined in this process.

The only real code difference is in `agent.py`:

```python
# travel_agent/agent.py  (in-process)
agent = create_agent(model, tools=[get_weather, web_search, ...], system_prompt=...)

# travel_agent_mcp/agent.py  (over MCP)
client = MultiServerMCPClient({"travel": {"url": "http://127.0.0.1:8000/mcp/", "transport": "streamable_http"}})
tools = await client.get_tools()
agent = create_agent(model, tools=tools, system_prompt=...)
```

`create_agent` doesn't care where the tools came from - the agent behaves identically.

## Run it

```bash
# terminal 1 - start the tool server
uv run python travel_mcp_server/server.py

# terminal 2 - run the agent
uv run python travel_agent_mcp/cli.py
```

Type a request and watch the agent decide which tools to call; each call is tagged `[from MCP server]`.

## Files

- `agent.py` - builds the agent, loading tools from the MCP server (async)
- `cli.py`   - the same colourful streaming CLI as `travel_agent/`, async

The server URL can be overridden with the `TRAVEL_MCP_URL` env var.
