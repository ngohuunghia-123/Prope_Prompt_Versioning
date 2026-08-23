"""Shared fixtures for prompt-improvement's tests.

Mirrors ``tests.prompt_readiness``: the module's router on a bare application with
the **real** session boundary, never a ``dependency_overrides`` seam. This
module's refusal shapes are the reason — not-found for a prompt the actor cannot
see, forbidden naming the missing permission when they can — and neither means
anything if the session did not come from a live row.

**The window builder is the interesting part of this file.** Every ledger
detector is a pure function over two :class:`PromptCallWindow` values, so AC-1
needs no database, no provider and no prompt body at all — just counts. That is
the property the detectors were written for, and :func:`window` is what makes it
usable: name the fields that matter for one detector and let the rest be a
healthy baseline.

The seeds themselves live in ``tests.prompt_registry`` and ``tests.evaluation``.
prompt-improvement owns no prompt, no revision and no suite; a second set of seeds
here would be a second definition of what a released prompt looks like, and the
one that drifted would be the one nobody was reading.
"""

from collections.abc import Iterator
from typing import Any

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.bootstrap import authenticate_session
from prope.call_ledger.seams import PromptCallWindow
from prope.errors import install_error_envelope
from prope.prompt_improvement.api import router as improvement_router
from prope.prompt_improvement.domain import WindowPair
from prope.session_auth import install_session_authenticator, reset_session_authenticator

__all__ = ["improvement_api", "pair", "window"]

#: A healthy window, well above ``detectors.MIN_REQUESTS``. Every field a
#: detector reads is present and boring, so a test that changes one field is a
#: test about that field alone.
_BASELINE: dict[str, Any] = {
    "requests": 200,
    "truncated": 0,
    "fallback": 0,
    "caller_error": 0,
    "upstream_error": 0,
    "pinned": 0,
    "usage_unknown": 0,
    "cost_unpriced": 0,
    "chained": 0,
    "input_tokens": 100_000,
    "output_tokens": 100_000,
    "latency_p95_ms": 800,
    "latency_p99_ms": 1_200,
    "last_called_at": None,
}


def window(**overrides: Any) -> PromptCallWindow:
    """One window, healthy except for what the caller names.

    The REAL ``PromptCallWindow`` rather than a stand-in, deliberately. A
    ``SimpleNamespace`` would let a detector read a field the seam does not
    return and the test would still pass — which is exactly the drift between
    the read path and the arithmetic that would be invisible everywhere else.
    """
    return PromptCallWindow(**{**_BASELINE, **overrides})


def pair(**overrides: Any) -> WindowPair:
    """A degraded current window against a healthy prior one."""
    return WindowPair(current=window(**overrides), prior=window())


def improvement_api(app_sessionmaker: async_sessionmaker[AsyncSession]) -> Iterator[FastAPI]:
    """This module's router alone, so what is under test is behaviour.

    A bare ``FastAPI`` rather than ``prope.app.app`` for ``tests.evaluation``'s
    stated reason: the assembled route table is asserted in
    ``tests/architecture``, and mounting a dozen modules here would make a failure
    in any of them look like a failure in this one.
    """
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    install_error_envelope(application)
    application.include_router(improvement_router)
    application.state.sessionmaker = app_sessionmaker
    install_session_authenticator(lambda cookie: authenticate_session(app_sessionmaker, cookie))
    try:
        yield application
    finally:
        reset_session_authenticator()
