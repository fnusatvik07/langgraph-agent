# LangGraph Checkpointers - SQLite · PostgreSQL · MongoDB

Three self-contained CLI demos that show how LangGraph persistence works
across different storage backends - all with identical commands so you can
compare what changes (just the backend) vs what stays the same (everything else).

## Supported checkpointers (as of LangGraph 1.1)

| Checkpointer | Package | Type | Use case |
|---|---|---|---|
| `InMemorySaver` | `langgraph` (built-in) | In-memory | Dev / quick testing |
| `SqliteSaver` | `langgraph-checkpoint-sqlite` | SQL (local file) | Local scripts, notebooks |
| `AsyncSqliteSaver` | `langgraph-checkpoint-sqlite` | SQL async | Async local apps |
| `PostgresSaver` | `langgraph-checkpoint-postgres` | SQL (server) | Production |
| `AsyncPostgresSaver` | `langgraph-checkpoint-postgres` | SQL async | Production async |
| `CosmosDBSaver` | `langchain-azure-cosmosdb` | NoSQL (Azure) | Azure production |
| `MongoDBSaver` | custom (this repo) | NoSQL (document) | MongoDB / Atlas |

---

## CLI commands (same for all three backends)

```bash
# Start / continue a conversation
python chat.py chat --thread alice

# Show the latest state snapshot
python chat.py state --thread alice

# Show every checkpoint ever saved for a thread
python chat.py history --thread alice

# List every thread stored in the database
python chat.py threads

# Time travel: replay the graph from a past step
python chat.py replay --thread alice --step 2

# Fork: branch the timeline from a past step into a new thread
python chat.py fork --thread alice --step 2 --fork-thread alice-v2
```

MongoDB also has:
```bash
# Inspect raw NoSQL documents in MongoDB
python chat.py inspect --thread alice
```

---

## Quick start

### 1 · SQLite (local, no setup)

```bash
cd sqlite
pip install -r requirements.txt

cp ../.env.example .env   # add your OPENAI_API_KEY

python chat.py chat --thread alice
# > talk to the bot ...

python chat.py history --thread alice
python chat.py threads
```

**What's stored:** a single `.db` file (`checkpoints.db` by default).  
Each row in the `checkpoints` table = one LangGraph super-step.

---

### 2 · PostgreSQL (production SQL)

```bash
cd postgres
pip install -r requirements.txt

docker compose up -d          # starts Postgres on port 5433
# OR set DATABASE_URL in .env to point at Supabase / RDS / etc.

cp ../.env.example .env

python chat.py chat --thread alice
python chat.py history --thread alice
python chat.py threads
```

**What's stored:** two Postgres tables - `checkpoints` and `checkpoint_writes`.  
`checkpointer.setup()` creates them automatically on first run.

---

### 3 · MongoDB (NoSQL)

```bash
cd mongodb
pip install -r requirements.txt

docker compose up -d          # starts MongoDB on port 27017
# OR set MONGO_URI in .env to point at Atlas

cp ../.env.example .env

python chat.py chat --thread alice
python chat.py inspect --thread alice   # see raw NoSQL documents!
python chat.py threads
```

**What's stored:** two MongoDB collections - `checkpoints` and `checkpoint_writes`.  
Each checkpoint is a BSON document - you can see the raw structure with `inspect`.

---

## What each state command shows

```
========================================
  Thread 'alice'  [SQLite]
========================================
  Checkpoint : 1ef663ba-28fe-6528...
  Step       : 6
  Messages   : 6
  Next nodes : (done)
  Source     : loop

  Conversation:
    [1] YOU:   Hi! My name is Satvik and I love LangGraph.
    [2] BOT:   Hi Satvik! It's great to hear that you love LangGraph!
    [3] YOU:   What's my name and what do I love?
    [4] BOT:   Your name is Satvik, and you love LangGraph!
    [5] YOU:   What programming stack do I probably use?
    [6] BOT:   Given your love of LangGraph, you likely use Python...
```

## What history shows

```
  6 checkpoints (newest first)
  [ 1] step=  6  msgs= 6  next=()              ckpt=1ef663ba-28fe-6528...
         last: 'Given your love of LangGraph...'
  [ 2] step=  5  msgs= 5  next=('chat',)       ckpt=1ef663ba-28f9-6ec4...
         last: 'What programming stack do I...'
  [ 3] step=  4  msgs= 4  next=()              ckpt=...
  ...
```

## Key concepts

- **Thread** = one conversation. Pass the same `thread_id` to continue it.
- **Checkpoint** = a snapshot saved after every super-step.
- **get_state** = open the latest checkpoint for a thread.
- **get_state_history** = see every checkpoint ever saved (time travel!).
- **replay** = `graph.invoke(None, checkpoint_config)` - re-run from any past step.
- **fork** = `graph.update_state(new_thread_config, values)` - branch the timeline.

The only thing that differs across SQLite, Postgres, and MongoDB is the
`checkpointer=` argument at compile time. The graph, the LLM, and all the
state commands work identically.
