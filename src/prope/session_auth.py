"""The declared session boundary, and the closed management-action vocabulary.

**This file is the answer to a discretion item, and the answer is fail-closed.**
CONTEXT left "management-route authentication before access-control exists" open.
INT-028 settles what the boundary *is* — *"Route-level session auth (INT-005) is
the boundary; there is no INT-001 call here"* — and access-control, which
provides INT-005, ships in Phase 7. So Phase 2 has a boundary with no
implementation behind it, and there are exactly two things it can do with that:
mount the routes with no dependency, or mount them with a dependency that
refuses.

**Mounting them with no dependency is the failure.** Five routes with nothing
declared are five routes that are unauthenticated *by default*, and nothing in
the repository would say so — not a test, not a docstring, not the route table.
The absence of a session store is not the problem; a boundary nobody declared is.
So :func:`require_session` is declared at all five sites today and refuses every
request with ``401`` and the ``session_required`` code, and
``tests/architecture/test_route_table.py`` asserts the declaration over the
*assembled* route table rather than by reading this file.

**What Phase 7 changes, and what it does not.** It replaces this function's
**implementation** with INT-005's server-side session lookup — a live row read,
never a token verification (ADR-0029, ADR-0043), which is why the cookie is
already a parameter here rather than being introduced then. **The five
declaration sites do not change**, and neither does the return type. The shape
was chosen to minimise that diff, not to be convenient now.

**The consequence, stated rather than hidden.** For this phase the five routes
cannot be exercised by hand: every request gets a ``401``. The tests reach the
handlers through FastAPI's ``dependency_overrides``, which is a **test seam and
not a bypass** — nothing in the shipped application overrides anything, and
``tests/integration/test_management_routes.py`` asserts that a request made
without the override is refused rather than served.

**Where this file lives is a spec question, and it is raised rather than
settled.** INT-005 names its consumer as *"the shared session dependency in
``app``, used by every management route in prompt-registry, evaluation,
release-control, provider-access, call-ledger and access-control itself"* — so
the dependency is shared infrastructure. But no module's lock file lists
``src/prope/session_auth.py`` as an artifact it owns, and the upstream planning
root is read-only. This phase places it here, outside every module's package,
because that is the only location consistent with six modules importing it
without any of them importing another module's internals — and records the
reasoning as ``docs/brainstorm/open_questions/OQ-021.md``. No file under
``docs/`` was edited to agree with this choice.

**Nothing here reads or logs anything.** A session cookie is a credential
(ADR-0029 makes it the whole of a person's authority), so it is never written to
a log line or a metric label, and the refusal below quotes no part of it. That is
``prope.observability``'s A-046 allow-list applied at the one place a credential
enters the process.
"""

from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Any

from fastapi import Cookie
from fastapi.routing import APIRoute

#: The one machine code this module produces, held as a constant because
#: ``prope.call_ledger.schemas.ErrorCode`` takes its ``SESSION_REQUIRED`` member's
#: value from it. One literal, in the module that owns the refusal — a second
#: copy in the envelope's vocabulary is a second place for the two to disagree,
#: and the client's translation catalogue is keyed on exactly this string
#: (ADR-0053).
SESSION_REQUIRED = "session_required"

#: The cookie INT-005 authenticates. HttpOnly, Secure, SameSite=Lax, same-origin
#: (ADR-0043, ADR-0052) — none of which this file can enforce, because all three
#: are set by the response that creates the session, and creating sessions is
#: access-control's in Phase 7. Named here so Phase 7 replaces a body rather than
#: introducing a parameter at five call sites.
SESSION_COOKIE = "prope_session"


