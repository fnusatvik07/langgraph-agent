"""
LangGraph + SQLite Checkpointer - CLI Demo
==========================================
Shows how checkpoints are stored in a local SQLite file.

Commands:
  chat     --thread <id>                    Interactive chatbot
  state    --thread <id>                    Latest state snapshot
  history  --thread <id>                    Full checkpoint timeline
  threads                                   List all threads in the DB
  replay   --thread <id> --step <n>         Replay from a past step
  fork     --thread <id> --step <n> --fork-thread <new-id>  Fork timeline

Usage:
  python chat.py chat --thread alice
  python chat.py history --thread alice
  python chat.py threads
  python chat.py replay --thread alice --step 2
"""

import argparse
import os
import sqlite3
import sys

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph, MessagesState

load_dotenv()

DB_PATH = os.getenv("SQLITE_DB_PATH", "checkpoints.db")
MODEL   = os.getenv("MODEL", "openai:gpt-4o-mini")

# ── Graph setup ──────────────────────────────────────────────────────────────

llm = init_chat_model(MODEL, temperature=0)

def chat_node(state: MessagesState):
    return {"messages": [llm.invoke(state["messages"])]}

def build_graph():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    builder = StateGraph(MessagesState)
    builder.add_node("chat", chat_node)
    builder.add_edge(START, "chat")
    builder.add_edge("chat", END)
    graph = builder.compile(checkpointer=checkpointer)
    return graph, conn

# ── Helpers ───────────────────────────────────────────────────────────────────

def _print_snapshot(snap, label="State snapshot"):
    msgs = snap.values.get("messages", [])
    ckpt_id = snap.config["configurable"].get("checkpoint_id", "-")
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  Checkpoint : {ckpt_id[:32]}...")
    print(f"  Step       : {snap.metadata.get('step', '?')}")
    print(f"  Messages   : {len(msgs)}")
    print(f"  Next nodes : {snap.next or '(done)'}")
    print(f"  Source     : {snap.metadata.get('source', '?')}")
    if msgs:
        print(f"\n  Conversation:")
        for i, m in enumerate(msgs, 1):
            icon = "YOU:" if m.type == "human" else "BOT:"
            content = m.content.replace("\n", " ")
            print(f"    [{i}] {icon:<5} {content[:72]}")
    print()

def _print_history_row(snap, idx):
    msgs = snap.values.get("messages", [])
    ckpt_id = snap.config["configurable"].get("checkpoint_id", "-")
    last = msgs[-1].content[:40].replace("\n", " ") if msgs else "-"
    print(f"  [{idx:>2}] step={snap.metadata.get('step'):>3}  "
          f"msgs={len(msgs):>2}  "
          f"next={str(snap.next):<16}  "
          f"ckpt={ckpt_id[:16]}...")
    print(f"       last: {last!r}")

# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_chat(args):
    graph, _ = build_graph()
    config = {"configurable": {"thread_id": args.thread}}
    print(f"\nSQLite chatbot  |  thread='{args.thread}'  |  db={DB_PATH}")
    print("Type 'quit' to exit.\n")
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if user_input.lower() in ("quit", "exit", "q"):
            break
        if not user_input:
            continue
        result = graph.invoke(
            {"messages": [{"role": "user", "content": user_input}]}, config
        )
        print(f"Bot: {result['messages'][-1].content}\n")


def cmd_state(args):
    graph, _ = build_graph()
    config = {"configurable": {"thread_id": args.thread}}
    snap = graph.get_state(config)
    if not snap or not snap.values:
        print(f"No state found for thread '{args.thread}' in {DB_PATH}")
        return
    _print_snapshot(snap, label=f"Thread '{args.thread}'  [SQLite]")


def cmd_history(args):
    graph, _ = build_graph()
    config = {"configurable": {"thread_id": args.thread}}
    history = list(graph.get_state_history(config))
    if not history:
        print(f"No history found for thread '{args.thread}' in {DB_PATH}")
        return
    print(f"\n{'='*60}")
    print(f"  Checkpoint history — thread '{args.thread}'  [SQLite]")
    print(f"  {len(history)} checkpoints  (newest first)")
    print(f"{'='*60}")
    for i, snap in enumerate(history):
        _print_history_row(snap, i + 1)
    print()


