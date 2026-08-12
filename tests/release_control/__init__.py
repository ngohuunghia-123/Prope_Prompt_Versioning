"""Shared factories for the ``release`` schema's tests.

Same placement argument as ``tests/prompt_registry/`` and ``tests/evaluation/``:
a per-subject package named after the module, created when its subject arrived.

**The role matrix is the whole of the permission story here**, and these
factories make that visible. Migration 0006 seeds ``revision.submit`` on Owner,
``revision.approve`` on Reviewer, and ``release.create`` /
``release.break_glass`` / ``release.withdraw`` on Admin — five permissions across
three roles, which is NFR-01's edit / review / release separation expressed as
data. A test that needs two of them binds two roles to one person, which is
exactly what a workspace would do and exactly what ADR-0010 refuses to treat as
an error.

**The evaluation seam is stubbed rather than driven.** Release-control PULLS
``get_review_summary`` and evaluation never calls back (A-042), so a test whose
subject is a decision does not need a live eval run — it needs a summary that
says a specific thing, including the thing it says when the pull raises (A-070).
:func:`stub_summary` is that seam and nothing else.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.access_control.bootstrap import authenticate_session
from prope.errors import install_error_envelope
from prope.evaluation.domain import CostDelta, ReviewSummary, RunStatus, SuiteSummary
from prope.release_control import review
from prope.release_control.api import router as release_control_router
from prope.session_auth import install_session_authenticator, reset_session_authenticator
from tests.access_control import (
    ADMIN_ID,
    MEMBER_ID,
    seed_member,
    seed_role,
    seed_session,
    seed_user,
    seed_workspace,
)
from tests.prompt_registry import PROMPT_ID, seed_prompt, seed_revision
from tests.unit import WORKSPACE_A, day

__all__ = [
    "ADMIN_ID",
    "APPROVER_ID",
    "MEMBER_ID",
    "PROMPT_ID",
    "SUITE_ID",
    "WORKSPACE_A",
    "day",
    "failing_summary",
    "passing_summary",
    "read_approvals",
    "read_releases",
    "read_review_tasks",
    "release_api",
    "releases_without_approval",
    "seed_actor",
    "seed_prompt",
    "seed_revision",
    "stub_summary",
    "unavailable_summary",
]

#: A second person, so "the author approved their own revision" and "somebody
#: else approved it" are two different actors rather than one flag.
APPROVER_ID = "usr_01J000000000000000APPROVE"

SUITE_ID = "evs_01J00000000000000SAFETY01"

RUN_ID = "evr_01J00000000000000SAFETY01"

BASELINE_RUN_ID = "evr_01J0000000000000BASELINE"

READ_APPROVALS = text(
    """
    SELECT id, prompt_id, version_id, decision, reviewer_id, comment,
           acknowledgement_reason, evidence_digest, self_approved, decided_at
    FROM   release.approval
    ORDER  BY decided_at, id
    """
)

READ_RELEASES = text(
    """
    SELECT id, prompt_id, version_id, kind, previous_version_id, approval_id,
           break_glass, reason, released_by, released_at
    FROM   release.release
    ORDER  BY released_at, id
    """
)

READ_REVIEW_TASKS = text(
    """
    SELECT id, prompt_id, version_id, kind, assigned_role, due_at, status,
           created_from_release_id, created_at, closed_by, closed_at, closed_note
    FROM   release.review_task
    ORDER  BY created_at, id
    """
)

#: 00_context.md#success, as SQL. It must return zero rows, and the table shape
#: is what makes it one scan rather than a join across two modules.
RELEASES_WITHOUT_APPROVAL = text(
    """
    SELECT id
    FROM   release.release
    WHERE  version_id IS NOT NULL AND approval_id IS NULL AND break_glass = false
    """
)


@contextmanager
def release_api(
    app_sessionmaker: async_sessionmaker[AsyncSession],
) -> Iterator[FastAPI]:
    """This module's router on a bare application, with the real session boundary.

    The real ``authenticate_session``, never a ``dependency_overrides`` bypass:
    the refusal shapes these tests assert — 404 for a prompt the actor cannot
    see, 403 naming the missing permission when they can — are only meaningful
    if the session came from a live row.
    """
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    install_error_envelope(application)
    application.include_router(release_control_router)
    application.state.sessionmaker = app_sessionmaker
    install_session_authenticator(lambda cookie: authenticate_session(app_sessionmaker, cookie))
    try:
        yield application
    finally:
        reset_session_authenticator()


async def seed_actor(
    migrate_engine: AsyncEngine,
    session_id: str,
    *,
    roles: tuple[str, ...],
    user_id: str = ADMIN_ID,
    workspace_id: str = WORKSPACE_A,
    seed_the_workspace: bool = True,
) -> str:
    """One person, their roles, and a live session cookie.

    ``roles`` is a tuple rather than a single string because five permissions
    live on three roles and half of this module's tests are about an actor who
    holds one and not the other.
    """
    if seed_the_workspace:
        await seed_workspace(migrate_engine, workspace_id)
    await seed_user(migrate_engine, user_id)
    await seed_member(migrate_engine, workspace_id, user_id)
    for role in roles:
        await seed_role(migrate_engine, role, workspace_id, user_id)
    return await seed_session(migrate_engine, session_id, workspace_id, user_id)


def _suite(
    *, pass_count: int, fail_count: int, error_count: int, name: str = "safety"
) -> SuiteSummary:
    return SuiteSummary(
        suite_id=SUITE_ID,
        suite_name=name,
        suite_version=1,
        run_id=RUN_ID,
        status=RunStatus.COMPLETED,
        pass_count=pass_count,
        fail_count=fail_count,
        error_count=error_count,
        case_count=pass_count + fail_count + error_count,
        baseline_run_id=BASELINE_RUN_ID,
        baseline_ran_at=day(3),
        baseline_reused=True,
        cost_delta=CostDelta(
            input_tokens=100, output_tokens=50, cost=None, currency="USD", ratio=None
        ),
        withheld_reason=None,
        cost_warning=False,
    )


def passing_summary(prompt_id: str, version_id: str) -> ReviewSummary:
    return ReviewSummary(
        prompt_id=prompt_id,
        version_id=version_id,
        suites=(_suite(pass_count=20, fail_count=0, error_count=0),),
        requires_acknowledgement=False,
    )


def failing_summary(
    prompt_id: str, version_id: str, *, fail_count: int = 2
) -> ReviewSummary:
    return ReviewSummary(
        prompt_id=prompt_id,
        version_id=version_id,
        suites=(_suite(pass_count=18, fail_count=fail_count, error_count=0),),
        requires_acknowledgement=True,
    )


@contextmanager
def stub_summary(
    monkeypatch: pytest.MonkeyPatch, answer: ReviewSummary | Exception | None
) -> Iterator[list[tuple[str, str]]]:
    """Replace INT-017 for the duration of a test, and record what was asked.

    ``answer`` is a summary to return, or an exception to raise — the second is
    A-070's whole case, and it is a stub rather than a broken database because
    the property under test is *what this module does when evaluation is
    unavailable*, not how evaluation fails.

    Patched on ``prope.release_control.review``, which is where the name is
    bound. Patching ``prope.evaluation.summary`` would leave this module holding
    the original reference and the test would silently exercise nothing.
    """
    asked: list[tuple[str, str]] = []

    async def _stub(_db: AsyncSession, prompt_id: str, version_id: str) -> ReviewSummary:
        asked.append((prompt_id, version_id))
        if isinstance(answer, Exception):
            raise answer
        assert answer is not None
        return answer

    monkeypatch.setattr(review, "get_review_summary", _stub)
    yield asked


def unavailable_summary() -> Exception:
    return RuntimeError("evaluation is unavailable")


async def _rows(migrate_engine: AsyncEngine, statement) -> list[dict[str, Any]]:  # noqa: ANN001
    async with migrate_engine.begin() as connection:
        return [dict(row) for row in (await connection.execute(statement)).mappings().all()]


async def read_approvals(migrate_engine: AsyncEngine) -> list[dict[str, Any]]:
    return await _rows(migrate_engine, READ_APPROVALS)


async def read_releases(migrate_engine: AsyncEngine) -> list[dict[str, Any]]:
    return await _rows(migrate_engine, READ_RELEASES)


async def read_review_tasks(migrate_engine: AsyncEngine) -> list[dict[str, Any]]:
    return await _rows(migrate_engine, READ_REVIEW_TASKS)


async def releases_without_approval(migrate_engine: AsyncEngine) -> list[dict[str, Any]]:
    return await _rows(migrate_engine, RELEASES_WITHOUT_APPROVAL)


def utc_now() -> datetime:
    return datetime.now(UTC)
