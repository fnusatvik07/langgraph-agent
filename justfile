# LangGraph workshop - short commands.  Run `just` to see this list.
# These wrap the uv environment, so you never have to type `uv run ...` yourself.

# show all available commands
default:
    @just --list

# install / update the environment from the lockfile
sync:
    uv sync

# launch Jupyter Lab (then pick the "Python (langgraph-workshop)" kernel)
start:
    uv run jupyter lab

# start the travel-tools MCP server (HTTP at http://127.0.0.1:8000/mcp/)
mcp:
    uv run python travel_mcp_server/server.py

# run the travel agent CLI (tools run in-process)
cli:
    cd travel_agent && uv run --project .. python cli.py

# run the travel agent CLI that uses the MCP server  (start `just mcp` first, in another terminal)
mcp-cli:
    cd travel_agent_mcp && uv run --project .. python cli.py

# open the MCP Inspector (connect to http://127.0.0.1:8000/mcp/ , Streamable HTTP)
inspector:
    npx @modelcontextprotocol/inspector

# (re)register the Jupyter kernel for this project
kernel:
    uv run python -m ipykernel install --user --name langgraph-workshop --display-name "Python (langgraph-workshop)"

alias lab := start
alias launch := start
alias notebook := start
alias server := mcp
