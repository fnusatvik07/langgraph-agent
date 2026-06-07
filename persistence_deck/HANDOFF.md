# HANDOFF - LangGraph Persistence & Short-term Memory deck

Read this fully before doing anything. It captures the complete state of this project so a
new session can continue without re-deriving context.

## What this is
A cinematic PowerPoint workshop deck on **LangGraph Persistence & Short-term Memory**, built
from https://docs.langchain.com/oss/python/langgraph/persistence (scope: through short-term
memory; long-term Store shown only as the contrast). Built with the `cinematic-deck` skill
(SVG -> PNG via rsvg-convert -> .pptx via python-pptx), plus draw.io diagrams and GIF animations.

## Where everything lives
- Project root: `/Users/datasense/Desktop/langgrapgh-agent/persistence_deck/`
- Build dir:   `persistence_deck/build/`
  - `engine.py`        - cinematic-deck SVG->PNG->pptx engine (PALETTE block re-themed)
  - `deck.py`          - the deck: 28 slides in `SLIDES`, `build()` renders + assembles
  - `drawio_assets.py` - 16 draw.io concept diagrams as mxGraph XML, rendered to `out/dg/*.png`
  - `anim.py`          - `make_gif()` helper (SVG frames -> looping GIF)
  - `out/`             - rendered slide PNGs, `out/dg/` diagram PNGs, `anim_*.gif`, the `.pptx`

## How to build (IMPORTANT: use the skill venv, not system python)
```bash
cd /Users/datasense/Desktop/langgrapgh-agent/persistence_deck/build
VENV=~/.claude/skills/cinematic-deck/scripts/.venv/bin/python
$VENV drawio_assets.py --force   # re-render draw.io diagrams (uses `drawio` CLI; ~1s each)
$VENV deck.py                    # renders all slides + builds the .pptx
```
- `deck.py build()` renders draw.io diagrams (cached), builds 6 GIFs, renders 28 slides,
  writes a contact sheet, and emits a full + compressed .pptx.
- Current output filenames: `out/LangGraph_Persistence_v5.pptx` and `..._v5_compressed.pptx`.
- **Bump the version filename every rebuild** (v6, v7, ...). PowerPoint will NOT reload a file
  that is already open under the same name. Always hand the user a NEW filename, prefer opening
  the compressed one (the full file is ~83 MB).

## Theme - LangGraph brand (navy + blue). DO NOT invent new palettes.
Pulled from docs.langchain.com CSS. In `engine.py` PALETTE block:
- bg `#030710` / `#0B1426`, surfaces `#121C33 #1A2842 #243455`
- primary blue `BLUE=#2E8BFF`, `BLUED=#006DDD`, light `SKYBLUE=#9FD4FF`
- `GOLD` slot repurposed to light-blue `#7FC8FF` (no amber), `CREAM=#DCEBFB`
- `GREEN` repurposed to blue `#3B9EFF` (NO green anywhere), `RED=#FF6B6B` for errors only
- draw.io diagrams (`drawio_assets.py` palette): navy fills, blue primary, coral `#FF8FA3`
  as the second tone (echoes the pink/blue in LangGraph's own docs diagrams)

## Deck structure (28 slides, tight focus)
```
01 title
02 GIF: stateless agent (the problem)
03 statement: "What if every step was saved?"
04 d_arch: how persistence fits together
05 code: 3-line compile with checkpointer
06 statement: "A thread is one save file."
07 d_thread: thread isolation diagram
08 GIF: threads accumulating independently
09 statement: "A checkpoint is a snapshot."
10 d_superstep: when checkpoints happen
11 d_lifecycle: the mechanism (node->delta->reducer->state->checkpoint) [NEW in v5]
12 GIF: checkpoints building step by step (with delta writes shown) [IMPROVED in v5]
13 d_state: worked example - state evolves across 4 checkpoints
14 d_reducer: overwrite vs append (foo vs bar)
15 d_snapshot: StateSnapshot anatomy
16 code: get_state + get_state_history
17 d_history: newest-first ordering
18 statement: "Replay the past. Fork the future."
19 d_replay: how replay actually works (swimlane)
20 GIF: time travel animation
21 d_fork: forking with update_state
22 d_hitl: human-in-the-loop flow
23 GIF: HITL step by step
24 statement: "Short-term memory is thread-scoped persistence."
25 GIF: memory growing on a thread
26 d_shortlong: short-term vs long-term memory
27 d_libs: checkpointer libraries
28 statement: "Remember. Resume. Rewind. Recover."
```
6 GIFs, 12 draw.io diagram slides, 2 code slides, 8 statement slides.

## draw.io diagrams (16 total, all in out/dg/)
d_arch, d_thread, d_state, d_superstep, d_replay, d_fork, d_snapshot, d_reducer,
d_history, d_fault (not in deck but rendered), d_hitl, d_shortlong, d_durability (not in deck),
d_libs, d_recap (not in deck), **d_lifecycle** (NEW).

## Known draw.io gotcha: reserved cell IDs
The draw.io CLI silently fails to export if any mxCell uses a reserved id like `"reduce"`.
The fix applied: rename `"reduce"` to `"rdx"` in d_lifecycle. Always use prefixed/unique ids
(e.g. `lc_reduce`, `rdx`, `step3`) rather than bare English words that might be JS internals.

## OPEN ITEMS
1. **Visual QA done for v5.** All 28 slides eyeballed via contact sheet - navy/blue confirmed,
   no green/amber, all draw.io diagrams rendering. No layout overlaps observed.
2. **Durability modes (d_durability) and fault tolerance (d_fault) slides were cut** to keep
   the deck tight at 28 slides. They can be added back as slides 27a/27b if the workshop needs
   the "production knobs" section.
3. **Official docs images** (checkpoints_full_story.jpg, get_state.jpg, re_play.png, etc.) are
   still in `assets/official/` but no longer used in slides - the draw.io diagrams cover the
   same concepts. Can be added back with `official_slide()` if desired.
4. Commits, if any, use the user's own git identity (no Claude attribution).
5. Plain hyphens only - never em-dashes (caused drawio CLI export failure, now fixed).

## Tools confirmed available this machine
- `drawio` CLI at `/opt/homebrew/bin/drawio` (exports .drawio -> transparent PNG, works headless)
- `rsvg-convert` (homebrew), the cinematic-deck venv (python-pptx + Pillow)
- NOT available: Eraser MCP.