class ManagementRefusal(Exception):  # noqa: N818
    """A management route's refusal, as the A-045 envelope will render it.

    Raised by a route or by a dependency; turned into
    ``{error: {code, message, details, request_id}}`` by the single handler
    ``prope.app`` registers. Two properties are load-bearing:

    **The ``code`` is the client's, the ``message`` is the log's.** ADR-0053
    puts Vietnamese behind an i18n layer with a keyed catalogue and no literal
    display strings, so the SPA renders the ``code`` and never the ``message``.
    A route that invented a code the catalogue has never seen would render as
    nothing at all, which is why the vocabulary is a ``StrEnum``
    (``prope.call_ledger.schemas.ErrorCode``) and not a free string.

    **``details`` carries structured values, never a driver's words.** A
    constraint name, a SQL fragment or a connection string reaching a client is
    T-02-34; every construction site below builds ``details`` from values the
    caller already sent.

    Not an ``HTTPException`` subclass. FastAPI's own handler renders
    ``{"detail": ...}``, which is a second error shape, and A-045 says there is
    one.
    """

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


@dataclass(frozen=True, slots=True)
class Session:
    """INT-005's whole return: who, and in which workspace. Nothing else.

    Frozen and slotted, like every value object in ``call_ledger.domain`` — a
    handler that could mutate the workspace it was authenticated into is a
    handler that could write into another tenant while holding a valid session.

    ``workspace_id`` is what every route passes to ``workspace_transaction``, so
    it is the tenant for the whole request. ``user_id`` is what a write records
    as ``created_by`` / ``updated_by``. There is no role, no permission set and
    no access level here **on purpose**: call-ledger performs no permission check
    (ADR-0018) and access-control's rule is that callers supply the subject
    (ADR-0020), so a field carrying authority would be a field this module could
    be tempted to decide with.
    """

    user_id: str
    workspace_id: str


