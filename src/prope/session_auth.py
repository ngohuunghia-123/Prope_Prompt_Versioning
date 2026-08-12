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

from fastapi import Cookie, Request

#: The one machine code this module produces, held as a constant because
#: ``prope.errors.ErrorCode`` takes its ``SESSION_REQUIRED`` member's value from
#: it. One literal, in the module that owns the refusal — a second copy in the
#: envelope's vocabulary is a second place for the two to disagree, and the
#: client's translation catalogue is keyed on exactly this string (ADR-0053).
#:
#: The direction of that import is why this module may not import
#: ``prope.errors`` back: ``errors`` depends on this file, and ``ManagementRefusal``
#: therefore stays here rather than moving with the envelope in Phase 7.
SESSION_REQUIRED = "session_required"

#: A-110's forced first sign-in, as a machine code. Same construction and same
#: reason as ``SESSION_REQUIRED`` above: ``prope.errors.ErrorCode`` takes its
#: member's value from here.
#:
#: An Admin creates an account and hands the password over out of band, so the
#: account is usable by whoever heard it said out loud until it is changed.
#: Enforcing that at the **session boundary** rather than on the sign-in response
#: alone is what makes it real: a client that simply ignored the sign-in
#: response's hint would otherwise keep the handed-over password indefinitely.
PASSWORD_CHANGE_REQUIRED = "password_change_required"

#: The cookie INT-005 authenticates. HttpOnly, Secure, SameSite=Lax, same-origin
#: (ADR-0043, ADR-0052) — none of which this file can enforce, because all three
#: are set by the response that creates the session, and creating sessions is
#: access-control's. Named here since Phase 2 so Phase 7 replaced a body rather
#: than introducing a parameter at five call sites, which is what happened.
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
    (``prope.errors.ErrorCode``) and not a free string.

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


#: What an installed authenticator answers with: the session, and whether its
#: owner still owes A-110's password change. A two-tuple rather than a widened
#: :class:`Session`, because the promise made in Phase 2 was that this module's
#: **return type does not change** — six modules' routes are annotated
#: ``Annotated[Session, Depends(require_session)]``, and a third field would have
#: been a field one of them could decide with.
SessionAuthenticator = Callable[[str | None], Awaitable[tuple["Session", bool] | None]]

#: Installed by the composition root, exactly as ``property_history``'s action
#: registry is (ADR-0038). ``None`` until then, and ``require_session`` refuses
#: while it is ``None`` — which is byte-for-byte the Phase 2 behaviour this file
#: shipped with, now reachable only in a process that did not wire itself up.
_authenticator: SessionAuthenticator | None = None

#: The actions a person who owes a password change may still take.
#:
#: Sign out, change the password, and read your own session. Anything else would
#: let somebody keep working on a credential an Admin read out to them, which is
#: the whole of what A-110's *"required at first sign-in"* forbids; and *fewer*
#: than these would lock them out of the only route that clears the condition,
#: which is worse than not enforcing it at all.
#:
#: **``auth.session`` is on the list for that second reason rather than the
#: first.** It reads no tenant data and changes nothing — it answers who the
#: cookie belongs to — and the SPA needs it to draw the change-password screen's
#: own chrome. Refusing it would send the client to a screen it cannot render,
#: which is the lock-out this set exists to prevent arriving one route later.
#:
#: Held as actions rather than as paths. A path check is a string comparison
#: against a route table that moves; ``declared_action`` reads what the route
#: itself declares, which is the same mechanism AC-10 asserts over.
PASSWORD_CHANGE_EXEMPT_ACTIONS = frozenset(
    {
        "access_control.auth.password",
        "access_control.auth.logout",
        "access_control.auth.session",
    }
)


def install_session_authenticator(authenticator: SessionAuthenticator) -> None:
    """Put INT-005 behind :func:`require_session`. Composition roots only.

    **This is how Phase 7 replaced the body without this file importing
    access-control.** ``prope.access_control.actions`` imports ``ManagementAction``
    from here, so an import in the other direction would be a cycle — and a
    function-local import to dodge it would be a dependency the module graph test
    could not see. Injection at the composition root is the same shape
    ``install_registry`` already uses, for the same reason, and it keeps this file
    what its docstring says it is: shared infrastructure that imports no module.
    """
    global _authenticator
    _authenticator = authenticator


def reset_session_authenticator() -> None:
    """Restore the refuse-everything default. Test rig only."""
    global _authenticator
    _authenticator = None


