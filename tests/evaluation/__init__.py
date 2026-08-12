"""Shared factories for the ``evaluation`` schema's tests.

Same placement argument as ``tests/prompt_registry/`` and
``tests/access_control/``: a per-subject package named after the module, created
when its subject arrived.

Everything that seeds rows writes through ``migrate_engine`` — the owner — so the
rows a test needs exist independently of the privileges and policies under test.
A test whose subject is a command writes through the command.

**The dispatcher stub is injected at ``execute_run``'s seam, not at httpx.**
``tests/provider_access/_stub.py`` sits one layer below the transport because
what it asserts is the composed HTTP request; nothing here asserts anything about
HTTP. What these tests assert is the *executor's* behaviour given a dispatch that
succeeded, failed, or returned the wrong shape — so the stub stands where
``execute_run`` already accepts one, and every case below reads as the outcome it
is named for rather than as a JSON body two layers away.
"""

import asyncio
import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.access_control.bootstrap import authenticate_session
from prope.call_ledger.seams import CeilingDecision, RunTotals
from prope.errors import install_error_envelope
from prope.evaluation.api import router as evaluation_router
from prope.provider_access.domain import (
    DispatchError,
    DispatchResult,
    ErrorClass,
    Origin,
    Usage,
)
from prope.session_auth import install_session_authenticator, reset_session_authenticator
from tests.access_control import (
    ADMIN_ID,
    seed_member,
    seed_role,
    seed_session,
    seed_user,
    seed_workspace,
)
from tests.prompt_registry import PROMPT_ID, VERSION_ID, seed_revision
from tests.provider_access import CONFIG_ID, seed_provider_config
from tests.unit import WORKSPACE_A, day

__all__ = [
    "ADMIN_ID",
    "CASE_ID",
    "PROMPT_ID",
    "PROVIDER_CONFIG_ID",
    "RUN_ID",
    "SUITE_ID",
    "UPSTREAM_MODEL",
    "VERSION_ID",
    "WORKSPACE_A",
    "StubDispatcher",
    "allow_ceiling",
    "completion",
    "day",
    "evaluation_api",
    "frozen_clock",
    "no_pricing",
    "priced_totaller",
    "refuse_ceiling",
    "seed_bound_revision",
    "seed_case",
    "seed_case_result",
    "seed_owner",
    "seed_run",
    "seed_suite",
    "totaller_by_run",
    "totals",
    "transport_error",
]

SUITE_ID = "evs_01J000000000000000SUITE1"

CASE_ID = "evc_01J0000000000000000CASE1"

RUN_ID = "evr_01J00000000000000000RUN1"

#: ``registry.revision`` carries a real foreign key to ``provider.provider_config``,
#: so a revision that names a binding needs the row to exist. Reusing
#: ``tests.provider_access``'s id rather than minting one keeps a single provider
#: config in the suite and makes the FK a fact rather than a surprise.
PROVIDER_CONFIG_ID = CONFIG_ID

UPSTREAM_MODEL = "gpt-4o-mini"

INSERT_SUITE = text(
    """
    INSERT INTO evaluation.eval_suite (
        id, workspace_id, prompt_id, name, suite_version, output_modality,
        case_count, created_by, created_at
    ) VALUES (
        :id, :workspace_id, :prompt_id, :name, :suite_version, :output_modality,
        :case_count, :created_by, :created_at
    )
    """
)

INSERT_CASE = text(
    """
    INSERT INTO evaluation.eval_case (
        id, workspace_id, suite_id, ordinal, name, input_messages,
        input_variables, assertions, created_at
    ) VALUES (
        :id, :workspace_id, :suite_id, :ordinal, :name,
        CAST(:input_messages AS jsonb), CAST(:input_variables AS jsonb),
        CAST(:assertions AS jsonb), :created_at
    )
    """
)

