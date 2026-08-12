"""A-119's *one indexed read*, asserted against the planner rather than the DDL.

An index existing and an index being used are different facts, and only the
second one keeps a screen fast on a table that never shrinks (A-121). Each of
the three read statements is run through ``EXPLAIN (FORMAT JSON)`` with real
parameters, and the assertion is that the index that statement was written for
appears somewhere in the plan.

**The corpus size is an empirical threshold, not a specification.** The lock's
performance condition names *"a prompt with 200 events in a workspace with
50,000 events"*, which is too slow to seed per test; ~3,000 rows over ~60
prompts, ~60 targets and ~30 actors plus an ``ANALYZE`` is the smallest corpus
that reliably tips the planner here. If a future PostgreSQL still chooses a
sequential scan, **raise the corpus** — do not set ``enable_seqscan = off``,
which would prove the index *can* be used rather than that it *is*.

The assertion is the index NAME anywhere in the plan, deliberately not the node
type: refusing an ``Index Only Scan`` or a ``Bitmap Index Scan`` would make this
file fail on a planner that got smarter, which is not a regression.
"""

import json
from typing import Any

from sqlalchemy import text

from prope.db.session import workspace_transaction
from prope.property_history.domain import ActorScope, PromptScope, TargetScope
from prope.property_history.read import READ_BY_ACTOR, READ_BY_PROMPT, READ_BY_TARGET, _statement_for
from tests.property_history import WORKSPACE_A, day, history_event_values, seed_history_events

CORPUS_ROWS = 3_000
PROMPTS = 60
TARGETS = 60
ACTORS = 30

PROMPT_INDEX = "ix_history_event_workspace_id_scope_prompt_id_seq"
TARGET_INDEX = "ix_history_event_workspace_id_target_type_target_id_seq"
ACTOR_INDEX = "ix_history_event_workspace_id_actor_id_seq"

ANALYZE = text("ANALYZE history.history_event")

#: The vacuity control. Run as the owner so no policy predicate is added and the
#: plan is unambiguously a sequential scan over the whole table.
NO_PREDICATE = "SELECT seq, id FROM history.history_event"


def scope_prompt(n: int) -> str:
    return f"prm_01J{n:022d}"


def target(n: int) -> str:
    return f"rev_01J{n:022d}"


def actor(n: int) -> str:
    return f"usr_01J{n:022d}"


async def seed_corpus(migrate_engine) -> None:
    await seed_history_events(
        migrate_engine,
        [
            history_event_values(
                id=f"hev_01J{n:022d}",
                scope_prompt_id=scope_prompt(n % PROMPTS),
                target_id=target(n % TARGETS),
                actor_id=actor(n % ACTORS),
                occurred_at=day(5),
            )
            for n in range(CORPUS_ROWS)
        ],
    )
    async with migrate_engine.begin() as connection:
        # Kept although a probe showed the three tests pass without it: without
        # ANALYZE the plan depends on whether autovacuum has visited yet, which
        # is a race this file should not be running.
        await connection.execute(ANALYZE)


def _index_names(node: dict[str, Any]) -> set[str]:
    names = {node["Index Name"]} if "Index Name" in node else set()
    for child in node.get("Plans", []):
        names |= _index_names(child)
    return names


async def explained_indexes(executor, statement: str, parameters: dict[str, Any]) -> set[str]:
    plan = (await executor.execute(text("EXPLAIN (FORMAT JSON) " + statement), parameters)).scalar_one()
    if isinstance(plan, str):
        plan = json.loads(plan)
    return _index_names(plan[0]["Plan"])


async def indexes_for(app_sessionmaker, scope) -> set[str]:
    statement, parameters = _statement_for(scope)
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        return await explained_indexes(
            session, statement.text, {**parameters, "before_seq": None, "limit": 50}
        )


async def test_the_prompt_scope_is_read_on_its_own_index(app_sessionmaker, migrate_engine):
    await seed_corpus(migrate_engine)
    found = await indexes_for(app_sessionmaker, PromptScope(WORKSPACE_A, scope_prompt(7)))
    assert PROMPT_INDEX in found, found


async def test_the_target_scope_is_read_on_its_own_index(app_sessionmaker, migrate_engine):
    await seed_corpus(migrate_engine)
    found = await indexes_for(app_sessionmaker, TargetScope(WORKSPACE_A, "revision", target(7)))
    assert TARGET_INDEX in found, found


async def test_the_actor_scope_is_read_on_its_own_index(app_sessionmaker, migrate_engine):
    await seed_corpus(migrate_engine)
    found = await indexes_for(app_sessionmaker, ActorScope(WORKSPACE_A, actor(7)))
    assert ACTOR_INDEX in found, found


async def test_the_three_statements_are_the_ones_the_dispatch_returns():
    """Guards the three tests above against explaining a statement nobody runs."""
    assert _statement_for(PromptScope(WORKSPACE_A, "p"))[0] is READ_BY_PROMPT
    assert _statement_for(TargetScope(WORKSPACE_A, "revision", "t"))[0] is READ_BY_TARGET
    assert _statement_for(ActorScope(WORKSPACE_A, "a"))[0] is READ_BY_ACTOR


async def test_a_statement_with_no_predicate_names_no_index(migrate_engine):
    """The vacuity guard: the walker finds index names, not any string it looks for.

    Without this, a plan walker that returned every key in the JSON would make
    the three tests above pass against a sequential scan.
    """
    await seed_corpus(migrate_engine)

    async with migrate_engine.begin() as connection:
        found = await explained_indexes(connection, NO_PREDICATE, {})

    assert found == set(), found
