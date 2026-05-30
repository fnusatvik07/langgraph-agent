"""Interactive command-line Travel Agent (no memory yet - that's the checkpointer lesson).

Run it:
    just cli
    # or:  cd travel_agent && uv run --project .. python cli.py

You type a request; the agent decides which tools to call. The CLI shows each step (Claude-Code style:
coral action bullets, muted result lines) and renders the final answer as Markdown.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain.messages import HumanMessage
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.theme import Theme

from agent import build_agent

# Claude-Code-inspired palette: coral accent + muted greys.
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
    console.print(Panel("[accent]✻[/] [bold accent]Wanderlust[/]  [dim]·[/]  [muted]AI Travel Agent[/]",
                        border_style="accent", padding=(0, 2)))
    console.print("[muted]Ask anything about a trip. The agent decides which tools to use, then answers.[/]\n")
    console.print("[bold]Try one of these[/] [dim](copy/paste):[/]")
    for ex in EXAMPLES:
        console.print(f"  [accent]›[/] [muted]{ex}[/]")
    console.print("\n[dim]Type 'exit' to quit.[/]\n")


def _oneline(text: str, width: int = 110) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= width else text[:width] + " …"


def _fmt_args(args: dict) -> str:
    return ", ".join(f"{k}={v!r}" for k, v in args.items())


def stream_turn(agent, user_text: str) -> None:
    """Stream one turn: coral action bullets for steps, then the answer as Markdown."""
    console.print(Rule(style="dim"))
    answer = ""
    for mode, payload in agent.stream(
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
                            f"[dim]{tc['name']}({_fmt_args(tc['args'])})[/]"
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


def main() -> None:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY missing. Put it in a .env file.")

    agent = build_agent()
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
        stream_turn(agent, user_text)
    console.print("\n[dim]Safe travels![/]")


if __name__ == "__main__":
    main()