async def require_session(
    request: Request,
    session_cookie: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> Session:
    """INT-005, at the one boundary every management route in Prope declares.

    **A live row read, not a token verification** (A-108, ADR-0022, ADR-0029).
    Sessions are server-side rows precisely so that signing out or removing a
    member takes effect at once rather than at expiry, and nothing here or in any
    caller may cache the answer (A-114).

    ``session_cookie`` is never logged and never quoted in a refusal — a session
    cookie is the whole of a person's authority, so it is treated as a credential
    at the one place it enters the process (A-046).

    Three refusals, and the shapes are not interchangeable:

    **No authenticator installed** — ``401 session_required``. This is Phase 2's
    behaviour preserved rather than deleted: a process that mounted routes without
    wiring its session store must refuse everything, loudly and by default, rather
    than serve tenant data to anyone who can reach the port (Pitfall 11).

    **No session** — ``401 session_required``, and it covers an absent cookie, an
    unknown id, an expired row and a signed-out one. INT-005's failure line is
    ``null -> 401 in the A-045 envelope, and the SPA routes to sign-in``; the
    client may distinguish none of the four and does not need to.

    **A session whose owner owes a password change** — ``403
    password_change_required`` on every route but the two in
    :data:`PASSWORD_CHANGE_EXEMPT_ACTIONS`. A ``403`` rather than a ``401``
    because the person *is* authenticated: a ``401`` would send the SPA to the
    sign-in screen, where signing in again would succeed and change nothing.

    ``request`` was added in Phase 7 and is not a broken promise. The promise was
    that the **five declaration sites** and the **return type** do not change, and
    neither did: every route still writes ``Depends(require_session)`` and still
    receives a two-field :class:`Session`. FastAPI injects ``Request`` without any
    call site naming it.
    """
    if _authenticator is None:
        raise ManagementRefusal(
            status_code=401,
            code=SESSION_REQUIRED,
            message="this process has no session authenticator installed; every route refuses",
        )

    authenticated = await _authenticator(session_cookie)
    if authenticated is None:
        raise ManagementRefusal(
            status_code=401,
            code=SESSION_REQUIRED,
            message="no live session for the presented cookie",
        )

    session, must_change_password = authenticated
    if must_change_password:
        action = declared_action(request.scope.get("route"))
        if action is None or action.value not in PASSWORD_CHANGE_EXEMPT_ACTIONS:
            raise ManagementRefusal(
                status_code=403,
                code=PASSWORD_CHANGE_REQUIRED,
                message="this account must change its password before it may do anything else",
            )

    return session


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

    A module prefix on every member, because this vocabulary is shared
    infrastructure: six more modules add their own members to this enum, and
    ``price.read`` unqualified would collide the first time two modules both
    have prices. INT-001's own table is grouped by caller for the same reason.

    **This is NOT A-115's vocabulary, and Phase 7 is where the difference became
    load-bearing.** A-115 enumerates twenty-five *permissions* and is the domain
    of ``access.role_permission.action``; this enumerates *operations*, one per
    HTTP route, and the route-table test asserts that bijection. They are coarser
    and finer respectively — ``price.manage`` is one permission over three routes
    — and they are joined by ``prope.access_control.actions.ROUTE_ACTION``, which
    is total over this enum and is the only place the two meet. The whole
    argument is in that module's docstring.
    """

    # --- call-ledger, INT-028 (Phase 2) -----------------------------------
    PRICE_CREATE = "call_ledger.price.create"
    PRICE_READ = "call_ledger.price.read"
    UNPRICED_WORKLIST_READ = "call_ledger.unpriced_worklist.read"
    SPEND_CEILING_SET = "call_ledger.spend_ceiling.set"
    RETENTION_SET = "call_ledger.retention.set"

    # --- access-control, INT-029 (Phase 8) --------------------------------
    #
    # Sixteen operations across thirteen paths. INT-029's own text says
    # "15 routes" and the lock file says the tombstone took it "from 14 to 15";
    # neither count matches an enumeration of the route list either document
    # prints, which is OQ-134. Sixteen is what is served, and the route table
    # asserts sixteen.
    AUTH_LOGIN = "access_control.auth.login"
    AUTH_LOGOUT = "access_control.auth.logout"
    AUTH_PASSWORD = "access_control.auth.password"
    #: Added with ADR-0052's SPA. A same-origin ``HttpOnly`` cookie is invisible to
    #: the script it authorises, so the client cannot know whether it holds a
    #: session without asking — and firing a real request to read the ``401``
    #: instead means every page load renders the signed-out shell first.
    AUTH_SESSION = "access_control.auth.session"
    #: Self-serve sign-up, and the second and last unauthenticated route. Before
    #: it, an install with no accounts could not be signed into at all: every door
    #: into the product was behind a door.
    AUTH_REGISTER = "access_control.auth.register"
    WORKSPACE_CREATE = "access_control.workspace.create"
    MEMBER_LIST = "access_control.member.list"
    MEMBER_ADD = "access_control.member.add"
    MEMBER_REMOVE = "access_control.member.remove"
    MEMBER_ROLES_SET = "access_control.member.roles_set"
    GRANT_LIST = "access_control.grant.list"
    GRANT_CREATE = "access_control.grant.create"
    GRANT_REVOKE = "access_control.grant.revoke"
    KEY_LIST = "access_control.key.list"
    KEY_CREATE = "access_control.key.create"
    KEY_REVOKE = "access_control.key.revoke"
    PERMISSION_MATRIX_READ = "access_control.permission_matrix.read"
    USER_TOMBSTONE = "access_control.user.tombstone"

    # --- provider-access, INT-027 (Phase 11) ------------------------------
    #
    # Ten operations across six paths. The credential is write-only across
    # the whole seam: no member here reads one back, and no route declares an
    # operation that could.
    PROVIDER_CREATE = "provider_access.provider.create"
    PROVIDER_LIST = "provider_access.provider.list"
    PROVIDER_READ = "provider_access.provider.read"
    PROVIDER_UPDATE = "provider_access.provider.update"
    PROVIDER_ROTATE_CREDENTIAL = "provider_access.provider.rotate_credential"
    PROVIDER_VERIFY = "provider_access.provider.verify"
    PROVIDER_DELETE = "provider_access.provider.delete"
    CATALOGUE_READ = "provider_access.catalogue.read"
    CATALOGUE_REFRESH = "provider_access.catalogue.refresh"
    CATALOGUE_ADD = "provider_access.catalogue.add"

    # --- prompt-registry, INT-024 (Phase 14) ------------------------------
    #
    # Ten operations across seven paths — the widest management surface in the
    # build. Three of those paths sit under ``/api/v1/prompts/{prompt_id}``,
    # which access-control's grants already share and evaluation and
    # release-control will share later; no module owns the prefix, and
    # ``test_the_assembled_table_has_no_duplicate_operation`` is what keeps that
    # safe rather than the fact that nobody has collided yet.
    #
    # ``prompt.update`` covers three permissions rather than one: the route
    # declares ``prompt.edit`` and the handler additionally requires
    # ``prompt.transfer_owner`` or ``prompt.grant`` when the field that needs
    # them actually moves. The map in ``access_control.actions`` records the
    # coarsest of the three, because that is the one every call to this route
    # needs.
    PROMPT_LIST = "prompt_registry.prompt.list"
    PROMPT_CREATE = "prompt_registry.prompt.create"
    PROMPT_READ = "prompt_registry.prompt.read"
    PROMPT_UPDATE = "prompt_registry.prompt.update"
    PROMPT_RETIRE = "prompt_registry.prompt.retire"
    REVISION_LIST = "prompt_registry.revision.list"
    REVISION_CREATE = "prompt_registry.revision.create"
    REVISION_READ = "prompt_registry.revision.read"
    DIFF_READ = "prompt_registry.diff.read"
    ACTIVITY_READ = "prompt_registry.activity.read"
    #: One prompt's call **metadata**, never a body. It is declared by
    #: prompt-registry rather than by call-ledger because ADR-0018 leaves that
    #: module unable to check a permission, and a workspace-wide version of this
    #: read would name the ``prompt_id`` of a private prompt — the disclosure
    #: BR-01 closes as not-found. See ADR-0055.
    CALL_RECORD_LIST = "prompt_registry.call_record.list"

    # --- evaluation, INT-025 (Phase 17) -----------------------------------
    #
    # Nine operations across eight paths. Two of those paths sit under
    # ``/api/v1/prompts/{prompt_id}``, which prompt-registry and access-control
    # already share and release-control will share later; no module owns the
    # prefix, and ``test_the_assembled_table_has_no_duplicate_operation`` is
    # what keeps that safe.
    #
    # ``eval_suite.update`` is a CREATE in every sense but the verb: a PUT
    # writes the next version of the suite and never mutates one, because a
    # suite edit changes the yardstick every later comparison is measured with
    # (A-004). It maps to ``suite.edit``, which BR-10 keeps distinct from
    # ``prompt.edit``.
    EVAL_SUITE_LIST = "evaluation.eval_suite.list"
    EVAL_SUITE_CREATE = "evaluation.eval_suite.create"
    EVAL_SUITE_READ = "evaluation.eval_suite.read"
    EVAL_SUITE_VERSIONS = "evaluation.eval_suite.versions"
    EVAL_SUITE_UPDATE = "evaluation.eval_suite.update"
    EVAL_RUN_START = "evaluation.eval_run.start"
    EVAL_RUN_READ = "evaluation.eval_run.read"
    EVAL_RUN_CASES = "evaluation.eval_run.cases"
    COMPARISON_READ = "evaluation.comparison.read"

    # --- release-control, INT-026 (Phase 23) ------------------------------
    #
    # Eleven operations across ten paths. Eight of those paths sit under
    # ``/api/v1/prompts/{prompt_id}``, which access-control, prompt-registry and
    # evaluation already share; no module owns the prefix, and
    # ``test_the_assembled_table_has_no_duplicate_operation`` is what keeps that
    # safe rather than the fact that nobody has collided yet.
    #
    # ``release.approve_and_release`` maps to ``revision.approve`` and the
    # handler additionally requires ``release.create`` — the same shape
    # ``prompt.update`` already uses, because this map answers *"what must every
    # caller of this route hold"* and a route has exactly one entry. Refusing it
    # names whichever of the two is missing (A-076).
    RELEASE_SUBMIT = "release_control.revision.submit"
    RELEASE_REVIEW_READ = "release_control.review.read"
    RELEASE_APPROVE = "release_control.revision.approve"
    RELEASE_REQUEST_CHANGES = "release_control.revision.request_changes"
    RELEASE_APPROVE_AND_RELEASE = "release_control.revision.approve_and_release"
    RELEASE_CREATE = "release_control.release.create"
    RELEASE_LIST = "release_control.release.list"
    RELEASE_BREAK_GLASS = "release_control.release.break_glass"
    RELEASE_WITHDRAW = "release_control.release.withdraw"
    RELEASE_REVIEW_TASK_LIST = "release_control.review_task.list"
    RELEASE_REVIEW_TASK_CLOSE = "release_control.review_task.close"


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


def assembled_routes(application: Any) -> list[Any]:
    """Every route the application will actually serve, with prefixes applied.

    **``app.routes`` is not the assembled table, and assuming it is would make an
    assertion that passes while checking nothing.** ``include_router`` does not
    flatten a router's routes into ``app.routes``: it appends one lazy entry that
    expands to the effective routes on demand. A test that enumerated
    ``app.routes`` and looked for ``APIRoute`` instances would find ``/healthz``
    and ``/readyz``, find no ``/api/v1`` route at all, and conclude that every
    ``/api/v1`` route declares a session — vacuously, over an empty set.

    So this walks both shapes and returns objects that all carry ``path``,
    ``methods`` and ``dependant``. It lives here rather than in the test that
    needs it because **Phase 23 extends that test across every module** and the
    walk is the part that is easy to get subtly wrong.
    """
    routes: list[Any] = []
    for route in application.routes:
        expand = getattr(route, "effective_route_contexts", None)
        if expand is not None:
            routes.extend(expand())
        elif getattr(route, "dependant", None) is not None:
            routes.append(route)
    return routes


def _dependencies(route: Any) -> Iterator[Any]:
    """Every ``Dependant`` reachable from ``route``, at any depth.

    ``route`` is anything carrying a ``dependant``, and the looseness is a fact
    about FastAPI rather than a shrug: ``include_router`` does not flatten a
    router's routes into ``app.routes``, so the assembled table is a mixture of
    ``APIRoute`` (for routes declared on the application itself) and the
    effective-route contexts an included router yields. Both carry ``path``,
    ``methods`` and ``dependant``; neither is the other's subclass.

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


def declared_action(route: Any) -> ManagementAction | None:
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


def declares_session(route: Any) -> bool:
    """Whether this route declares :func:`require_session`, at any depth.

    Identity comparison against the function object rather than a name match: a
    look-alike dependency called ``require_session`` in another module would
    pass a name check and authenticate nothing.
    """
    return any(dependency.call is require_session for dependency in _dependencies(route))
