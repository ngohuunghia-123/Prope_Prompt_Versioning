"""The App-Agent LLM call cache seam: a protocol, a no-op, a Postgres cache.

The design pack (`docs/agent-design/cache/`) decided the shape. This module is the
shared runtime's half of it — a ``Cache`` protocol that callers depend on, a
:class:`NoOpCache` that is the default so every existing caller is byte-identical
until it opts in (00-D10), and a :class:`PostgresCache` that reads and writes the
``evaluation.llm_cache`` row behind a tenant-scoped session.

**Why this lives in ``app_agent`` and the repository lives in ``evaluation``.**
``app_agent`` is the shared runtime every agent module already reaches on the same
terms (the evaluation module-map test says so in as many words). The seam here is
plumbing; the table is evaluation's, and `test_no_cross_schema_sql` refuses any
other module reading it. A later caller (the eval-case drafter, 00-D13) gets the
same protocol and its own repository functions in its own module.

**The key is the contract.** :func:`compute_key` is a deterministic SHA-256 over
*everything the model was asked*: the prompt body and title, the catalogue (or
any caller-specific context string), a program schema version, the model name and
the ``extra_body``. A body edit, a signature edit, a catalogue move and a model
swap each produce a different key — that is the whole invalidation story, and
there is deliberately no other one (02-D4/D7/D8).

**Prompt bodies do not reach disk and do not reach telemetry (A-020/A-046).** The
key is a hash, and the stored row holds only the gated model output plus token
counts. Nothing in this module ever writes the body or the title anywhere.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Protocol, runtime_checkable

from prope.app_agent.client import APP_AGENT_MODEL

__all__ = [
    "Cache",
    "CacheMeta",
    "NoOpCache",
    "PostgresCache",
    "PROGRAM_SCHEMA_VERSION",
    "compute_key",
]

#: Bumped on any DSPy signature or instruction edit that changes what a program
#: is being asked, so a new question never reads an old answer (02-D7). One
#: constant for the whole runtime; a caller that needs its own invalidation axis
#: folds that axis into its key inputs instead.
PROGRAM_SCHEMA_VERSION = 1

#: How long a row may be served. Enforced at read, not at write — an expired row
#: simply stops being served, and the next identical ask is a fresh call.
LLM_CACHE_TTL_HOURS = float(os.getenv("LLM_CACHE_TTL_HOURS", "24"))


@dataclass(frozen=True, slots=True)
class CacheMeta:
    """The non-answer facts a row carries, for cost accounting and diagnostics."""

    program: str
    model: str
    input_tokens: int
    output_tokens: int


@runtime_checkable
class Cache(Protocol):
    """What a caller depends on. ``get`` returns ``None`` on a miss; ``put`` is best-effort.

    The value a ``get`` returns is the stored row's ``findings`` rehydrated to
    the object shape the caller's gate reads — the same attribute shape a DSPy
    prediction has — so a cached answer flows through the exact same gate as a
    fresh one (05-D1). ``put`` receives plain dicts (the JSON-storable form).

    A read failure is a miss and a write failure is a no-op — the cache is an
    optimization, never a dependency (07-D3). Callers pass this in; nothing in
    the runtime holds a process-wide instance (00-D7).
    """

    async def get(self, key: str) -> tuple[list[Any], CacheMeta] | None: ...

    async def put(
        self,
        key: str,
        value: list[dict[str, Any]],
        meta: CacheMeta,
    ) -> None: ...


class NoOpCache:
    """The default: every call is a miss, every put is a no-op.

    This is what makes the seam safe to introduce: until a caller opts in by
    passing a :class:`PostgresCache`, its behaviour is byte-identical to before
    the cache existed.
    """

    async def get(self, key: str) -> tuple[list[Any], CacheMeta] | None:
        return None

    async def put(
        self,
        key: str,
        value: list[dict[str, Any]],
        meta: CacheMeta,
    ) -> None:
        return None


class PostgresCache:
    """A cache over ``evaluation.llm_cache``, behind the caller's tenant-scoped session.

    The caller owns the ``AsyncSession`` — the one already scoped to its
    ``workspace_id`` under ``workspace_transaction`` — and passes that
    ``workspace_id`` here, so the row's tenant boundary is the same RLS
    predicate every evaluation table carries. The repository functions this
    calls live in ``prope.evaluation.repository``; this class is the transport,
    not the SQL.
    """

    def __init__(self, repository: Any, *, workspace_id: str) -> None:
        self._repository = repository
        self._workspace_id = workspace_id

    async def get(self, key: str) -> tuple[list[Any], CacheMeta] | None:
        row = await self._repository.read_cached_llm(
            workspace_id=self._workspace_id, key=key
        )
        if row is None:
            return None
        # The stored JSON is dicts; rehydrate to the object shape the caller's
        # gate reads (the same attribute shape a DSPy prediction has), so the
        # cached answer flows through the exact same gate as a fresh one.
        findings = [SimpleNamespace(**entry) for entry in row["findings"]]
        return findings, CacheMeta(
            program=row["program"],
            model=row["model"],
            input_tokens=int(row["input_tokens"] or 0),
            output_tokens=int(row["output_tokens"] or 0),
        )

    async def put(
        self,
        key: str,
        value: list[dict[str, Any]],
        meta: CacheMeta,
    ) -> None:
        await self._repository.write_cached_llm(
            workspace_id=self._workspace_id,
            key=key,
            program=meta.program,
            model=meta.model,
            findings=value,
            input_tokens=meta.input_tokens,
            output_tokens=meta.output_tokens,
        )


def compute_key(
    *,
    prompt_body: str,
    prompt_title: str,
    catalogue: str,
    model: str | None = None,
    extra_body: dict[str, Any] | None = None,
    schema_version: int = PROGRAM_SCHEMA_VERSION,
) -> str:
    """The deterministic cache key: everything the model was asked, hashed.

    ``temperature``, ``num_retries`` and ``timeout`` are deliberately absent
    (02-D5/D6): they change transport, not semantics, and keying on them would
    fragment the cache for no correctness gain. ``extra_body`` IS present because
    a reasoning tier's thinking setting can change what the model returns
    (02-D3).
    """
    digest = hashlib.sha256()
    digest.update(b"\x00".join(
        (
            str(schema_version).encode("utf-8"),
            (model or APP_AGENT_MODEL).encode("utf-8"),
            prompt_title.encode("utf-8"),
            prompt_body.encode("utf-8"),
            catalogue.encode("utf-8"),
        )
    ))
    if extra_body:
        digest.update(b"\x00")
        digest.update(
            json.dumps(extra_body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
    return digest.hexdigest()