async def require_session(
    session_cookie: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> Session:
    """Refuse. Every request, until Phase 7 puts INT-005 behind this.

    **This is the whole of Phase 2's session boundary and it is deliberately
    total.** There is no session store, so there is no request this function can
    honestly say is authenticated; returning a stand-in ``Session`` would make
    five routes serve tenant data to anyone who could reach the port, and doing
    it *quietly* is the failure Pitfall 11 names.

    ``session_cookie`` is read as a parameter and then not used. That is not an
    oversight: it is the argument Phase 7's implementation needs
    (``authenticate_session(cookie)``), declared now so that phase replaces this
    body and touches no call site. It is never logged and never quoted in the
    refusal — a session cookie is a credential.

    Raises :class:`ManagementRefusal` with ``401`` and ``session_required``.
    INT-005's own failure line says ``null -> 401 in the A-045 envelope, and the
    SPA routes to sign-in``, which is the behaviour a client sees today and will
    still see for an expired session after Phase 7.
    """
    raise ManagementRefusal(
        status_code=401,
        code=SESSION_REQUIRED,
        message=(
            "this route requires a session; Prope's session store arrives with access-control "
            "in Phase 7 and until then every management route refuses"
        ),
    )


class ManagementAction(StrEnum):
    """The closed vocabulary every management route declares one member of.

    **What this is not.** It is not an authorisation call and it must never
    become one here. call-ledger performs no permission check by design
    (ADR-0018: *"this module exposes nothing that needs a permission check,
    which is exactly why it can have no dependency on access-control"*), and an
    outbound edge to access-control is the one edge that would turn a ledger
    into a caller. So :func:`declares_action` **attaches** an action to a route
    and checks nothing.

    **What it is.** A declaration that two later tests read: Phase 23's
    cross-module route-table assertion (AC-10 — *"every route declares an action
    from the vocabulary"*), and Phase 7's permission wiring, which needs
    somewhere to look up what a route is asking to do. Declaring it now is what
    stops Phase 23 discovering that five routes never said.

    **Closed, in INT-001's sense and for INT-001's reason.** A-115 makes the
    action vocabulary closed and an unrecognised action a *deny* rather than an
    error, *"because a typo that silently allows is the failure this closure
    exists to prevent"*. call-ledger makes no INT-001 call, so this enum is the
    pattern shaped to fit rather than a call to make — and the closure is
    enforced one step earlier here, at import: :func:`declares_action` refuses
    anything that is not a member, which makes a typo a **startup error** rather
    than a route that mounts and later denies.

    ``call_ledger.`` prefixes every member because this vocabulary is shared
    infrastructure: seven more modules add their own members to this enum, and
    ``price.read`` unqualified would collide the first time two modules both
    have prices. INT-001's own table is grouped by caller for the same reason.
    """

    PRICE_CREATE = "call_ledger.price.create"
    PRICE_READ = "call_ledger.price.read"
    UNPRICED_WORKLIST_READ = "call_ledger.unpriced_worklist.read"
    SPEND_CEILING_SET = "call_ledger.spend_ceiling.set"
    RETENTION_SET = "call_ledger.retention.set"


#: The name the route-table assertions and Phase 7's wiring import, and the same
#: object as :class:`ManagementAction`. Two names for one enum rather than one,
#: because the class follows this repository's ``CostStatus`` / ``CeilingReason``
#: naming and the *vocabulary* is what a reader greps for — INT-008 registers the
#: equivalent for property-history as ``registered_actions()``, a vocabulary
#: readable as data.
MANAGEMENT_ACTIONS = ManagementAction


def declares_action(action: ManagementAction) -> Callable[[], Awaitable[None]]:
    """A no-op dependency that carries ``action`` on the assembled route table.

    Used as ``dependencies=[Depends(declares_action(...))]`` so the action lands
    in the route's own ``dependant`` and is therefore readable from
    ``app.routes`` — which is where AC-10 asserts, and it asserts about the
    *assembled* table rather than about source text. :func:`declared_action` is
    the reader.

    **It performs no check and returns nothing.** See :class:`ManagementAction`.

    Raises ``ValueError`` for anything outside the vocabulary. Because every
    route builds its dependency at module import, that raise is a **startup
    error** — the process does not come up with a route declaring an action the
    vocabulary has never heard of, which is INT-001's closure rule applied at the
    earliest moment available.
    """
    if not isinstance(action, ManagementAction):
        raise ValueError(
            f"{action!r} is not a member of ManagementAction; the vocabulary is closed (A-115) "
            "and an action outside it would mount a route that Phase 7's permission wiring and "
            "Phase 23's route-table assertion could not resolve"
        )

    async def declared_management_action() -> None:
        return None

    declared_management_action.management_action = action  # type: ignore[attr-defined]
    return declared_management_action


def _dependencies(route: APIRoute) -> Iterator[Any]:
    """Every ``Dependant`` reachable from ``route``, at any depth.

    Recursive rather than one level deep: a dependency declared through another
    dependency is still declared, and an assertion that only looked at the top
    level would pass a route that had quietly moved its session check one level
    down and then removed it.
    """
    dependant = getattr(route, "dependant", None)
    if dependant is None:
        return

    pending = list(dependant.dependencies)
    while pending:
        dependency = pending.pop()
        yield dependency
        pending.extend(dependency.dependencies)


def declared_action(route: APIRoute) -> ManagementAction | None:
    """The ``ManagementAction`` this route declares, or ``None`` if it declares none.

    Reads the assembled route table, not the source. Shared by this phase's
    ``tests/architecture/test_route_table.py`` and by Phase 23's cross-module
    form of the same assertion, so the two cannot drift.
    """
    for dependency in _dependencies(route):
        action = getattr(dependency.call, "management_action", None)
        if isinstance(action, ManagementAction):
            return action
    return None


def declares_session(route: APIRoute) -> bool:
    """Whether this route declares :func:`require_session`, at any depth.

    Identity comparison against the function object rather than a name match: a
    look-alike dependency called ``require_session`` in another module would
    pass a name check and authenticate nothing.
    """
    return any(dependency.call is require_session for dependency in _dependencies(route))
