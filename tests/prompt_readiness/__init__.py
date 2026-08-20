"""Shared fixtures for prompt-readiness's database-backed tests.

Mirrors ``tests.evaluation`` and ``tests.prompt_registry``: the module's router
on a bare application with the **real** session boundary, never a
``dependency_overrides`` seam. This module's refusal shapes are the reason —
not-found for a prompt the actor cannot see, forbidden naming the missing
permission when they can — and neither means anything if the session did not come
from a live row.

The seeds themselves live in ``tests.prompt_registry`` and ``tests.evaluation``.
prompt-readiness owns no prompt, no revision and no provider config; a second set
of seeds here would be a second definition of what a bound revision looks like,
and the one that drifted would be the one nobody was reading.
"""

from collections.abc import Iterator

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.bootstrap import authenticate_session
from prope.errors import install_error_envelope
from prope.prompt_readiness.api import router as readiness_router
from prope.session_auth import install_session_authenticator, reset_session_authenticator

__all__ = ["readiness_api"]


def readiness_api(app_sessionmaker: async_sessionmaker[AsyncSession]) -> Iterator[FastAPI]:
    """This module's router alone, so what is under test is behaviour.

    A bare ``FastAPI`` rather than ``prope.app.app`` for ``tests.evaluation``'s
    stated reason: the assembled route table is asserted in
    ``tests/architecture``, and mounting eight modules here would make a failure
    in any of them look like a failure in this one.
    """
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    install_error_envelope(application)
    application.include_router(readiness_router)
    application.state.sessionmaker = app_sessionmaker
    install_session_authenticator(lambda cookie: authenticate_session(app_sessionmaker, cookie))
    try:
        yield application
    finally:
        reset_session_authenticator()