INSERT_RUN = text(
    """
    INSERT INTO evaluation.eval_run (
        id, workspace_id, prompt_id, version_id, suite_id, role, status,
        refused_reason, started_at, finished_at, pass_count, fail_count,
        error_count, input_tokens, output_tokens, cost_amount, cost_currency,
        priced_at, started_by
    ) VALUES (
        :id, :workspace_id, :prompt_id, :version_id, :suite_id, :role, :status,
        :refused_reason, :started_at, :finished_at, :pass_count, :fail_count,
        :error_count, :input_tokens, :output_tokens, :cost_amount, :cost_currency,
        :priced_at, :started_by
    )
    """
)

INSERT_CASE_RESULT = text(
    """
    INSERT INTO evaluation.case_result (
        id, workspace_id, run_id, case_id, outcome, assertion_results,
        output_content, latency_ms, input_tokens, output_tokens, error_code,
        attempt_count, created_at
    ) VALUES (
        :id, :workspace_id, :run_id, :case_id, :outcome,
        CAST(:assertion_results AS jsonb), :output_content, :latency_ms,
        :input_tokens, :output_tokens, :error_code, :attempt_count, :created_at
    )
    """
)


async def _insert(migrate_engine: AsyncEngine, statement, values: dict[str, Any]) -> None:  # noqa: ANN001
    async with migrate_engine.begin() as connection:
        await connection.execute(statement, values)


@contextmanager
def evaluation_api(
    app_sessionmaker: async_sessionmaker[AsyncSession],
) -> Iterator[FastAPI]:
    """This module's router on a bare application, with the real session boundary.

    Identical in shape and for identical reasons to
    ``tests.prompt_registry.registry_api``: the REAL ``authenticate_session``
    rather than a ``dependency_overrides`` seam, because AC-6's refusal shapes are
    only meaningful if the session came from a live row; and a bare ``FastAPI``
    rather than ``prope.app.app``, because the assembled route table is asserted
    in ``tests/architecture`` and what is under test here is behaviour.
    """
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    install_error_envelope(application)
    application.include_router(evaluation_router)
    application.state.sessionmaker = app_sessionmaker
    install_session_authenticator(lambda cookie: authenticate_session(app_sessionmaker, cookie))
    try:
        yield application
    finally:
        reset_session_authenticator()


async def seed_owner(migrate_engine: AsyncEngine, session_id: str) -> str:
    """A workspace, an Owner, a provider config, and a live session cookie.

    The Owner role is the one that holds all four of this module's permissions —
    ``suite.read``, ``suite.edit``, ``run.start``, ``run.read`` — so it is the
    right actor for every test whose subject is not the refusal.

    The provider config comes with it because ``registry.revision``'s binding is
    a real foreign key: a test that forgot it would fail while seeding, in a file
    whose subject is somewhere else entirely.
    """
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, "Owner")
    await seed_provider_config(migrate_engine)
    return await seed_session(migrate_engine, session_id)


async def seed_bound_revision(
    migrate_engine: AsyncEngine,
    version_id: str = VERSION_ID,
    *,
    revision_number: int = 1,
    prompt_id: str = PROMPT_ID,
    **overrides: Any,
) -> str:
    """A revision that names a provider config and an upstream model.

    ``execute_run`` treats an unbound revision as a whole run of
    ``dispatch_failed`` errors rather than dispatching against a NULL, so every
    test that expects cases to be *dispatched* needs the binding present.
    """
    return await seed_revision(
        migrate_engine,
        version_id=version_id,
        prompt_id=prompt_id,
        revision_number=revision_number,
        provider_config_id=PROVIDER_CONFIG_ID,
        upstream_model=UPSTREAM_MODEL,
        **overrides,
    )


async def seed_suite(
    migrate_engine: AsyncEngine,
    suite_id: str = SUITE_ID,
    *,
    name: str = "safety",
    suite_version: int = 1,
    output_modality: str = "text",
    case_count: int = 0,
    prompt_id: str = PROMPT_ID,
    workspace_id: str = WORKSPACE_A,
    **overrides: Any,
) -> str:
    """One eval suite version. ``case_count`` is the author's, not derived."""
    values: dict[str, Any] = {
        "id": suite_id,
        "workspace_id": workspace_id,
        "prompt_id": prompt_id,
        "name": name,
        "suite_version": suite_version,
        "output_modality": output_modality,
        "case_count": case_count,
        "created_by": ADMIN_ID,
        "created_at": day(1),
    }
    values.update(overrides)
    await _insert(migrate_engine, INSERT_SUITE, values)
    return str(values["id"])


