"""A workspace with the evaluation corpus in it, built through the real code paths.

**Nothing here inserts a prompt with SQL.** ``register_account``,
``create_prompt`` and ``create_revision`` are the same functions the HTTP routes
call, so the rows under evaluation carry the same ``search_text`` the registry's
trigger maintains, the same canonical XML the converter produces, and the same
tenant context RLS enforces. A fixture that wrote its own rows would be
measuring a corpus the product cannot produce.

**The database is reusable on purpose.** Set ``PROPE_EVAL_DATABASE_URL`` to a
superuser URL and the harness upgrades and reuses it; leave it unset and it
starts a throwaway container. Reuse matters because indexing is the expensive
step — every re-provision from scratch is another few hundred LLM calls on
somebody's bill — and because comparing two rankers over two different corpora
would compare nothing.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from eval.retrieval.corpus import CorpusItem

PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: Same test-only role passwords the pytest rig uses (tests/conftest.py). The
#: migration bakes none (D-05, ADR-0032), so somebody has to set them.
ROLE_PASSWORDS = {
    "prope_migrate": "test-only-migrate",
    "prope_app": "test-only-app",
    "prope_report": "test-only-report",
}

EVAL_EMAIL = "eval@prope.local"
EVAL_PASSWORD = "eval-only-password-8127"
EVAL_DISPLAY_NAME = "Retrieval Eval"
NAMESPACE = "library"


@dataclass(slots=True)
class EvalWorkspace:
    sessionmaker: async_sessionmaker[AsyncSession]
    engine: AsyncEngine
    user_id: str
    workspace_id: str
    #: ``prompt_id`` keyed by corpus stem, and its inverse. Every metric in the
    #: run is computed in stem space; ids never leave this module's callers.
    prompt_id_by_stem: dict[str, str]
    stem_by_prompt_id: dict[str, str]
    version_id_by_stem: dict[str, str]


def _upgrade(superuser_url: str) -> None:
    """``alembic upgrade head``, and **it must not run on the caller's event loop**.

    ``alembic/env.py`` drives an async engine with its own ``asyncio.run``, which
    raises the moment there is already a loop running — so every caller here goes
    through :func:`upgrade_off_loop`. The pytest rig avoids this by upgrading in a
    synchronous fixture; a harness that is async from ``main()`` down cannot.
    """
    os.environ["PROPE_DATABASE_URL"] = superuser_url
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    command.upgrade(config, "head")


async def upgrade_off_loop(superuser_url: str) -> None:
    await asyncio.to_thread(_upgrade, superuser_url)


async def _set_role_passwords(superuser_url: str) -> None:
    from prope.db.engine import build_engine

    engine = build_engine(superuser_url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            for role, password in ROLE_PASSWORDS.items():
                await connection.execute(text(f"ALTER ROLE {role} WITH PASSWORD '{password}'"))
    finally:
        await engine.dispose()


def _app_url(superuser_url: str) -> str:
    """The same database, reached as ``prope_app`` — the role RLS actually binds."""
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(superuser_url)
    host = parts.hostname or "localhost"
    port = f":{parts.port}" if parts.port else ""
    database = parts.path
    return urlunsplit(
        ("postgresql+asyncpg", f"prope_app:{ROLE_PASSWORDS['prope_app']}@{host}{port}", database, "", "")
    )


@asynccontextmanager
async def database():
    """Yield a superuser URL for an upgraded database, starting a container if needed."""
    configured = os.environ.get("PROPE_EVAL_DATABASE_URL")
    if configured:
        await upgrade_off_loop(configured)
        await _set_role_passwords(configured)
        yield configured
        return

    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("pgvector/pgvector:0.8.6-pg17", driver="asyncpg") as container:
        url = container.get_connection_url()
        await upgrade_off_loop(url)
        await _set_role_passwords(url)
        yield url


async def open_workspace(superuser_url: str) -> EvalWorkspace:
    """The evaluation account, created once and reused on every later run."""
    from prope.access_control import commands
    from prope.access_control.sessions import sign_in
    from prope.db.engine import build_engine, build_sessionmaker
    from prope.session_auth import ManagementRefusal

    engine = build_engine(_app_url(superuser_url), poolclass=NullPool)
    sessionmaker = build_sessionmaker(engine)

    # Every write below appends to property-history, and `append` refuses to run
    # against a registry nobody installed. `prope.app`'s lifespan and
    # `worker.run_worker` each do this at startup; a harness that drives the
    # command layer directly is a third entrypoint and owes the same call.
    from prope.property_history.registry import install_registry, load_action_registry

    async with sessionmaker() as session:
        install_registry(await load_action_registry(session))

    try:
        account = await commands.register_account(
            sessionmaker,
            display_name=EVAL_DISPLAY_NAME,
            email=EVAL_EMAIL,
            password=EVAL_PASSWORD,
            now=datetime.now(UTC),
        )
        user_id, workspace_id = account.user_id, account.workspace_id
    except ManagementRefusal as refusal:
        if refusal.status_code != 409:
            raise
        result = await sign_in(
            sessionmaker,
            email=EVAL_EMAIL,
            password=EVAL_PASSWORD,
            source_address="eval-harness",
            user_agent="prope-eval",
        )
        if result.session is None:
            raise RuntimeError(f"eval account exists but will not authenticate ({result.metric_result})")
        user_id, workspace_id = result.session.user_id, result.session.workspace_id

    return EvalWorkspace(
        sessionmaker=sessionmaker,
        engine=engine,
        user_id=user_id,
        workspace_id=workspace_id,
        prompt_id_by_stem={},
        stem_by_prompt_id={},
        version_id_by_stem={},
    )


async def seed_prompts(workspace: EvalWorkspace, items: list[CorpusItem]) -> dict[str, int]:
    """Insert the corpus, skipping what is already there. Returns a small tally."""
    from prope.db.session import workspace_transaction
    from prope.prompt_registry import commands
    from prope.prompt_registry.domain import RevisionDraft
    from prope.prompt_registry.repository import load_latest_revision
    from prope.session_auth import ManagementRefusal

    tally = {"created": 0, "existing": 0}
    now = datetime.now(UTC)

    for item in items:
        try:
            async with workspace_transaction(workspace.sessionmaker, workspace.workspace_id) as db:
                prompt = await commands.create_prompt(
                    db,
                    workspace_id=workspace.workspace_id,
                    actor_id=workspace.user_id,
                    namespace=NAMESPACE,
                    name=item.name,
                    title=item.title,
                    purpose=item.purpose,
                    owner_id=workspace.user_id,
                    access_level="workspace",
                    tags=["eval"],
                    now=now,
                )
                revision = await commands.create_revision(
                    db,
                    workspace_id=workspace.workspace_id,
                    actor_id=workspace.user_id,
                    prompt_id=prompt.id,
                    draft=RevisionDraft(
                        body=item.body,
                        change_summary="Evaluation corpus import",
                        original_body=item.raw[:32768],
                        original_format="txt",
                        original_filename=item.source_file,
                        conversion_model="deterministic-seed-v1",
                        conversion_schema_version="2",
                        parameters={},
                    ),
                    now=now,
                )
            workspace.prompt_id_by_stem[item.stem] = prompt.id
            workspace.version_id_by_stem[item.stem] = revision.version_id
            tally["created"] += 1
        except ManagementRefusal as refusal:
            if refusal.status_code != 409:
                raise
            # Already seeded by an earlier run — find it and carry on.
            async with workspace_transaction(workspace.sessionmaker, workspace.workspace_id) as db:
                found = await db.execute(
                    text(
                        "SELECT id FROM registry.prompt_property "
                        "WHERE workspace_id = :ws AND namespace = :ns AND name = :name"
                    ),
                    {"ws": workspace.workspace_id, "ns": NAMESPACE, "name": item.name},
                )
                prompt_id = found.scalar_one_or_none()
                if prompt_id is None:
                    raise
                latest = await load_latest_revision(db, prompt_id)
            workspace.prompt_id_by_stem[item.stem] = prompt_id
            if latest is not None:
                workspace.version_id_by_stem[item.stem] = latest.version_id
            tally["existing"] += 1

    workspace.stem_by_prompt_id = {
        prompt_id: stem for stem, prompt_id in workspace.prompt_id_by_stem.items()
    }
    return tally


async def close(workspace: EvalWorkspace) -> None:
    await workspace.engine.dispose()


def run(coroutine):
    """``asyncio.run`` with the Windows selector policy the asyncpg driver wants."""
    return asyncio.run(coroutine)
