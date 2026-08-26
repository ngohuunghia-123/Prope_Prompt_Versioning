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

from fastapi import Cookie, Depends, Request

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

#: ADR-0056. The session is live and names **no workspace** — its owner is in the
#: lobby, either because they belong to no workspace yet or because they hold
#: several and have not chosen. Every route that touches tenant data answers this;
#: the handful of lobby routes do not.
#:
#: A ``403`` rather than a ``401``, for ``PASSWORD_CHANGE_REQUIRED``'s reason
#: exactly: the person **is** authenticated, and a ``401`` would send the SPA to
#: the sign-in screen where signing in again would produce the same session and
#: change nothing. The client's next move is the workspace chooser, and this code
#: is what tells it so.
WORKSPACE_REQUIRED = "workspace_required"


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
class ActorSession:
    """A live session, **whose workspace may be absent**. ADR-0056.

    The wider of the two shapes, and the one the authenticator answers with. It
    exists because revision 0022 makes ``access.session.workspace_id`` nullable:
    a person who belongs to no workspace, or who belongs to several and has not
    picked, holds a real session that names no tenant.

    **Almost nothing takes this type.** The lobby routes do — listing your
    workspaces, entering one, redeeming an invitation — and they are the only
    places in Prope where "signed in" and "in a workspace" come apart. Everything
    else declares :class:`Session`, whose ``workspace_id`` is a plain ``str``,
    so the nullability stops at :func:`require_session` and cannot reach a handler
    that assumed a string.

    Frozen and slotted for :class:`Session`'s reason: a handler that could set the
    workspace on its own session is a handler that could write into another tenant
    while holding a valid one.
    """

    user_id: str
    workspace_id: str | None


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

    **``workspace_id`` is still a plain ``str``, and revision 0022 did not change
    that.** The column behind it became nullable, but this type is what a hundred
    routes are annotated with, and widening it would have made every
    ``workspace_transaction(session.workspace_id)`` in the product a call that
    type-checks and fails at runtime for the one caller in the lobby.
    :class:`ActorSession` carries the nullable form and :func:`require_session`
    is the one place the narrowing happens.
    """

    user_id: str
    workspace_id: str


#: What an installed authenticator answers with: the session, and whether its
#: owner still owes A-110's password change. A two-tuple rather than a widened
#: value object, because the promise made in Phase 2 was that this module's
#: **return type does not change** — six modules' routes are annotated
#: ``Annotated[Session, Depends(require_session)]``, and a third field would have
#: been a field one of them could decide with.
#:
#: It answers with the **wider** :class:`ActorSession` from revision 0022 onward.
#: That is not the broken promise it looks like: what the promise protected was
#: the type a *route* receives, and every route that received a :class:`Session`
#: still does. The authenticator is internal — one implementation, one caller.
SessionAuthenticator = Callable[[str | None], Awaitable[tuple["ActorSession", bool] | None]]

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


async def require_actor(
    request: Request,
    session_cookie: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> ActorSession:
    """INT-005 itself: **the whole session boundary, workspace or no workspace.**

    ADR-0056 split :func:`require_session` in two and put every line of the old
    body here. This half answers *"is there a live session, and whose"*; the half
    below adds *"and does it name a tenant"*. Splitting rather than adding a flag
    is what keeps the narrow type honest — a boolean parameter on one dependency
    would have made ``session.workspace_id`` a ``str`` that is sometimes ``None``,
    which is the failure the two types exist to prevent.

    **Declared by the lobby routes and by nothing else.** Listing your workspaces,
    entering one, and redeeming an invitation are the three things a person may do
    while belonging nowhere; each of them either reads no tenant table at all or
    opens its own context on a workspace it has just resolved. Every other route in
    the product declares :func:`require_session`, which is built on this one — so
    ``declares_session`` is true for both, and the route-table assertion sees a
    declared boundary either way.

    Refusals, and the shapes are not interchangeable:

    **No authenticator installed** — ``401 session_required``. Phase 2's behaviour
    preserved rather than deleted: a process that mounted routes without wiring its
    session store must refuse everything, loudly and by default (Pitfall 11).

    **No session** — ``401 session_required``, covering an absent cookie, an
    unknown id, an expired row and a signed-out one. The client may distinguish
    none of the four and does not need to.

    **A session whose owner owes a password change** — ``403
    password_change_required`` on every route but those in
    :data:`PASSWORD_CHANGE_EXEMPT_ACTIONS`. A ``403`` rather than a ``401`` because
    the person *is* authenticated: a ``401`` would send the SPA to the sign-in
    screen, where signing in again would succeed and change nothing.

    ``session_cookie`` is never logged and never quoted in a refusal — a session
    cookie is the whole of a person's authority, so it is treated as a credential
    at the one place it enters the process (A-046).
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

    actor, must_change_password = authenticated
    if must_change_password:
        action = declared_action(request.scope.get("route"))
        if action is None or action.value not in PASSWORD_CHANGE_EXEMPT_ACTIONS:
            raise ManagementRefusal(
                status_code=403,
                code=PASSWORD_CHANGE_REQUIRED,
                message="this account must change its password before it may do anything else",
            )

    return actor