async def seed_case(
    migrate_engine: AsyncEngine,
    case_id: str = CASE_ID,
    *,
    suite_id: str = SUITE_ID,
    ordinal: int = 1,
    name: str = "refuses an out-of-policy refund",
    prompt: str = "case-1",
    assertions: Sequence[Mapping[str, Any]] = (),
    workspace_id: str = WORKSPACE_A,
    **overrides: Any,
) -> str:
    """One case. ``prompt`` becomes the user message the stub dispatcher keys on."""
    values: dict[str, Any] = {
        "id": case_id,
        "workspace_id": workspace_id,
        "suite_id": suite_id,
        "ordinal": ordinal,
        "name": name,
        "input_messages": json.dumps([{"role": "user", "content": prompt}]),
        "input_variables": json.dumps({}),
        "assertions": json.dumps([dict(entry) for entry in assertions]),
        "created_at": day(1),
    }
    values.update(overrides)
    await _insert(migrate_engine, INSERT_CASE, values)
    return str(values["id"])


async def seed_run(
    migrate_engine: AsyncEngine,
    run_id: str = RUN_ID,
    *,
    suite_id: str = SUITE_ID,
    version_id: str = VERSION_ID,
    role: str = "candidate",
    status: str = "queued",
    prompt_id: str = PROMPT_ID,
    workspace_id: str = WORKSPACE_A,
    **overrides: Any,
) -> str:
    """One run, ``queued`` unless a test says otherwise — like the write path.

    A run seeded straight into ``completed`` carries its own counts and money, so
    the comparison tests can pin a baseline without paying for an execution they
    are not asserting.
    """
    values: dict[str, Any] = {
        "id": run_id,
        "workspace_id": workspace_id,
        "prompt_id": prompt_id,
        "version_id": version_id,
        "suite_id": suite_id,
        "role": role,
        "status": status,
        "refused_reason": None,
        "started_at": None,
        "finished_at": None,
        "pass_count": 0,
        "fail_count": 0,
        "error_count": 0,
        "input_tokens": None,
        "output_tokens": None,
        "cost_amount": None,
        "cost_currency": None,
        "priced_at": None,
        "started_by": ADMIN_ID,
    }
    values.update(overrides)
    await _insert(migrate_engine, INSERT_RUN, values)
    return str(values["id"])


async def seed_case_result(
    migrate_engine: AsyncEngine,
    result_id: str,
    *,
    run_id: str = RUN_ID,
    case_id: str = CASE_ID,
    outcome: str = "pass",
    output_content: str | None = "ok",
    error_code: str | None = None,
    workspace_id: str = WORKSPACE_A,
    **overrides: Any,
) -> str:
    """One case result. ``error_code`` is not defaulted from ``outcome``.

    ``ck_case_result_error_carries_a_code`` makes the pairing an invariant, and a
    factory that filled the code in would let a test assert a shape the database
    would have refused.
    """
    values: dict[str, Any] = {
        "id": result_id,
        "workspace_id": workspace_id,
        "run_id": run_id,
        "case_id": case_id,
        "outcome": outcome,
        "assertion_results": json.dumps([]),
        "output_content": output_content,
        "latency_ms": 12,
        "input_tokens": 10,
        "output_tokens": 5,
        "error_code": error_code,
        "attempt_count": 1,
        "created_at": day(1),
    }
    values.update(overrides)
    await _insert(migrate_engine, INSERT_CASE_RESULT, values)
    return str(values["id"])


def completion(
    content: str = "ok",
    *,
    input_tokens: int | None = 10,
    output_tokens: int | None = 5,
) -> DispatchResult:
    """One successful dispatch, in the OpenAI shape ``response_content`` reads."""
    total = None if input_tokens is None or output_tokens is None else input_tokens + output_tokens
    return DispatchResult(
        response={
            "id": "cmpl-1",
            "object": "chat.completion",
            "model": UPSTREAM_MODEL,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
        },
        usage=Usage(
            input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total
        ),
        upstream_duration_ms=4.0,
    )