def cmd_threads(args):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT thread_id, COUNT(*) as ckpts, MAX(checkpoint_id) as latest "
            "FROM checkpoints GROUP BY thread_id ORDER BY latest DESC"
        )
        rows = cur.fetchall()
    except Exception as e:
        print(f"Error querying {DB_PATH}: {e}")
        return
    finally:
        conn.close()

    if not rows:
        print(f"No threads found in {DB_PATH}")
        return

    print(f"\n{'='*60}")
    print(f"  All threads in {DB_PATH}  [SQLite]")
    print(f"  {len(rows)} thread(s) found")
    print(f"{'='*60}")

    graph, _ = build_graph()
    for thread_id, ckpt_count, _ in rows:
        config = {"configurable": {"thread_id": thread_id}}
        snap = graph.get_state(config)
        msgs = len(snap.values.get("messages", [])) if snap and snap.values else 0
        print(f"  {thread_id:<30}  checkpoints={ckpt_count:>3}  messages={msgs:>3}")
    print()


def cmd_replay(args):
    graph, _ = build_graph()
    config = {"configurable": {"thread_id": args.thread}}
    history = list(graph.get_state_history(config))
    target = next(
        (s for s in history if s.metadata.get("step") == args.step), None
    )
    if not target:
        available = sorted({s.metadata.get("step") for s in history})
        print(f"Step {args.step} not found. Available steps: {available}")
        return

    print(f"\nReplaying thread '{args.thread}' from step {args.step}...")
    print(f"  next at that point: {target.next}")
    result = graph.invoke(None, target.config)
    msgs = result.get("messages", [])
    print(f"  Replay complete. Final state: {len(msgs)} messages.")
    for m in msgs:
        icon = "YOU:" if m.type == "human" else "BOT:"
        print(f"    {icon:<5} {m.content[:72]}")
    print()


def cmd_fork(args):
    graph, _ = build_graph()
    config = {"configurable": {"thread_id": args.thread}}
    history = list(graph.get_state_history(config))
    target = next(
        (s for s in history if s.metadata.get("step") == args.step), None
    )
    if not target:
        available = sorted({s.metadata.get("step") for s in history})
        print(f"Step {args.step} not found. Available steps: {available}")
        return

    fork_config = {"configurable": {"thread_id": args.fork_thread}}
    graph.update_state(fork_config, target.values)
    print(f"\nForked '{args.thread}' (step {args.step}) -> new thread '{args.fork_thread}'")
    print(f"  State copied: {len(target.values.get('messages', []))} messages")
    print(f"  Continue with:  python chat.py chat --thread {args.fork_thread}")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="LangGraph + SQLite checkpointer demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("chat", help="Start/continue a chat on a thread")
    p.add_argument("--thread", default="default", help="Thread ID")

    p = sub.add_parser("state", help="Show latest state snapshot for a thread")
    p.add_argument("--thread", required=True)

    p = sub.add_parser("history", help="Show full checkpoint history for a thread")
    p.add_argument("--thread", required=True)

    sub.add_parser("threads", help="List all threads in the SQLite database")

    p = sub.add_parser("replay", help="Replay the graph from a past checkpoint step")
    p.add_argument("--thread", required=True)
    p.add_argument("--step", type=int, required=True, help="Step number to replay from")

    p = sub.add_parser("fork", help="Fork a thread at a specific checkpoint")
    p.add_argument("--thread", required=True, help="Source thread")
    p.add_argument("--step", type=int, required=True, help="Checkpoint step to fork from")
    p.add_argument("--fork-thread", required=True, dest="fork_thread", help="New thread name")

    args = parser.parse_args()
    {
        "chat":    cmd_chat,
        "state":   cmd_state,
        "history": cmd_history,
        "threads": cmd_threads,
        "replay":  cmd_replay,
        "fork":    cmd_fork,
    }[args.cmd](args)


if __name__ == "__main__":
    main()
