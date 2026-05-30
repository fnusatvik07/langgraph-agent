# Wanderlust - a Travel Agent

A small, real travel-planning agent. It's the *simple* agent from `01_agents.ipynb`
(`create_agent` = model + tools + loop), given four useful tools.

> **No memory (on purpose).** This project has no checkpointer, so every question is independent.
> Adding memory across turns is exactly what the **LangGraph checkpointer** lesson covers next - this
> agent is the setup for it.

## Tools

| tool | what it does | key needed |
|------|--------------|------------|
| `get_weather`    | real 1-7 day forecast (Open-Meteo) | none (free) |
| `web_search`     | attractions, food, neighborhoods, tips (Tavily) | `TAVILY_API_KEY` |
| `search_flights` | flights between airports (SerpApi Google Flights) | `SERPAPI_API_KEY` |
| `search_hotels`  | hotels for given dates (SerpApi Google Hotels) | `SERPAPI_API_KEY` |

SerpApi gives both flights and hotels from one key (free tier ~100 searches/month).

## Setup

1. Keys in a `.env` (repo root or this folder):

   ```
   OPENAI_API_KEY=sk-...
   TAVILY_API_KEY=tvly-...
   SERPAPI_API_KEY=...
   ```

2. Install deps (already present if you ran the notebooks):

   ```
   pip install -r requirements.txt
   ```

## Run it

```bash
python cli.py
```

Ask complete questions (the agent has no memory yet, so put everything in one message):

```
You: Fly JFK to CDG on 2026-07-10, 3 nights in Paris. Find flights, hotels, and the weather.
  [calling: search_flights]
  [calling: search_hotels]
  [calling: get_weather]
Wanderlust: Here's your Paris trip...
```

Stop with `exit`.

## How it maps to LangGraph

`create_agent(model, tools, system_prompt)` compiles to this graph:

```
__start__ -> model -> (tool_calls? -> tools -> model)  -> __end__
```

- `model` node = the LLM with `bind_tools` + your `system_prompt`
- `tools` node = runs the four tools
- the back-edge `tools -> model` is the agent loop

## Files

- `tools.py` - the four tools
- `agent.py` - `build_agent()` (no checkpointer)
- `cli.py`   - interactive streaming REPL