def transport_error(
    *,
    error_class: ErrorClass = ErrorClass.UPSTREAM_UNAVAILABLE,
    retryable: bool = False,
) -> DispatchError:
    """A dispatch failure. A-057 makes this an ``error`` outcome, never a ``fail``."""
    return DispatchError(
        error_class=error_class,
        origin=Origin.PROVIDER,
        fallback_eligible=False,
        retryable=retryable,
        message="the upstream did not answer",
    )


class StubDispatcher:
    """Stands where ``execute_run``'s ``dispatcher=`` parameter expects ``dispatch``.

    Keyed on the case's own user message rather than on call order, because
    cases 2..N run concurrently under a semaphore and their order is not a
    property any test should depend on.

    ``max_in_flight`` is what the load test reads: it is recorded around the
    ``await``, so a bound the semaphore fails to hold shows up as a number rather
    than as a timing.
    """

    def __init__(
        self,
        default: DispatchResult | DispatchError | None = None,
        by_prompt: Mapping[str, DispatchResult | DispatchError] | None = None,
        *,
        latency_seconds: float = 0.0,
    ) -> None:
        self.default: DispatchResult | DispatchError = (
            completion() if default is None else default
        )
        self.by_prompt = dict(by_prompt or {})
        self.latency_seconds = latency_seconds
        self.calls: list[dict[str, Any]] = []
        self.in_flight = 0
        self.max_in_flight = 0

    async def __call__(
        self, sessionmaker: Any, **kwargs: Any
    ) -> DispatchResult | DispatchError:
        self.calls.append(kwargs)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            if self.latency_seconds:
                await asyncio.sleep(self.latency_seconds)
            return self._pick(kwargs.get("messages") or [])
        finally:
            self.in_flight -= 1

    def _pick(self, messages: Sequence[Any]) -> DispatchResult | DispatchError:
        blob = json.dumps(list(messages))
        for key, result in self.by_prompt.items():
            if key in blob:
                return result
        return self.default


async def allow_ceiling(*args: Any, **kwargs: Any) -> CeilingDecision:
    """INT-020 saying yes. The default for every test whose subject is not money."""
    return CeilingDecision(allowed=True)


async def refuse_ceiling(*args: Any, **kwargs: Any) -> CeilingDecision:
    """INT-020 saying no, and — per A-056 — carrying no figure with it."""
    return CeilingDecision(allowed=False)


async def no_pricing(*args: Any, **kwargs: Any) -> None:
    """INT-019 accepting the usage rows and doing nothing observable."""
    return None


def totals(
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost: Decimal | None = None,
    currency: str | None = None,
    unpriced_count: int = 0,
    unknown_usage_count: int = 0,
) -> RunTotals:
    """INT-021's six fields, for a ``totaller=`` that must answer a known figure."""
    return RunTotals(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost=cost,
        currency=currency,
        unpriced_count=unpriced_count,
        unknown_usage_count=unknown_usage_count,
    )


def priced_totaller(
    cost: Decimal, currency: str = "USD", *, input_tokens: int = 0, output_tokens: int = 0
):
    """A ``totaller=`` that answers one fully priced run."""

    async def _totaller(*args: Any, **kwargs: Any) -> RunTotals:
        return totals(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            currency=currency,
        )

    return _totaller


def totaller_by_run(by_run: Mapping[str, RunTotals], default: RunTotals | None = None):
    """A ``totaller=`` that answers a different figure per run.

    A candidate and its baseline are executed by the same batch, so a single
    flat answer would make every cost delta zero — and a delta of zero is
    indistinguishable from a delta that was never computed.
    """
    fallback = totals() if default is None else default

    async def _totaller(
        sessionmaker: Any, workspace_id: str, run_id: str, *args: Any, **kwargs: Any
    ) -> RunTotals:
        return by_run.get(run_id, fallback)

    return _totaller


def frozen_clock(moment: datetime):
    """A ``clock=`` that answers the same instant every time it is asked."""

    def _clock() -> datetime:
        return moment

    return _clock