async def require_session(
    actor: Annotated[ActorSession, Depends(require_actor)],
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
    call site naming it — and from ADR-0056 it does not reach this function at all,
    because :func:`require_actor` one level down is where it is needed.

    **What ADR-0056 added is the fourth refusal, and it is the whole of this
    function.** Everything above is now :func:`require_actor`'s; what is left here
    is the narrowing:

    **A live session that names no workspace** — ``403 workspace_required``. Its
    owner is in the lobby, and this route reads tenant data. Refusing here rather
    than in a hundred handlers is the point: ``Session.workspace_id`` stays a plain
    ``str``, so ``workspace_transaction(session.workspace_id)`` is a call that
    cannot receive a ``None`` anywhere in the product. There is no route that
    "handles" a workspace-less session by falling back to something — a fallback
    would be a tenant chosen by code rather than by the person.
    """
    if actor.workspace_id is None:
        raise ManagementRefusal(
            status_code=403,
            code=WORKSPACE_REQUIRED,
            message="this session names no workspace; enter one before using this route",
        )

    return Session(user_id=actor.user_id, workspace_id=actor.workspace_id)


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
    OBSERVABILITY_CONTENT_ACCESS_READ = "call_ledger.observability_content_access.read"
    OBSERVABILITY_CONTENT_ACCESS_SET = "call_ledger.observability_content_access.set"

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
    #: ADR-0056. Which workspaces this person may enter, and which they have asked
    #: to. Under ``/auth`` rather than ``/workspaces`` because it is a fact about
    #: the SESSION's owner and not about any one tenant — it is answered from the
    #: lobby, where no tenant exists to hang it off, and its result set is the
    #: person's own memberships rather than anything a workspace holds.
    WORKSPACE_LIST = "access_control.workspace.list"
    #: ADR-0056. Bind the session to one workspace: the current row is deleted and
    #: a fresh one issued in the target, with a new cookie. Its own action rather
    #: than a reuse of ``AUTH_LOGIN`` because it is the only route in Prope that
    #: changes which tenant an already-authenticated person is acting in, and that
    #: is precisely the operation an audit of a cross-tenant mistake looks for.
    WORKSPACE_ENTER = "access_control.workspace.enter"
    WORKSPACE_CREATE = "access_control.workspace.create"
    MEMBER_LIST = "access_control.member.list"
    MEMBER_ADD = "access_control.member.add"
    MEMBER_REMOVE = "access_control.member.remove"
    MEMBER_ROLES_SET = "access_control.member.roles_set"
    #: ADR-0057's four invitation operations and two decisions.
    #:
    #: ``INVITE_REDEEM`` is the odd one and belongs under ``/auth``: it is answered
    #: from the lobby, where there is no tenant to scope it to, and the workspace it
    #: reaches is discovered from the code rather than named by the caller.
    #: ``MEMBER_APPROVE`` and ``MEMBER_REJECT`` are their own actions rather than a
    #: reuse of ``MEMBER_ADD`` because the fact an audit looks for is *who let this
    #: person in*, and a shared declaration would make the two indistinguishable in
    #: the route table.
    INVITE_LIST = "access_control.invite.list"
    INVITE_CREATE = "access_control.invite.create"
    INVITE_REVOKE = "access_control.invite.revoke"
    INVITE_REDEEM = "access_control.invite.redeem"
    MEMBER_APPROVE = "access_control.member.approve"
    MEMBER_REJECT = "access_control.member.reject"
    GRANT_LIST = "access_control.grant.list"
    GRANT_CREATE = "access_control.grant.create"
    GRANT_REVOKE = "access_control.grant.revoke"
    KEY_LIST = "access_control.key.list"
    KEY_CREATE = "access_control.key.create"
    KEY_REVOKE = "access_control.key.revoke"
    #: Replace a key's ``scope_model_names``. Its own member rather than a second
    #: use of ``KEY_CREATE`` because every route declares exactly one action and
    #: no action is declared twice — and because the two are genuinely different
    #: acts: creation mints a secret, this one changes what an *existing* secret
    #: can already reach, which is the operation an audit of a widened key looks
    #: for. Both map to ``workspace.manage_keys``.
    KEY_SCOPE_SET = "access_control.key.scope_set"
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
    PROMPT_MODEL_NAME_READ = "prompt_registry.prompt.model_name.read"
    PROMPT_UPDATE = "prompt_registry.prompt.update"
    REVISION_TAGS_UPDATE = "prompt_registry.revision_tags.update"
    PROMPT_RETIRE = "prompt_registry.prompt.retire"
    REVISION_LIST = "prompt_registry.revision.list"
    REVISION_CREATE = "prompt_registry.revision.create"
    REVISION_READ = "prompt_registry.revision.read"
    #: The playground: one interactive turn against a revision, dispatched with
    #: that revision's own binding and streamed back. It maps to ``run.start``
    #: rather than to ``prompt.read`` because what it does is **spend provider
    #: money** — the same thing an eval run does, and the permission that already
    #: means "may cause this prompt to cost something". Reading a prompt must not
    #: imply being allowed to bill for it.
    REVISION_TRIAL = "prompt_registry.revision.trial"
    DIFF_READ = "prompt_registry.diff.read"
    ACTIVITY_READ = "prompt_registry.activity.read"
    #: One prompt's call **metadata**, never a body. It is declared by
    #: prompt-registry rather than by call-ledger because ADR-0018 leaves that
    #: module unable to check a permission, and a workspace-wide version of this
    #: read would name the ``prompt_id`` of a private prompt — the disclosure
    #: BR-01 closes as not-found. See ADR-0056.
    CALL_RECORD_LIST = "prompt_registry.call_record.list"
    CALL_OBSERVABILITY_READ = "prompt_registry.call_observability.read"
    #: The same traffic as `CALL_RECORD_LIST`, rolled up per calling integration
    #: instead of listed. A separate member because the vocabulary is one member
    #: per route and no action is declared twice — and because this one, alone
    #: among the registry's reads, resolves an `access.api_key` name. It maps to
    #: `prompt.read` for the reason `CALL_RECORD_LIST` does: what a prompt has
    #: served is part of the prompt, and a reviewer who could see the diff but not
    #: who is calling it would be working from half the evidence.
    PROMPT_USAGE_READ = "prompt_registry.usage.read"
    #: The customer's own chain — which of their prompts a single end-user
    #: conversation put through the gateway, in what order. Two members because
    #: the vocabulary is one member per route: `CONVERSATION_LIST` scans a
    #: prompt's conversations, `CONVERSATION_READ` opens one as a graph.
    #:
    #: Both map to `prompt.read`, for `CALL_RECORD_LIST`'s reason and one more of
    #: their own: the graph is assembled from call *metadata*, the same rows that
    #: read already returns, arranged by a correlation id the caller supplied. No
    #: body is reachable from it, so `read_bodies` (A-040) is as absent here as it
    #: is there — and there is deliberately no workspace-wide route either, so
    #: neither member can be used to discover that a private prompt exists.
    CONVERSATION_LIST = "prompt_registry.conversation.list"
    CONVERSATION_READ = "prompt_registry.conversation.read"
    #: Folders. Four operations because the vocabulary is one member per route,
    #: not one per permission — all four map to ``prompt.create`` in
    #: ``ROUTE_ACTION``, which is where the argument for that lives.
    #:
    #: ``FOLDER_LIST`` is a separate member from ``PROMPT_LIST`` even though both
    #: read ``prompt_property``: no action is declared twice
    #: (``test_every_registered_action_is_declared_exactly_once``), and the two
    #: are genuinely different reads — one pages prompts, the other aggregates
    #: every namespace in the workspace.
    FOLDER_LIST = "prompt_registry.folder.list"
    FOLDER_CREATE = "prompt_registry.folder.create"
    FOLDER_UPDATE = "prompt_registry.folder.update"
    FOLDER_DELETE = "prompt_registry.folder.delete"

    # --- prompt-search ---------------------------------------------------
    PROMPT_SEARCH = "prompt_search.prompt.search"
    #: The duplicate check the import screen runs before creating anything. Its
    #: own member rather than a second use of ``PROMPT_SEARCH`` because every
    #: route declares exactly one action and no action is declared twice
    #: (``test_every_registered_action_is_declared_exactly_once``) — and because
    #: the two are separable in principle: this one reads a whole prompt body
    #: out of the caller and spends an embedding on it.
    PROMPT_SEARCH_SIMILAR = "prompt_search.prompt.search_similar"
    PROMPT_CONVERT = "prompt_conversion.prompt.convert"
    PROMPT_INDEX_READ = "prompt_search.index.read"
    PROMPT_INDEX_TRIGGER = "prompt_search.index.trigger"
    PROMPT_INDEX_PREVIEW = "prompt_search.index.preview"
    PROMPT_INDEX_DELETE = "prompt_search.index.delete"
    PROMPT_INDEX_JOB_READ = "prompt_search.index_job.read"

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
    #: One prompt's run history, newest first — what the prompt-detail Eval tab
    #: reads to say whether this revision survived its suites. `EVAL_RUN_READ`
    #: loads one run by id, which is no use to a screen that does not yet know
    #: any id; a member of its own because no action is declared twice.
    EVAL_RUN_LIST = "evaluation.eval_run.list"
    EVAL_RUN_CASES = "evaluation.eval_run.cases"
    EVAL_CASE_TRACE = "evaluation.eval_case.trace"
    COMPARISON_READ = "evaluation.comparison.read"

    # --- evaluation, datasets (step 4a) -----------------------------------
    #
    # Four more operations across three paths. A *dataset* is the reusable
    # library object somebody picks; a *suite* is the immutable per-prompt thing
    # a run reads. The two are separate objects on purpose (A-004 needs the same
    # yardstick on both sides of a comparison), and these four names keep the
    # distinction visible in the vocabulary rather than only in the schema.
    #
    # ``dataset_attachment.replace`` is a PUT that takes the whole tick-state at
    # once. It maps to ``suite.edit``: choosing what measures a prompt is a
    # suite-authoring act even though no suite is written until a run, and BR-10
    # keeps that distinct from ``prompt.edit``. It is one route rather than a
    # POST/DELETE pair because a builtin id (``builtin:<slug>@<n>``) in a path
    # segment would be a URL-encoding trap for no gain.
    #
    # ``eval_run.start_from_attachments`` maps to ``run.start`` exactly as
    # ``eval_run.start`` does; the difference is where the suite list comes
    # from, which is not an authorisation distinction.
    DATASET_LIST = "evaluation.dataset.list"
    DATASET_ATTACHMENT_LIST = "evaluation.dataset_attachment.list"
    DATASET_ATTACHMENT_REPLACE = "evaluation.dataset_attachment.replace"
    EVAL_RUN_START_FROM_ATTACHMENTS = "evaluation.eval_run.start_from_attachments"

    # --- evaluation, the writable library (step 4b) -----------------------
    #
    # Five more operations across three paths. `datasets` takes GET and POST;
    # `datasets/{dataset_id}` takes GET, PUT and DELETE.
    #
    # Four of the five map to `suite.edit` asked about the WORKSPACE rather than
    # about a prompt — a dataset belongs to no prompt, so there is no
    # per-subject grant to consult and role bindings alone decide. Deliberately
    # NOT a new member of `Action`: that vocabulary is closed, growing it costs
    # a migration, a database CHECK and a matrix row, and "may author yardsticks
    # here" is the permission this already is.
    #
    # `dataset.draft` is the one that is prompt-scoped, because drafting reads a
    # prompt body. It checks `suite.edit` on the prompt itself and then the
    # library gate before writing, so somebody who may read a prompt but not
    # author its yardstick cannot use the agent as a way around that.
    DATASET_READ = "evaluation.dataset.read"
    DATASET_CREATE = "evaluation.dataset.create"
    DATASET_UPDATE = "evaluation.dataset.update"
    DATASET_DELETE = "evaluation.dataset.delete"
    DATASET_DRAFT = "evaluation.dataset.draft"

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

    # --- chat-orchestrator -----------------------------------------------
    #
    # Seven operations across six paths. The interesting one is the split
    # between ``message.send`` and ``action.decide``: they are the same
    # conversation and deliberately not the same operation, because sending a
    # turn reads and deciding on a proposal WRITES. One member covering both
    # would mean the vocabulary could not express *"this person may talk to the
    # assistant and may not let it create anything"*, which is precisely the
    # distinction the human-in-the-loop design exists to make.
    CHAT_MESSAGE_SEND = "chat_orchestrator.message.send"
    #: `POST /chat/messages/stream` — the same turn delivered as SSE. It had
    #: reused `CHAT_MESSAGE_SEND`, which is one member across two routes and
    #: breaks the bijection `test_every_registered_action_is_declared_exactly_once`
    #: asserts. Minted 2026-08-20; the PERMISSION is unchanged (`prompt.read`),
    #: because streaming an answer and returning it are the same act with a
    #: different transport, and this vocabulary answers *"what does this endpoint
    #: do"* rather than *"what may this actor do"*.
    CHAT_MESSAGE_SEND_STREAM = "chat_orchestrator.message.send_stream"
    CHAT_ACTION_DECIDE = "chat_orchestrator.action.decide"
    CHAT_CONVERSATION_LIST = "chat_orchestrator.conversation.list"
    CHAT_CONVERSATION_READ = "chat_orchestrator.conversation.read"
    CHAT_MESSAGE_FEEDBACK = "chat_orchestrator.message.feedback"
    #: The shape of the assistant's pipeline — every node it *could* visit, not
    #: what one turn did. Its own member rather than a reuse of
    #: ``CONVERSATION_READ`` because it reads no conversation and no row: the
    #: response is derived from ``domain.TOOLS`` at request time and is identical
    #: for every actor in every workspace. Declaring that separately is what
    #: keeps the route table honest about which routes touch tenant data.
    CHAT_PIPELINE_READ = "chat_orchestrator.pipeline.read"

    # --- prompt-ingestion ------------------------------------------------
    INGESTION_BATCH_CREATE = "prompt_ingestion.batch.create"
    INGESTION_BATCH_READ = "prompt_ingestion.batch.read"
    INGESTION_ITEM_LIST = "prompt_ingestion.item.list"
    INGESTION_ITEM_UPDATE = "prompt_ingestion.item.update"
    INGESTION_ITEM_RETRY = "prompt_ingestion.item.retry"
    INGESTION_PROPOSAL_CREATE = "prompt_ingestion.proposal.create"
    INGESTION_PROPOSAL_DECIDE = "prompt_ingestion.proposal.decide"
    # --- access-control, namespace authority (ADR-0061) -------------------
    #
    # Three operations over one path pair, and they are the reason ADR-0061 adds
    # the twenty-sixth member of `Action` — `namespace.grant`, the only new
    # PERMISSION in this whole change. A namespace grant hands somebody read or
    # edit over every prompt in a folder at once, present and future, so it is
    # emphatically not `prompt.grant` under another name: `prompt.grant` is
    # bounded by the row it names, this one is not.
    NAMESPACE_GRANT_LIST = "access_control.namespace_grant.list"
    NAMESPACE_GRANT_CREATE = "access_control.namespace_grant.create"
    NAMESPACE_GRANT_REVOKE = "access_control.namespace_grant.revoke"

    # --- prompt-observation, INT-035 (ADR-0060) ---------------------------
    #
    # Seven operations across four paths. Every one maps to `prompt.read` asked
    # about the observation's NAMESPACE (SR-1) — this module mints no permission
    # of its own and borrows nothing, because ADR-0061 gave an observation an
    # access container and the ordinary check against it is the whole rule.
    #
    # That includes the four WRITES, which is worth stating rather than leaving
    # to be noticed. Adopting, dismissing, redacting and deleting are all acts on
    # the inventory and none of them writes a prompt, a revision or a release:
    # adoption RECORDS that prompt-registry created something, through
    # prompt-registry's own routes, under prompt-registry's own permissions. A
    # person who may read the folder may tidy its inbox; a person who may not
    # cannot see that there is one.
    # --- prompt-readiness, INT-038..INT-042 (ADR-0067) ---------------------
    #
    # Five operations, four permissions, and only one of them is new.
    #
    # `card.read` is `prompt.read`, for prompt-registry's reason: a grant confers
    # visibility of the prompt and everything hanging off it, and a reviewer who
    # could see the diff but not what the check found would be a reviewer working
    # from half the evidence.
    #
    # `probe.start` is the twenty-seventh member of `Action` and NOTHING was
    # reused. `run.start` describes a probe accurately — may spend workspace
    # money dispatching against a revision — and reusing it would cost no
    # vocabulary at all. It is refused because A-115's set is mapped to roles by
    # `role_permission` rows, so reuse hands probe capability to every role
    # already holding `run.start` on the deploy that ships this, with nobody
    # deciding (ADR-0067, SR-8).
    #
    # `case_drafts.create` maps to `suite.edit`, which is where
    # `evaluation.dataset.draft` already sits and for that route's stated reason:
    # drafting reads a prompt body and writes to the yardstick library, so
    # somebody who may read a prompt but not author its yardstick cannot use the
    # agent as a way around that.
    #
    # `dismissal.create` is `prompt.edit` rather than `prompt.read`. Silencing a
    # finding is an editorial act on the prompt's own record, and a Reviewer who
    # could dismiss on somebody else's prompt could clear the screen they are
    # meant to be reading.
    READINESS_CARD_READ = "prompt_readiness.card.read"
    READINESS_PROBE_START = "prompt_readiness.probe.start"
    READINESS_CASE_DRAFTS = "prompt_readiness.case_drafts.create"
    READINESS_DISMISSAL_CREATE = "prompt_readiness.dismissal.create"
    READINESS_RULES_READ = "prompt_readiness.rules.read"

    # --- prompt-improvement, INT-045..INT-050 (ADR-0068) -------------------
    #
    # Six operations, four permissions, and NOTHING new is minted. The
    # vocabulary stays at twenty-seven and `ck_role_permission_action_values` is
    # untouched — which is worth stating, because a module that reads every
    # prompt in a workspace and proposes edits to them sounds like one that
    # should need its own action, and the reason it does not is that every act
    # here is an act somebody could already perform by hand.
    #
    # `inbox.read` and `prompt_findings.read` are `prompt.read`, for
    # prompt-registry's reason. The inbox additionally authorises PER PROMPT
    # inside the route (SR-7): a prompt the reader cannot see contributes no row,
    # no count and no total that differs, which is A-116's byte-identical
    # property applied at the list level rather than to one response.
    #
    # `finding.dismiss` and `proposal.dismiss` are `prompt.edit`. Refusing a
    # finding is an editorial act on the prompt's own record, and a reader who
    # could silence findings on somebody else's prompt could clear the screen
    # they are meant to be reading — readiness's argument, unchanged.
    #
    # `proposal.accept` is `revision.create`, and this is the one worth reading
    # twice. The route WRITES NO REVISION (SR-6): it records the disposition and
    # hands back a candidate body for the person to create a revision from, on a
    # separate explicit request. It is nevertheless gated at `revision.create`
    # rather than at `prompt.edit`, because handing somebody a body destined for
    # a revision they could not create would be a permission gap wearing a
    # read's clothes.
    #
    # `schedule.write` is `spend_ceiling.manage`. Enabling the weekly re-probe
    # commits the workspace to a recurring provider bill on its own credential,
    # so it is a SPENDING decision before it is an authoring one — an author who
    # can change a prompt must not thereby be able to start a charge.
    #
    # **`schedule.read` takes the SAME permission as the write**, which is not
    # the usual read/write split and is deliberate. The row is a statement about
    # what the workspace has committed to spending every week; somebody who
    # cannot change that has no decision the number informs, and a read gated
    # lower would publish the workspace's spending posture to every prompt
    # reader. The route exists at all because the setting was write-only until
    # now — there was no way to render the toggle in its current state, so the
    # screen the lock asks for could not be built without guessing.
    IMPROVEMENT_INBOX_READ = "prompt_improvement.inbox.read"
    IMPROVEMENT_PROMPT_FINDINGS_READ = "prompt_improvement.prompt_findings.read"
    IMPROVEMENT_FINDING_DISMISS = "prompt_improvement.finding.dismiss"
    IMPROVEMENT_PROPOSAL_ACCEPT = "prompt_improvement.proposal.accept"
    IMPROVEMENT_PROPOSAL_DISMISS = "prompt_improvement.proposal.dismiss"
    IMPROVEMENT_SCHEDULE_READ = "prompt_improvement.schedule.read"
    IMPROVEMENT_SCHEDULE_WRITE = "prompt_improvement.schedule.write"

    OBSERVATION_LIST = "prompt_observation.observation.list"
    OBSERVATION_READ = "prompt_observation.observation.read"
    OBSERVATION_PROPOSAL = "prompt_observation.observation.proposal"
    OBSERVATION_ADOPTED = "prompt_observation.observation.adopted"
    OBSERVATION_DISMISSED = "prompt_observation.observation.dismissed"
    OBSERVATION_REDACTED = "prompt_observation.observation.redacted"
    OBSERVATION_DELETE = "prompt_observation.observation.delete"

    # Durable, content-free background execution graphs. Reads are scoped to
    # the requesting actor; the lifecycle summary additionally checks the
    # prompt's ordinary visibility before returning any status.
    AGENT_RUN_CREATE = "agent_run.run.create"
    AGENT_RUN_LIST = "agent_run.run.list"
    AGENT_RUN_READ = "agent_run.run.read"
    AGENT_RUN_ACKNOWLEDGE = "agent_run.run.acknowledge"
    LIFECYCLE_SUMMARY_READ = "agent_run.lifecycle_summary.read"
    ANNOTATION_LIST = "prompt_registry.annotation.list"
    ANNOTATION_WRITE = "prompt_registry.annotation.write"


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


#: The two dependencies that ARE the session boundary. ADR-0056 made it two.
#:
#: :func:`require_session` is built on :func:`require_actor`, so a route declaring
#: the first has both in its dependency tree and a route declaring the second has
#: only that one. Both are a declared boundary for AC-10's purposes: the question
#: that assertion asks is *"does anything on this route authenticate"*, and the
#: difference between the two is what a route does with the answer, not whether it
#: got one.
#:
#: Written as a pair rather than as an ``or`` inside the loop below, for
#: ``SESSIONLESS_VERSIONED_ROUTES``' reason one file over: a third entry should be
#: an edit somebody has to make here, beside this paragraph.
SESSION_BOUNDARY_DEPENDENCIES = (require_actor, require_session)


def declares_session(route: Any) -> bool:
    """Whether this route declares the session boundary, at any depth.

    Identity comparison against the function objects rather than a name match: a
    look-alike dependency called ``require_session`` in another module would
    pass a name check and authenticate nothing.
    """
    return any(
        dependency.call in SESSION_BOUNDARY_DEPENDENCIES
        for dependency in _dependencies(route)
    )
