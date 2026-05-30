"""Interactive Travel Agent whose tools come from an MCP server (Claude-Code-style display).

First start the server (another terminal):  just mcp
Then run this CLI:                           just mcp-cli

Same display as travel_agent/cli.py - the only difference is the tools are loaded from the MCP server.
"""
from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv
from langchain.messages import HumanMessage
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.theme import Theme

from agent import MCP_URL, build_agent

THEME = Theme({
    "accent": "#d97757",     # Claude coral
    "accent2": "#c15f3c",
    "muted": "grey62",
    "dim": "grey39",
    "ok": "#7da06f",
})
console = Console(theme=THEME)

EXAMPLES = [
    "Plan a 5-day trip to Tokyo in October - I love food and temples.",
    "Fly JFK to CDG on 2026-07-10, 3 nights in Paris. Flights, hotels, and weather.",
    "Cheapest flights from Delhi (DEL) to London (LHR) on 2026-09-15?",
    "7-day Delhi itinerary from New York in July: flights, hotels, and top sights.",
    "Weather in Lisbon this weekend and a great seafood restaurant.",
]

TOOL_LABEL = {
    "get_weather": "weather",
    "web_search": "web search",
    "search_flights": "flights",
    "search_hotels": "hotels",
}


def banner() -> None:
    console.print()
    console.print(Panel("[accent]✻[/] [bold accent]Wanderlust[/]  [dim]·[/]  [muted]Travel Agent (tools via MCP)[/]",
                        border_style="accent", padding=(0, 2)))
    console.print(f"[muted]Tools loaded from the MCP server at {MCP_URL}[/]\n")
    console.print("[bold]Try one of these[/] [dim](copy/paste):[/]")
    for ex in EXAMPLES:
        console.print(f"  [accent]›[/] [muted]{ex}[/]")
    console.print("\n[dim]Type 'exit' to quit.[/]\n")


def _extract(content) -> str:
    if isinstance(content, list):
        return " ".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return str(content)


def _oneline(content, width: int = 110) -> str:
    text = " ".join(_extract(content).split())
    return text if len(text) <= width else text[:width] + " …"


def _fmt_args(args: dict) -> str:
    return ", ".join(f"{k}={v!r}" for k, v in args.items())


async def stream_turn(agent, user_text: str) -> None:
    console.print(Rule(style="dim"))
    answer = ""
    async for mode, payload in agent.astream(
        {"messages": [HumanMessage(user_text)]},
        stream_mode=["updates", "messages"],
    ):
        if mode == "updates":
            for _node, update in payload.items():
                msg = update["messages"][-1]
                if getattr(msg, "tool_calls", None):
                    for tc in msg.tool_calls:
                        label = TOOL_LABEL.get(tc["name"], tc["name"])
                        console.print(
                            f"[accent]⏺[/] [bold]{label}[/]  "
                            f"[dim]{tc['name']}({_fmt_args(tc['args'])})[/] [dim]· via MCP[/]"
                        )
                elif msg.type == "tool":
                    console.print(f"  [dim]⎿[/]  [muted]{_oneline(msg.content)}[/]")
        elif mode == "messages":
            token, meta = payload
            if token.content and meta.get("langgraph_node") == "model":
                answer += token.content

    if answer:
        console.print()
        console.print(Panel(Markdown(answer), title="[accent]✻ Wanderlust[/]", title_align="left",
                            border_style="accent", padding=(1, 2)))
    console.print()


async def main() -> None:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY missing. Put it in a .env file.")
    try:
        agent = await build_agent()
    except Exception as exc:
        raise SystemExit(
            f"Could not connect to the MCP server at {MCP_URL}.\n"
            f"Start it first:  just mcp   (or: uv run python travel_mcp_server/server.py)\n({exc})"
        )

    banner()
    while True:
        try:
            user_text = console.input("[bold accent]›[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_text:
            continue
        if user_text.lower() in {"exit", "quit"}:
            break
        await stream_turn(agent, user_text)
    console.print("\n[dim]Safe travels![/]")


if __name__ == "__main__":
    asyncio.run(main())
