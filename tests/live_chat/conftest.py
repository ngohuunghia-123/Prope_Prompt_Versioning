"""Put ``.env`` in the environment before any test module imports `prope`.

Same problem and the same fix as ``tests/golden/conftest.py``. Both
``prope.app_agent.client`` and ``prope.chat_orchestrator.dspy_program`` read
their settings into module-level constants at import time, so anything that
imports them before the environment is populated binds the empty default
permanently. A lane that measured *that* would report a model routing badly when
what actually happened is an unset variable — the most expensive kind of wrong
measurement, because it reads as a finding.

pytest imports a directory's `conftest.py` before the test modules beside it, so
this is the last point where the ordering can still be fixed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from eval.retrieval.run_eval import load_dotenv  # noqa: E402

load_dotenv()

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker  # noqa: E402

from prope.access_control.bootstrap import authenticate_session  # noqa: E402
from prope.chat_orchestrator import orchestrator  # noqa: E402
from prope.chat_orchestrator.api import router as chat_router  # noqa: E402
from prope.chat_orchestrator.guardrails import RateLimiter  # noqa: E402
from prope.errors import install_error_envelope  # noqa: E402
from prope.session_auth import (  # noqa: E402
    install_session_authenticator,
    reset_session_authenticator,
)
from tests.live_chat import _report  # noqa: E402


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    """The chat router over the real sessionmaker, with the real error envelope."""
    from fastapi import FastAPI

    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    install_error_envelope(application)
    application.include_router(chat_router)
    application.state.sessionmaker = app_sessionmaker
    install_session_authenticator(lambda cookie: authenticate_session(app_sessionmaker, cookie))
    try:
        yield application
    finally:
        reset_session_authenticator()


@pytest.fixture(autouse=True)
def _fresh_rate_limiter(monkeypatch):
    """A per-actor 20-turn window is a production control, not a test budget.

    Twenty journeys in one process share one actor and one sliding minute, so
    without this the tail of the suite reports `chat_rate_limited` and the
    report reads as a routing failure. The limiter itself is asserted in
    `tests/unit/test_chat_guardrails.py`, where it costs nothing.
    """
    monkeypatch.setattr(orchestrator, "rate_limiter", RateLimiter())


@pytest.fixture(autouse=True)
def _name_the_running_test(request):
    """Tie the rows a test opens to the test, so a failure can overwrite them."""
    _report.ACTIVE = request.node.nodeid
    yield
    _report.ACTIVE = ""


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """A row that recorded early and then failed must not print `ok`.

    Every journey records before it asserts, which is what makes a failure
    informative — but it also means the verdict is written before the verdict is
    known. This is where the two are reconciled.
    """
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.failed:
        reason = str(call.excinfo.value).strip().splitlines()[0] if call.excinfo else "assertion"
        _report.mark_failed(item.nodeid, reason[:110])


@pytest.fixture(scope="session", autouse=True)
def _print_conformance_table():
    """One table for the whole run, printed after the last journey."""
    yield
    if _report.RECORDED and os.environ.get("PROPE_RUN_CHAT_LIVE"):
        _report.print_report()
