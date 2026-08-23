"""Shared factories for the ``registry`` schema's tests.

Same placement argument as ``tests/access_control/`` and
``tests/provider_access/``: a per-subject package named after the module,
created when its subject arrived.

Everything here seeds through ``migrate_engine`` — the owner — so the rows a test
needs exist independently of the privileges and policies under test. A test whose
subject is a command writes through the command.

**Nothing here writes ``search_text``.** The two triggers do, and a factory that
set the column by hand would let every search test pass against a document the
migration never built — which is the one failure AC-8 exists to catch.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.access_control.bootstrap import authenticate_session
from prope.errors import install_error_envelope
from prope.prompt_registry.api import router as prompt_registry_router
from prope.session_auth import install_session_authenticator, reset_session_authenticator
from tests.access_control import ADMIN_ID
from tests.unit import WORKSPACE_A, day

__all__ = [
    "ADMIN_ID",
    "NAME",
    "NAMESPACE",
    "PROMPT_ID",
    "VERSION_ID",
    "WORKSPACE_A",
    "approve",
    "day",
    "registry_api",
    "release",
    "seed_prompt",
    "seed_released_prompts",
    "seed_revision",
]

PROMPT_ID = "prm_01J0000000000000000PROMPT"

VERSION_ID = "rev_01J000000000000000000REV1"

NAMESPACE = "support"

NAME = "refund-classifier"

#: The four Usage Profile axes at their sentinel (ADR-0067, migration 0030).
#:
#: ``undeclared`` is a real value and not NULL — the whole point of A-163 is that
#: *nobody has said* is a state the card can badge, and a NULL would have made it
#: indistinguishable from *this axis does not apply*. Seeded explicitly rather
#: than left to the column default so a test that needs a declaration overrides
#: one key instead of discovering the columns exist.
UNDECLARED_PROFILE: dict[str, str] = {
    "audience": "undeclared",
    "untrusted_input": "undeclared",
    "acts": "undeclared",
    "sensitivity": "undeclared",
}

INSERT_PROMPT_PROPERTY = text(
    """
    INSERT INTO registry.prompt_property (
        id, workspace_id, namespace, name, title, purpose, owner_id,
        access_level, status, tags, created_at, updated_at,
        audience, untrusted_input, acts, sensitivity
    ) VALUES (
        :id, :workspace_id, :namespace, :name, :title, :purpose, :owner_id,
        :access_level, :status, CAST(:tags AS text[]), :created_at, :created_at,
        :audience, :untrusted_input, :acts, :sensitivity
    )
    """
)

INSERT_REVISION = text(
    """
    INSERT INTO registry.revision (
        version_id, workspace_id, prompt_id, revision_number, body,
        provider_config_id, upstream_model, parameters, fallback_answer,
        change_summary, author_id, status, created_at,
        audience, untrusted_input, acts, sensitivity
    ) VALUES (
        :version_id, :workspace_id, :prompt_id, :revision_number, :body,
        :provider_config_id, :upstream_model, CAST(:parameters AS jsonb),
        :fallback_answer, :change_summary, :author_id, :status, :created_at,
        :audience, :untrusted_input, :acts, :sensitivity
    )
    """
)

APPROVE_REVISION = text(
    "UPDATE registry.revision SET status = 'Approved' WHERE version_id = :version_id"
)

RELEASE_REVISION = text(
    """
    UPDATE registry.prompt_property
       SET released_version_id = :version_id, released_at = :now
     WHERE id = :prompt_id
    """
)


async def _insert(migrate_engine: AsyncEngine, statement, values: dict[str, Any]) -> None:  # noqa: ANN001
    async with migrate_engine.begin() as connection:
        await connection.execute(statement, values)


@contextmanager
def registry_api(
    app_sessionmaker: async_sessionmaker[AsyncSession],
) -> Iterator[FastAPI]:
    """This module's router on a bare application, with the real session boundary.

    **The real ``authenticate_session``, never an override.** FastAPI's
    ``dependency_overrides`` would be a test seam that bypasses INT-005, and the
    refusal shapes these tests assert — 401 for no session, 404 for a prompt the
    actor may not see — are only meaningful if the session came from a live row.

    A bare ``FastAPI`` rather than ``prope.app.app`` because the lifespan there
    builds an engine from an environment and opens a broker connection; the
    route table is asserted against the assembled application in
    ``tests/architecture``, and what is under test here is behaviour.
    """
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    install_error_envelope(application)
    application.include_router(prompt_registry_router)
    application.state.sessionmaker = app_sessionmaker
    install_session_authenticator(lambda cookie: authenticate_session(app_sessionmaker, cookie))
    try:
        yield application
    finally:
        reset_session_authenticator()


async def seed_prompt(
    migrate_engine: AsyncEngine,
    prompt_id: str = PROMPT_ID,
    workspace_id: str = WORKSPACE_A,
    **overrides: Any,
) -> str:
    """One prompt property, private by default because BR-01 says so."""
    values: dict[str, Any] = {
        "id": prompt_id,
        "workspace_id": workspace_id,
        "namespace": NAMESPACE,
        "name": NAME,
        "title": "Refund classifier",
        "purpose": "Decides whether a refund request is in policy",
        "owner_id": ADMIN_ID,
        "access_level": "private",
        "status": "active",
        "tags": ["support"],
        "created_at": day(1),
        **UNDECLARED_PROFILE,
    }
    values.update(overrides)
    await _insert(migrate_engine, INSERT_PROMPT_PROPERTY, values)
    return str(values["id"])


async def seed_revision(
    migrate_engine: AsyncEngine,
    version_id: str = VERSION_ID,
    prompt_id: str = PROMPT_ID,
    revision_number: int = 1,
    workspace_id: str = WORKSPACE_A,
    **overrides: Any,
) -> str:
    """One revision. ``Draft`` unless a test says otherwise, like the write path."""
    values: dict[str, Any] = {
        "version_id": version_id,
        "workspace_id": workspace_id,
        "prompt_id": prompt_id,
        "revision_number": revision_number,
        "body": "You are a helpful assistant.",
        "provider_config_id": None,
        "upstream_model": None,
        "parameters": "{}",
        "fallback_answer": None,
        "change_summary": "first draft",
        "author_id": ADMIN_ID,
        "status": "Draft",
        "created_at": day(1),
        **UNDECLARED_PROFILE,
    }
    values.update(overrides)
    await _insert(migrate_engine, INSERT_REVISION, values)
    return str(values["version_id"])


async def seed_released_prompts(
    migrate_engine: AsyncEngine,
    count: int,
    namespace: str = "filler",
    workspace_id: str = WORKSPACE_A,
) -> None:
    """``count`` approved-and-released prompts, in **one** transaction.

    The per-row factories above open a transaction each, which is right for a
    test that seeds three rows and wrong for one that seeds a few hundred:
    ``migrate_engine`` uses ``NullPool``, so every call also opens a connection
    and pays a SCRAM-SHA-256 handshake — 4,096 pure-Python HMAC rounds. Seeding
    200 neighbours through the row-at-a-time path took **five minutes** of a
    six-minute load run, all of it authentication.

    Four ``executemany`` batches instead, in the order the constraints require:
    every prompt, every revision, the approvals, then the pointers. BR-03's
    composite foreign key means a pointer cannot be set before its revision is
    ``Approved``, which is why the last two are separate statements rather than
    one insert with the column filled in.
    """
    prompts = [
        {
            "id": f"prm_01J00000000000000NB{index:05d}",
            "workspace_id": workspace_id,
            "namespace": namespace,
            "name": f"prompt-{index}",
            "title": f"Filler prompt {index}",
            "purpose": "A neighbour, so the index has something to discriminate against",
            "owner_id": ADMIN_ID,
            "access_level": "workspace",
            "status": "active",
            "tags": ["filler"],
            "created_at": day(1),
        }
        for index in range(count)
    ]
    revisions = [
        {
            "version_id": f"rev_01J00000000000000NB{index:05d}",
            "workspace_id": workspace_id,
            "prompt_id": prompt["id"],
            "revision_number": 1,
            "body": "You are a helpful assistant.",
            "provider_config_id": None,
            "upstream_model": None,
            "parameters": "{}",
            "fallback_answer": None,
            "change_summary": "first draft",
            "author_id": ADMIN_ID,
            "status": "Draft",
            "created_at": day(1),
        }
        for index, prompt in enumerate(prompts)
    ]

    async with migrate_engine.begin() as connection:
        await connection.execute(INSERT_PROMPT_PROPERTY, prompts)
        await connection.execute(INSERT_REVISION, revisions)
        await connection.execute(
            APPROVE_REVISION, [{"version_id": row["version_id"]} for row in revisions]
        )
        await connection.execute(
            RELEASE_REVISION,
            [
                {"prompt_id": row["prompt_id"], "version_id": row["version_id"], "now": day(2)}
                for row in revisions
            ],
        )


async def approve(migrate_engine: AsyncEngine, version_id: str = VERSION_ID) -> None:
    """Move a revision to ``Approved`` as the owner.

    Through the OWNER rather than through INT-012, deliberately: a test whose
    subject is the released-pointer constraint should not depend on the command
    that would normally precede it, or a failure in one reads as a failure in the
    other.
    """
    await _insert(migrate_engine, APPROVE_REVISION, {"version_id": version_id})


async def release(
    migrate_engine: AsyncEngine, prompt_id: str = PROMPT_ID, version_id: str = VERSION_ID
) -> None:
    """Point the released pointer, as the owner. The constraint still applies."""
    await _insert(
        migrate_engine,
        RELEASE_REVISION,
        {"prompt_id": prompt_id, "version_id": version_id, "now": day(2)},
    )
