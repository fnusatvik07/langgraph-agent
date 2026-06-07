"""
LangGraph + MongoDB Checkpointer (NoSQL) - CLI Demo
====================================================
Shows how checkpoints are stored in MongoDB documents (NoSQL).
Uses a custom MongoDBSaver built on BaseCheckpointSaver.

Prerequisites:
  docker compose up -d          (start local MongoDB)
  OR set MONGO_URI to any Atlas / cloud MongoDB connection string

Commands:
  chat     --thread <id>                    Interactive chatbot
  state    --thread <id>                    Latest state snapshot
  history  --thread <id>                    Full checkpoint timeline
  threads                                   List all threads in MongoDB
  replay   --thread <id> --step <n>         Replay from a past step
  fork     --thread <id> --step <n> --fork-thread <new-id>  Fork timeline
  inspect  --thread <id>                    Show raw MongoDB documents

Usage:
  python chat.py chat --thread alice
  python chat.py inspect --thread alice     # unique to MongoDB - see raw docs
  python chat.py threads
"""

import argparse
import os

import pymongo
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langgraph.graph import END, START, StateGraph, MessagesState

from checkpointer import MongoDBSaver

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME   = os.getenv("MONGO_DB", "langgraph")
MODEL     = os.getenv("MODEL", "openai:gpt-4o-mini")

# ── Graph setup ──────────────────────────────────────────────────────────────

llm = init_chat_model(MODEL, temperature=0)

def chat_node(state: MessagesState):
    return {"messages": [llm.invoke(state["messages"])]}

def build_graph():
    client = pymongo.MongoClient(MONGO_URI)
    db = client[DB_NAME]
    checkpointer = MongoDBSaver(db)
    builder = StateGraph(MessagesState)
    builder.add_node("chat", chat_node)
    builder.add_edge(START, "chat")
    builder.add_edge("chat", END)
    graph = builder.compile(checkpointer=checkpointer)
    return graph, client, db

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
    graph, client, _ = build_graph()
    config = {"configurable": {"thread_id": args.thread}}
    print(f"\nMongoDB chatbot  |  thread='{args.thread}'  |  db={DB_NAME}@{MONGO_URI}")
    print("Type 'quit' to exit.\n")
    try:
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
    finally:
        client.close()


def cmd_state(args):
    graph, client, _ = build_graph()
    try:
        config = {"configurable": {"thread_id": args.thread}}
        snap = graph.get_state(config)
        if not snap or not snap.values:
            print(f"No state found for thread '{args.thread}'")
            return
        _print_snapshot(snap, label=f"Thread '{args.thread}'  [MongoDB]")
    finally:
        client.close()


def cmd_history(args):
    graph, client, _ = build_graph()
    try:
        config = {"configurable": {"thread_id": args.thread}}
        history = list(graph.get_state_history(config))
        if not history:
            print(f"No history found for thread '{args.thread}'")
            return
        print(f"\n{'='*60}")
        print(f"  Checkpoint history — thread '{args.thread}'  [MongoDB]")
        print(f"  {len(history)} checkpoints  (newest first)")
        print(f"{'='*60}")
        for i, snap in enumerate(history):
            _print_history_row(snap, i + 1)
        print()
    finally:
        client.close()


def cmd_threads(args):
    client = pymongo.MongoClient(MONGO_URI)
    db = client[DB_NAME]
    checkpointer = MongoDBSaver(db)
    try:
        threads = checkpointer.all_threads()
    finally:
        client.close()

    if not threads:
        print(f"No threads found in MongoDB database '{DB_NAME}'")
        return

    print(f"\n{'='*60}")
    print(f"  All threads in MongoDB '{DB_NAME}.checkpoints'")
    print(f"  {len(threads)} thread(s) found")
    print(f"{'='*60}")

    graph, client2, _ = build_graph()
    try:
        for thread_id in sorted(threads):
            config = {"configurable": {"thread_id": thread_id}}
            snap = graph.get_state(config)
            msgs = len(snap.values.get("messages", [])) if snap and snap.values else 0
            ckpt_count = db["checkpoints"].count_documents({"thread_id": thread_id})
            print(f"  {thread_id:<30}  checkpoints={ckpt_count:>3}  messages={msgs:>3}")
    finally:
        client2.close()
    print()


def cmd_replay(args):
    graph, client, _ = build_graph()
    try:
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
    finally:
        client.close()


def cmd_fork(args):
    graph, client, _ = build_graph()
    try:
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
    finally:
        client.close()


def cmd_inspect(args):
    """Show the raw MongoDB documents for a thread - unique to the NoSQL demo."""
    client = pymongo.MongoClient(MONGO_URI)
    db = client[DB_NAME]
    try:
        docs = list(
            db["checkpoints"]
            .find({"thread_id": args.thread}, {"_id": 0, "checkpoint": 0, "metadata": 0})
            .sort("checkpoint_id", pymongo.DESCENDING)
        )
        if not docs:
            print(f"No documents found for thread '{args.thread}'")
            return
        writes = list(
            db["checkpoint_writes"]
            .find({"thread_id": args.thread}, {"_id": 0, "value": 0})
            .sort("checkpoint_id", pymongo.DESCENDING)
        )
        print(f"\n{'='*60}")
        print(f"  Raw MongoDB documents — thread '{args.thread}'  [NoSQL]")
        print(f"{'='*60}")
        print(f"\n  COLLECTION: checkpoints  ({len(docs)} docs)")
        for doc in docs:
            print(f"    checkpoint_id      : {doc.get('checkpoint_id', '-')[:32]}...")
            print(f"    parent_checkpoint_id: {str(doc.get('parent_checkpoint_id', '-'))[:32]}")
            print(f"    type               : {doc.get('type', '-')}")
            print(f"    meta_step          : {doc.get('meta_step', '-')}")
            print(f"    meta_source        : {doc.get('meta_source', '-')}")
            print()
        print(f"  COLLECTION: checkpoint_writes  ({len(writes)} docs)")
        for w in writes:
            print(f"    checkpoint_id: {w.get('checkpoint_id', '-')[:16]}...  "
                  f"task_id: {w.get('task_id', '-')[:8]}...  "
                  f"channel: {w.get('channel', '-')}")
    finally:
        client.close()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="LangGraph + MongoDB (NoSQL) checkpointer demo",
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

    sub.add_parser("threads", help="List all threads in MongoDB")

    p = sub.add_parser("replay", help="Replay the graph from a past checkpoint step")
    p.add_argument("--thread", required=True)
    p.add_argument("--step", type=int, required=True)

    p = sub.add_parser("fork", help="Fork a thread at a specific checkpoint")
    p.add_argument("--thread", required=True)
    p.add_argument("--step", type=int, required=True)
    p.add_argument("--fork-thread", required=True, dest="fork_thread")

    p = sub.add_parser("inspect", help="Show raw MongoDB documents (NoSQL view)")
    p.add_argument("--thread", required=True)

    args = parser.parse_args()
    {
        "chat":    cmd_chat,
        "state":   cmd_state,
        "history": cmd_history,
        "threads": cmd_threads,
        "replay":  cmd_replay,
        "fork":    cmd_fork,
        "inspect": cmd_inspect,
    }[args.cmd](args)


if __name__ == "__main__":
    main()
