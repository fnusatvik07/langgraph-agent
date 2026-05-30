# Commands

All the short `just` commands for this workshop. Run them from the **repo root**.

> First time? Install the runner once: `brew install just`. Then `just sync` to build the environment.
> Run `just` (no arguments) anytime to see this list in your terminal.

## All commands

| command | what it does | same thing with uv |
|---------|--------------|--------------------|
| `just` | list all commands | `just --list` |
| `just sync` | install / update the environment from the lockfile | `uv sync` |
| `just start` | launch Jupyter Lab (then pick the **Python (langgraph-workshop)** kernel) | `uv run jupyter lab` |
| `just cli` | run the travel agent CLI (tools run in-process) | `cd travel_agent && uv run --project .. python cli.py` |
| `just mcp` | start the travel-tools **MCP server** (HTTP at `http://127.0.0.1:8000/mcp/`) | `uv run python travel_mcp_server/server.py` |
| `just mcp-cli` | run the travel agent that loads tools **over MCP** (start `just mcp` first) | `cd travel_agent_mcp && uv run --project .. python cli.py` |
| `just inspector` | open the MCP Inspector (connect to `http://127.0.0.1:8000/mcp/`, Streamable HTTP) | `npx @modelcontextprotocol/inspector` |
| `just kernel` | (re)register the Jupyter kernel for this project | `uv run python -m ipykernel install --user --name langgraph-workshop --display-name "Python (langgraph-workshop)"` |

### Aliases

- `just lab`, `just launch`, `just notebook` -> same as `just start`
- `just server` -> same as `just mcp`

## Typical flows

**Run the notebooks**
```bash
just start
# then choose the "Python (langgraph-workshop)" kernel
```

**Run the in-process travel agent (notebooks 01-02)**
```bash
just cli
```

**Run the MCP demo (notebook 03)** - two terminals:
```bash
# terminal 1 - start the tool server, leave it running
just mcp

# terminal 2 - the agent that uses the server
just mcp-cli
```

**Inspect the MCP server** - with `just mcp` running in another terminal:
```bash
just inspector
# connect to  http://127.0.0.1:8000/mcp/   (transport: Streamable HTTP)
```

## Notes

- All commands use the project's pinned uv environment (`.venv`) - you never have to type `uv run` yourself.
- API keys are read from `.env` in the repo root (`OPENAI_API_KEY`, `TAVILY_API_KEY`, `SERPAPI_API_KEY`).
- `SERPAPI_API_KEY` is only needed for the flight/hotel tools.
