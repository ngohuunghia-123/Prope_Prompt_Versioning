"""Queue indexing for prompts a workspace already holds but cannot search.

``seed_prompts.py`` caps indexing at ``--index 40`` on purpose — every prompt
costs one LLM extraction and one embedding, and a few hundred of them is an hour
of somebody's compute and two calls each on their bill. That cap is the right
default for a seed run. It is also a trap afterwards, because **the seed script
cannot undo it**: re-running skips every prompt that already exists
(``skipped:exists``) and returns no ids, so ``_request_indexing`` receives an
empty list and queues nothing. The remaining prompts stay unsearchable and the
only way back is this script or the per-prompt button.

The state it fixes is not visible anywhere. A workspace with 370 prompts and 10
index rows answers *"nothing resembles this"* to every duplicate check, which
reads as *there is no duplicate* and means *we looked at 2.7% of your library*.
That is the recall ceiling ``prompt-similarity.draft.md`` §2.0 calls "a
prerequisite metric, not a dashboard nicety".

**It queues; it does not index.** Each row becomes a job record plus a broker
message, exactly as ``POST /prompts/{id}/revisions`` does, and the search worker
drains them in the background at its own pace. Interrupting this script loses
nothing: an unqueued prompt is in the same state it was already in, and a prompt
queued twice is upserted on ``(prompt_id, role)`` rather than duplicated.

Run it inside the compose network, as the ``prope_app`` role the ``app`` service
already uses::

    docker compose run --rm -v "$(pwd)/seed:/work/seed" -w /work app \\
      python seed/backfill_index.py --email owner@acme.com --password 'secret'

Credentials may also come from ``SEED_EMAIL`` / ``SEED_PASSWORD`` to keep the
password out of the process list.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
_SRC = _HERE.parent / "src"
if _SRC.is_dir():
    sys.path.insert(0, str(_SRC))

from seed_prompts import _resolve_workspace  # noqa: E402
from sqlalchemy import text  # noqa: E402

from prope.db.engine import Settings, build_engine, build_sessionmaker  # noqa: E402
from prope.db.session import workspace_transaction  # noqa: E402
from prope.property_history.registry import (  # noqa: E402
    install_registry,
    load_action_registry,
)

#: Prompts with a revision and no `latest` index row, newest revision per prompt.
#:
#: `role = 'latest'` and not simply "any row": migration 0014 split the index
#: into `latest` and `released`, and a prompt indexed only under `released` is
#: still missing from the duplicate check, which ranks `latest`. RLS scopes this
#: to the workspace — there is no `workspace_id` predicate here because a missing
#: filter must return zero rows rather than someone else's (ADR-0035).
UNINDEXED = text("""
    SELECT p.id AS prompt_id,
           r.version_id AS version_id
      FROM registry.prompt_property p
      JOIN LATERAL (
             SELECT version_id
               FROM registry.revision
              WHERE prompt_id = p.id
              ORDER BY revision_number DESC
              LIMIT 1
           ) r ON TRUE
     WHERE NOT EXISTS (
             SELECT 1
               FROM search.prompt_search_index i
              WHERE i.prompt_id = p.id
                AND i.role = 'latest'
           )
     ORDER BY p.created_at, p.id
""")

#: Indexed, but carrying no declared output contract.
#:
#: Its own mode because a NULL here is ambiguous by design — migration 0035 says
#: NULL means *never extracted*, which is deliberately not the same as a
#: descriptor that exists and reads `unspecified`. So this re-queues rows that
#: may simply predate the column, and rows whose extraction failed. The second
#: case was not hypothetical: `descriptor_of` read the model's `keys` field with
#: `getattr`, which on a `dspy.Prediction` returns the bound mapping method, and
#: every extraction raised a `TypeError` that `extract_output_descriptor`
#: swallowed by contract. Re-running is how those rows get a real descriptor.
#:
#: **It does not converge, and that is not a bug in the query.** A prompt whose
#: body declares no output block leaves this column NULL no matter how often it
#: is re-queued — `extract_output_descriptor` returns `None` without calling
#: anything when `declared_output_text` finds nothing to read. On the 370-prompt
#: workspace a full pass left 300 of 413 index rows with a descriptor and 113
#: still NULL, and every subsequent run will pick those same 113 up again. So
#: use `--limit` and read the count as *"rows that may need one"*, not as a
#: backlog that empties.
NO_DESCRIPTOR = text("""
    SELECT i.prompt_id AS prompt_id,
           i.version_id AS version_id
      FROM search.prompt_search_index i
     WHERE i.role = 'latest'
       AND i.output_descriptor IS NULL
     ORDER BY i.indexed_at, i.prompt_id
""")


async def run(args: argparse.Namespace) -> None:
    email = args.email or os.environ.get("SEED_EMAIL")
    password = args.password or os.environ.get("SEED_PASSWORD")
    if not email or not password:
        sys.exit("provide --email/--password (or SEED_EMAIL/SEED_PASSWORD)")

    settings = Settings()
    engine = build_engine(settings.database_url)
    sessionmaker = build_sessionmaker(engine)

    try:
        # ADR-0038, same as the seed script: the history registry must be
        # installed in this process before anything reaches the command layer.
        async with sessionmaker() as session:
            install_registry(await load_action_registry(session))

        user_id, workspace_id = await _resolve_workspace(
            sessionmaker, email=email, password=password
        )
        print(f"authenticated as {email} -> workspace {workspace_id}")

        query = NO_DESCRIPTOR if args.missing_descriptor else UNINDEXED
        subject = (
            "indexed rows carry no output descriptor"
            if args.missing_descriptor
            else "prompts have no `latest` index row"
        )
        async with workspace_transaction(sessionmaker, workspace_id) as db:
            rows = (await db.execute(query)).mappings().all()

        pending = [(row["prompt_id"], row["version_id"]) for row in rows]
        if not pending:
            print(f"nothing matches: no {subject}")
            return

        batch = pending if args.limit < 0 else pending[: args.limit]
        print(
            f"{len(pending)} {subject}; "
            f"queueing {len(batch)}. Each costs one extraction and one embedding."
        )
        if args.dry_run:
            print("--dry-run: nothing queued")
            return

        import aio_pika

        from prope.prompt_search.seams import declare_search_queue, enqueue_index_job

        connection = await aio_pika.connect_robust(settings.broker_url)
        try:
            channel = await connection.channel()
            await declare_search_queue(channel)
            queued = 0
            for prompt_id, version_id in batch:
                job_id = await enqueue_index_job(
                    sessionmaker,
                    channel,
                    prompt_id=prompt_id,
                    version_id=version_id,
                    workspace_id=workspace_id,
                    created_by=user_id,
                    role="latest",
                )
                queued += 1 if job_id else 0
            print(f"queued {queued}/{len(batch)}; the worker drains them in the background")
            if queued < len(batch):
                # `enqueue_index_job` swallows every failure by contract, so a
                # shortfall is the only signal that some did not go out.
                print(f"  {len(batch) - queued} were not queued — see the app log for the reason")
        finally:
            await connection.close()
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", help="account to authenticate as (or SEED_EMAIL)")
    parser.add_argument("--password", help="that account's password (or SEED_PASSWORD)")
    parser.add_argument(
        "--limit",
        type=int,
        default=-1,
        help="queue at most N prompts (default: -1, meaning all of them)",
    )
    parser.add_argument(
        "--missing-descriptor",
        action="store_true",
        help=(
            "re-queue prompts that ARE indexed but whose row carries no declared "
            "output contract, rather than prompts that are not indexed at all"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report how many prompts match and queue nothing",
    )
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
