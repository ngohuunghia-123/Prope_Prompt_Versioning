"""In-memory workflow store.

Keeps workflow runs by `workflow_id` so the HTTP API can:
- POST /optimize  -> create run, kick off workflow, return id
- GET  /workflows/{id} -> fetch current state

Thread-safe enough for a single-process demo. Real production swaps this
for a Postgres-backed persistence layer.
"""
from __future__ import annotations

import asyncio
from typing import Any


class WorkflowStore:
    def __init__(self) -> None:
        self._runs: dict[str, dict[str, Any]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def get(self, workflow_id: str) -> dict[str, Any] | None:
        return self._runs.get(workflow_id)

    def list(self) -> list[dict[str, Any]]:
        return [
            {
                "workflow_id": k,
                "stage": v.get("stage"),
                "started_at": v.get("started_at"),
                "finished_at": v.get("finished_at"),
            }
            for k, v in self._runs.items()
        ]

    def upsert(self, workflow_id: str, state: dict[str, Any]) -> None:
        self._runs[workflow_id] = state

    def lock_for(self, workflow_id: str) -> asyncio.Lock:
        lock = self._locks.setdefault(workflow_id, asyncio.Lock())
        return lock


store = WorkflowStore()
