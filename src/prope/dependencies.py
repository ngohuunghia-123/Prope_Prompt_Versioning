"""The two FastAPI dependencies every management router needs, in one place.

Both shipped in `prope.call_ledger.api` in Phase 2, when there was one router in
the product and no way to tell module code from shared infrastructure. Phase 7
mounts the second, and access-control may not import call-ledger — ADR-0018 makes
that module a sink — so they move here rather than being written twice. Same
eviction OQ-021 predicted for the error envelope, arriving at the same time and
for the same reason; `prope.call_ledger.api` imports them back so no route in
that module changed.

**Neither of these is a permission check and neither ever becomes one.**
:func:`path_workspace` compares a path parameter against the session's workspace,
which is a *tenancy* question with an answer that does not depend on who is
asking. INT-001's `may()` is what asks who is asking, and it is called by the
route, after this.
"""

from typing import Annotated

from fastapi import Depends, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.errors import ErrorCode
from prope.session_auth import ManagementRefusal, Session, require_session

__all__ = ["cookie_secure", "get_sessionmaker", "path_workspace"]


def cookie_secure(request: Request) -> bool:
    """Whether the session cookie this response sets carries ``Secure``.

    Put on ``app.state`` by ``prope.app``'s lifespan from ``PROPE_COOKIE_SECURE``,
    read here for the same two reasons :func:`get_sessionmaker` is a dependency
    rather than a global: settings are not read at import, and a test needs a
    seam it can point somewhere else.

    **It defaults to ``True`` when the lifespan has not run**, which is the
    opposite of :func:`get_sessionmaker`'s ``503``. A missing sessionmaker means
    the request cannot be served at all; a missing cookie policy means only that
    nobody said, and the safe reading of nobody-said is the ``Secure`` cookie
    ADR-0043 describes. Failing open here would drop the attribute in exactly the
    deployment that forgot to configure itself.
    """
    return bool(getattr(request.app.state, "cookie_secure", True))


def get_sessionmaker(request: Request) -> async_sessionmaker[AsyncSession]:
    """The application's sessionmaker, put on ``app.state`` by ``prope.app``'s lifespan.

    A dependency rather than a module-level global for two reasons: a global
    would be built at import time, before any settings are read, and a test
    would have no seam to point at a container. It is what
    ``tests/integration/test_management_routes.py`` sets.

    A missing sessionmaker is a ``503`` and not a ``500``: the process is up and
    the request is well-formed, and the only state in which this can happen is
    one where the lifespan has not run.
    """
    sessionmaker = getattr(request.app.state, "sessionmaker", None)
    if sessionmaker is None:
        raise ManagementRefusal(
            status_code=503,
            code=ErrorCode.INTERNAL_ERROR,
            message="the application has no database sessionmaker; its lifespan has not run",
        )
    return sessionmaker


def path_workspace(
    workspace_id: Annotated[str, Path(alias="id")],
    session: Annotated[Session, Depends(require_session)],
) -> str:
    """The ``{id}`` path parameter, refused as **not-found** when it is not the session's.

    A-045: *"a subject the actor may not see returns not-found, never
    forbidden"*. The distinction carries security weight here rather than
    politeness — ``403`` would confirm that the named workspace exists, turning
    the path parameter into an enumeration oracle (T-02-30). The refusal is
    byte-identical to the one a workspace that does not exist at all would get,
    because both are this same branch.

    Underneath it, the tenant policy would return zero rows for another
    workspace anyway (ADR-0045). This check is what turns that silence into an
    answer, and what stops a ``PUT`` writing into the session's workspace while
    the caller believes it addressed another.

    **Phase 7 makes this stricter without changing a line of it.** Until now
    ``session.workspace_id`` came from a dependency that refused every request,
    so the comparison had no live values on either side. It now comes from
    ``access.lookup_session``, and a session's workspace is fixed at sign-in —
    there is no route that moves one, which is what makes the equality above a
    total answer rather than a first filter.
    """
    if workspace_id != session.workspace_id:
        raise ManagementRefusal(
            status_code=404,
            code=ErrorCode.NOT_FOUND,
            message="no such workspace",
        )
    return workspace_id
