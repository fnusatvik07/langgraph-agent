"""
Custom MongoDB CheckpointSaver for LangGraph
============================================
Implements the BaseCheckpointSaver interface using pymongo.

Stores two collections in the configured database:
  - checkpoints       : one doc per (thread_id, checkpoint_ns, checkpoint_id)
  - checkpoint_writes : pending writes for fault-tolerance
"""

from __future__ import annotations

from typing import Any, Iterator, Optional, Sequence, Tuple

import pymongo
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    get_checkpoint_id,
)
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer


class MongoDBSaver(BaseCheckpointSaver):
    """
    MongoDB-backed checkpoint saver for LangGraph.

    Usage:
        from pymongo import MongoClient
        client = MongoClient("mongodb://localhost:27017")
        saver = MongoDBSaver(client["langgraph"])
        graph = builder.compile(checkpointer=saver)
    """

    def __init__(self, db: pymongo.database.Database) -> None:
        super().__init__(serde=JsonPlusSerializer())
        self._checkpoints = db["checkpoints"]
        self._writes = db["checkpoint_writes"]
        self._setup_indexes()

    def _setup_indexes(self) -> None:
        self._checkpoints.create_index(
            [("thread_id", 1), ("checkpoint_ns", 1), ("checkpoint_id", pymongo.DESCENDING)],
            background=True,
        )
        self._writes.create_index(
            [("thread_id", 1), ("checkpoint_ns", 1), ("checkpoint_id", 1), ("task_id", 1), ("idx", 1)],
            unique=True,
            background=True,
        )

    # ── Required: get_next_version ────────────────────────────────────────────

    def get_next_version(self, current: Optional[int], channel) -> int:
        if current is None:
            return 1
        return current + 1

    # ── Required: get_tuple ───────────────────────────────────────────────────

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = get_checkpoint_id(config)

        query: dict[str, Any] = {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns}
        if checkpoint_id:
            query["checkpoint_id"] = checkpoint_id

        doc = self._checkpoints.find_one(
            query, sort=[("checkpoint_id", pymongo.DESCENDING)]
        )
        if not doc:
            return None

        checkpoint = self.serde.loads_typed((doc["type"], doc["checkpoint"]))
        metadata   = self.serde.loads_typed((doc["metadata_type"], doc["metadata"]))

        parent_config = None
        if doc.get("parent_checkpoint_id"):
            parent_config = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": doc["parent_checkpoint_id"],
                }
            }

        pending_writes = []
        for w in self._writes.find(
            {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": doc["checkpoint_id"],
            },
            sort=[("idx", 1)],
        ):
            value = self.serde.loads_typed((w["type"], w["value"]))
            pending_writes.append((w["task_id"], w["channel"], value))

        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": doc["checkpoint_id"],
                }
            },
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=parent_config,
            pending_writes=pending_writes,
        )

    # ── Required: list ────────────────────────────────────────────────────────

    def list(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        query: dict[str, Any] = {}
        if config:
            query["thread_id"] = config["configurable"]["thread_id"]
            query["checkpoint_ns"] = config["configurable"].get("checkpoint_ns", "")
        if filter:
            for k, v in filter.items():
                query[f"meta_{k}"] = v
        if before:
            bid = get_checkpoint_id(before)
            if bid:
                query["checkpoint_id"] = {"$lt": bid}

        cursor = self._checkpoints.find(
            query, sort=[("checkpoint_id", pymongo.DESCENDING)]
        )
        if limit:
            cursor = cursor.limit(limit)

        for doc in cursor:
            checkpoint = self.serde.loads_typed((doc["type"], doc["checkpoint"]))
            metadata   = self.serde.loads_typed((doc["metadata_type"], doc["metadata"]))
            parent_config = None
            if doc.get("parent_checkpoint_id"):
                parent_config = {
                    "configurable": {
                        "thread_id": doc["thread_id"],
                        "checkpoint_ns": doc["checkpoint_ns"],
                        "checkpoint_id": doc["parent_checkpoint_id"],
                    }
                }
            yield CheckpointTuple(
                config={
                    "configurable": {
                        "thread_id": doc["thread_id"],
                        "checkpoint_ns": doc["checkpoint_ns"],
                        "checkpoint_id": doc["checkpoint_id"],
                    }
                },
                checkpoint=checkpoint,
                metadata=metadata,
                parent_config=parent_config,
            )

    # ── Required: put ─────────────────────────────────────────────────────────

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: dict,
    ) -> RunnableConfig:
        thread_id      = config["configurable"]["thread_id"]
        checkpoint_ns  = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id  = checkpoint["id"]
        parent_ckpt_id = config["configurable"].get("checkpoint_id")

        ckpt_type, ckpt_bytes   = self.serde.dumps_typed(checkpoint)
        meta_type, meta_bytes   = self.serde.dumps_typed(metadata)

        doc = {
            "thread_id":           thread_id,
            "checkpoint_ns":       checkpoint_ns,
            "checkpoint_id":       checkpoint_id,
            "parent_checkpoint_id": parent_ckpt_id,
            "type":                ckpt_type,
            "checkpoint":          ckpt_bytes,
            "metadata_type":       meta_type,
            "metadata":            meta_bytes,
        }
        # also index metadata fields for filter queries
        if isinstance(metadata, dict):
            for k, v in metadata.items():
                doc[f"meta_{k}"] = v

        self._checkpoints.replace_one(
            {
                "thread_id":     thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            },
            doc,
            upsert=True,
        )
        return {
            "configurable": {
                "thread_id":     thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    # ── Required: put_writes ──────────────────────────────────────────────────

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        thread_id     = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"]["checkpoint_id"]

        ops = []
        for idx, (channel, value) in enumerate(writes):
            v_type, v_bytes = self.serde.dumps_typed(value)
            ops.append(
                pymongo.ReplaceOne(
                    {
                        "thread_id":     thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": checkpoint_id,
                        "task_id":       task_id,
                        "idx":           idx,
                    },
                    {
                        "thread_id":     thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": checkpoint_id,
                        "task_id":       task_id,
                        "task_path":     task_path,
                        "idx":           idx,
                        "channel":       channel,
                        "type":          v_type,
                        "value":         v_bytes,
                    },
                    upsert=True,
                )
            )
        if ops:
            self._writes.bulk_write(ops, ordered=False)

    # ── Convenience: list all thread_ids ─────────────────────────────────────

    def all_threads(self) -> list[str]:
        return self._checkpoints.distinct("thread_id")
