"""INT-029 — sixteen operations across thirteen paths, and Prope's only open route.

**Every route declares a `ManagementAction` and all but one declare a session.**
`POST /api/v1/auth/login` is the exception and it is the only one in the product;
`tests/architecture/test_route_table.py` carries the exemption as a named set
rather than as a `!=` in a loop, so adding a second unauthenticated route is an
edit somebody has to make deliberately.

**Two refusal shapes, and which one a route uses is a security decision.**
A-116: not-found when the actor cannot see the subject, forbidden **naming the
missing permission** when they can. :func:`refuse` is the one place that choice is
made, and every route goes through it — a route that raised its own
`ManagementRefusal` for a permission failure would be a route that could get the
shape wrong quietly.

**Three routes take a subject this module may not read**, and all three take its
attributes from the caller instead (ADR-0020): the grant routes are given a
`prompt_id` and the prompt's owner and access level by the SPA, which read them
from prompt-registry a moment earlier. That is the same contract every in-process
caller honours, arriving over HTTP because ADR-0052 has the SPA call this module
directly rather than proxying through the registry.

**`GET /permissions` renders the running matrix.** It is how OQ-006's eventual
answer gets checked against what is actually installed, which is why it is a read
of `access.role_permission` and not a serialisation of the `Action` enum.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Path, Query, Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control import commands
from prope.access_control.actions import Action
from prope.access_control.domain import (
    AccessLevel,
    Actor,
    ActorType,
    GrantLevel,
    Role,
    Subject,
    SubjectType,
)
from prope.access_control.limiter import limiter as process_limiter
from prope.access_control.permissions import may
from prope.access_control.schemas import (
    AddedMember,
    CreatedKey,
    GrantCreate,
    GrantRead,
    KeyCreate,
    KeyRead,
    LoginRequest,
    LoginResponse,
    MemberCreate,
    MemberPage,
    MemberRead,
    MemberRoleSet,
    MemberStatusFilter,
    PasswordChange,
    PermissionMatrix,
    PermissionRow,
    RegisterRequest,
    SessionRead,
    SessionUser,
    WorkspaceCreate,
    WorkspaceRead,
)
from prope.access_control.sessions import (
    SESSION_LIFETIME,
    delete_user_sessions,
    public_session_id,
    sign_in,
)
from prope.db.session import workspace_transaction
from prope.dependencies import cookie_secure, get_sessionmaker, path_workspace
from prope.errors import ErrorCode
from prope.session_auth import (
    SESSION_COOKIE,
    SESSION_REQUIRED,
    ManagementAction,
    ManagementRefusal,
    Session,
    declares_action,
    require_session,
)

router = APIRouter(prefix="/api/v1")

#: A-045's page size, restated rather than imported from call-ledger: that
#: module is a sink and this one may not depend on it (ADR-0018). The numbers are
#: A-045's and the duplication is the price of the dependency rule.
DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 200

LIST_MEMBERS = text(
    """
    SELECT wm.user_id,
           u.email,
           u.display_name,
           wm.status,
           wm.added_at,
           coalesce(
               array_agg(rb.role ORDER BY rb.role) FILTER (WHERE rb.role IS NOT NULL),
               '{}'
           ) AS roles
    FROM   access.workspace_member AS wm
    JOIN   access."user"           AS u  ON u.id = wm.user_id
    LEFT   JOIN access.role_binding AS rb
      ON   rb.workspace_id = wm.workspace_id AND rb.user_id = wm.user_id
    WHERE  (CAST(:status AS text) IS NULL OR wm.status = :status)
      AND  (CAST(:cursor AS text) IS NULL OR wm.user_id > :cursor)
    GROUP  BY wm.user_id, u.email, u.display_name, wm.status, wm.added_at
    ORDER  BY wm.user_id
    LIMIT  :limit
    """
)

LIST_GRANTS = text(
    """
    SELECT prompt_id, grantee_user_id, level, granted_by, granted_at
    FROM   access.prompt_grant
    WHERE  prompt_id = :prompt_id
    ORDER  BY grantee_user_id
    """
)

LIST_KEYS = text(
    """
    SELECT id, name, last_four, scope_model_names, created_by, created_at,
           revoked_at, last_used_at
    FROM   access.api_key
    ORDER  BY created_at DESC, id
    """
)

LOAD_PERMISSION_MATRIX = text(
    "SELECT role, action FROM access.role_permission ORDER BY role, action"
)

#: The whole of :class:`SessionRead`, in one statement, under the tenant policy.
#:
#: **Three routes read this and they are the SPA's entire session story**: sign in,
#: register, and the reload that follows every full page load. A shape assembled
#: separately at each of the three would be three chances for the account chip to
#: disagree with itself.
#:
#: It joins `access.session` by primary key rather than by `user_id`, because a
#: person may hold several sessions at once and `expires_at` is a property of the
#: one presenting the cookie. `access."user"` is global and needs no policy
#: (ADR-0045); `session`, `workspace` and `role_binding` are all policied, and the
#: caller opens this on `workspace_transaction` so every one of them is filtered
#: by the tenant the session already named.
#:
#: The `LEFT JOIN` and the `FILTER` are `LIST_MEMBERS`' — a person with no role
#: binding is a legitimate state (a member an Admin has not assigned yet), and an
#: inner join would answer *"no such session"* for them.
LOAD_SESSION_ENVELOPE = text(
    """
    SELECT s.expires_at,
           u.id            AS user_id,
           u.display_name,
           u.email,
           u.must_change_password,
           w.name          AS workspace_name,
           coalesce(
               array_agg(rb.role ORDER BY rb.role) FILTER (WHERE rb.role IS NOT NULL),
               '{}'
           ) AS roles
    FROM   access.session        AS s
    JOIN   access."user"         AS u ON u.id = s.user_id
    JOIN   access.workspace      AS w ON w.id = s.workspace_id
    LEFT   JOIN access.role_binding AS rb
      ON   rb.workspace_id = s.workspace_id AND rb.user_id = s.user_id
    WHERE  s.id = :session_id
      AND  u.status = 'active'
    GROUP  BY s.expires_at, u.id, u.display_name, u.email, u.must_change_password, w.name
    """
)


def _utc_now() -> datetime:
    """The one clock read in this module, in the one place that may read it.

    Everything downstream takes the instant as an argument, so what a request
    wrote is arithmetic on one value rather than on however many clock reads the
    call graph made. `prope.call_ledger.api` states the same rule.
    """
    return datetime.now(UTC)


def actor_of(session: Session) -> Actor:
    """The session, as INT-001's first parameter.

    A person, always. A consumer key never reaches a management route — it
    authenticates at the gateway and its whole authority is `may_resolve`.
    """
    return Actor(type=ActorType.USER, id=session.user_id, workspace_id=session.workspace_id)


def refuse(action: Action, subject: Subject, *, visible: bool) -> ManagementRefusal:
    """A-116's two shapes, decided in one place. **Never raise a refusal directly.**

    `visible=False` renders as **not-found**, byte-identical to the response for
    an id that does not exist. That is what stops a private prompt being confirmed
    to exist, which is BR-01's whole point and the failure most likely to end a
    pilot — because it is discovered by the person whose prompt leaked.

    `visible=True` renders as **forbidden, naming the missing permission** in
    `details.permission`. Once somebody can already see the subject, hiding *why*
    they cannot act on it protects nothing and produces the worst support
    conversation in the product: a button that does nothing, with no way to find
    out what to ask for.

    The permission name is a machine string from the closed vocabulary, so it is
    safe as `details` under A-046 and the SPA can key a catalogue entry on it
    (ADR-0053).
    """
    if not visible:
        return ManagementRefusal(
            status_code=404,
            code=ErrorCode.NOT_FOUND,
            message="no such subject",
        )
    return ManagementRefusal(
        status_code=403,
        code=ErrorCode.PERMISSION_DENIED,
        message=f"this action requires the {action.value} permission",
        details={"permission": action.value, "subject_type": subject.type.value},
    )


async def require_permission(
    db: AsyncSession, session: Session, action: Action, subject: Subject
) -> None:
    """`may()`, and the refusal shape that follows from it.

    **Visibility is a second question, and it is only in question for a prompt.**
    BR-01 makes prompts private by default, so an actor who may not `prompt.read`
    one must not learn it exists — the refusal is not-found. Every other subject
    here is the actor's *own workspace*, which their session already names: a
    not-found there would hide nothing and would tell an Admin their workspace
    does not exist, which is the worst support conversation in the product.

    The second `may()` call runs only on the failure path, so the cost is paid by
    requests that were about to be refused anyway.
    """
    if await may(db, actor_of(session), action, subject):
        return

    if subject.type is not SubjectType.PROMPT:
        visible = True
    elif action is Action.PROMPT_READ:
        # The failed check WAS the visibility check. Asking it again would answer
        # the same way and turn a not-found into a forbidden.
        visible = False
    else:
        visible = await may(db, actor_of(session), Action.PROMPT_READ, subject)

    raise refuse(action, subject, visible=visible)


def workspace_subject(session: Session) -> Subject:
    """The workspace itself, as a subject. Used by every workspace-admin route.

    It carries no `owner_id` and no `access_level`: a workspace has neither, and
    `may()` answers those routes on role bindings alone — which is A-007's
    `workspace.manage_members` and `workspace.manage_keys` doing exactly the job
    they exist for.
    """
    return Subject(
        type=SubjectType.WORKSPACE,
        id=session.workspace_id,
        workspace_id=session.workspace_id,
    )


# ---------------------------------------------------------------------------
# /auth
# ---------------------------------------------------------------------------


async def _read_session(
    sessionmaker: async_sessionmaker[AsyncSession], *, session_id: str, workspace_id: str
) -> SessionRead | None:
    """Assemble :class:`SessionRead` for a live session, or ``None`` if there is none.

    One place, because sign-in, registration and the session read all answer with
    this shape and a client that had to reconcile three of them would be a client
    with three chances to render a stale name.

    ``None`` covers a session id that is not in this tenant, one whose row has been
    deleted, and one whose owner is no longer active — the same four-facts-one-answer
    rule `bootstrap.authenticate_session` states, for the same reason: the client may
    distinguish none of them.

    The session id reaches this function and does not leave it: what goes into the
    response is :func:`public_session_id`'s digest.
    """
    async with workspace_transaction(sessionmaker, workspace_id) as db:
        row = (await db.execute(LOAD_SESSION_ENVELOPE, {"session_id": session_id})).one_or_none()

    if row is None:
        return None

    return SessionRead(
        id=public_session_id(session_id),
        expires_at=row.expires_at,
        must_change_password=row.must_change_password,
        user=SessionUser(
            id=row.user_id,
            display_name=row.display_name,
            email=row.email,
            roles=[Role(role) for role in row.roles],
            workspace_id=workspace_id,
            workspace_name=row.workspace_name,
        ),
    )


def _issue_session_cookie(response: Response, session_id: str, *, secure: bool) -> None:
    """Put the session id where ADR-0029 says it goes, and nowhere else.

    ``HttpOnly`` so no script can read it, ``SameSite=Lax`` because the SPA is
    same-origin — which is also why there is no CORS configuration and no CSRF
    token anywhere in Prope (A-142 §8, ADR-0052).

    ``secure`` is a parameter rather than ``True`` because ADR-0033's stated
    development and demo target is a laptop, where the single ingress listens on
    ``:80`` and a browser **silently discards** a ``Secure`` cookie. It defaults to
    ``True`` everywhere the setting is absent; see
    :func:`prope.dependencies.cookie_secure`.

    One function for two routes, so sign-in and registration cannot drift into
    setting different attributes on the same credential.
    """
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


@router.post(
    "/auth/login",
    response_model=LoginResponse,
    dependencies=[Depends(declares_action(ManagementAction.AUTH_LOGIN))],
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
    secure_cookie: Annotated[bool, Depends(cookie_secure)],
) -> LoginResponse:
    """**One of the two unauthenticated routes in Prope's management API.**

    Declares its action and no session, which is why
    `test_every_versioned_route_declares_a_session_and_an_action` carries a named
    exemption for this path — and, since sign-up landed, for `/auth/register`.
    Those two and no others.

    **The three failures are one response.** Unknown email, wrong password and
    rate-limited all return `401 authentication_failed` with the same body, the
    same headers and — with one stated exception — the same timing. A
    distinguishable rate-limit response would reintroduce by a side door the
    account-enumeration oracle this module closes everywhere else (A-144,
    ADR-0043). The exception is written at `sessions.sign_in`: a rate-limited
    attempt skips argon2id and is therefore *faster*, which is a fact about the
    attacker's own recent attempts rather than about any account.

    **The session id goes in a cookie and never in the body** — see
    :func:`_issue_session_cookie`. What the body carries is
    :func:`~prope.access_control.sessions.public_session_id`'s digest, which the
    SPA can compare and nobody can authenticate with.

    **It answers the full session envelope rather than three identifiers**, and
    the extra read is bought deliberately: the SPA draws its chrome from the
    person's name, their roles and their workspace's name, so a narrower response
    would be followed by `GET /auth/session` on the very next tick — a second
    round trip, on the one path whose 500 ms budget argon2id has already spent
    70 ms of. The read runs **only on the success branch**, so no failure pays for
    it and the three refusals stay byte- and timing-identical.
    """
    result = await sign_in(
        sessionmaker,
        email=payload.email,
        password=payload.password,
        source_address=_source_address(request),
        user_agent=request.headers.get("user-agent"),
    )

    if result.session is None or result.session_id is None:
        raise ManagementRefusal(
            status_code=401,
            code=ErrorCode.AUTHENTICATION_FAILED,
            message="those credentials are not valid",
        )

    envelope = await _read_session(
        sessionmaker,
        session_id=result.session_id,
        workspace_id=result.session.workspace_id,
    )
    if envelope is None:
        # The row this request committed a moment ago is gone, which means it was
        # deleted between the two statements — a concurrent sign-out or tombstone.
        # Setting the cookie anyway would hand back a credential already known to
        # be dead, so this refuses in the shape the SPA already handles.
        raise ManagementRefusal(
            status_code=401,
            code=ErrorCode.AUTHENTICATION_FAILED,
            message="those credentials are not valid",
        )

    _issue_session_cookie(response, result.session_id, secure=secure_cookie)
    return envelope


@router.post(
    "/auth/register",
    response_model=LoginResponse,
    status_code=201,
    dependencies=[Depends(declares_action(ManagementAction.AUTH_REGISTER))],
)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
    secure_cookie: Annotated[bool, Depends(cookie_secure)],
) -> LoginResponse:
    """Self-serve sign-up. **The second unauthenticated route, and the last.**

    **Why it exists at all.** A-071 rules out invitations and Prope has no
    outbound channel, so before this route an install could be deployed and then
    not signed into: `POST /api/v1/workspaces` and `POST /workspaces/{id}/members`
    both require a session, and nothing could issue the first one. Every other
    door into the product is behind a door.

    **It signs the person in, rather than returning them to the sign-in screen.**
    They have just proved they hold the password by choosing it, and a second
    argon2id verification thirty seconds later would spend 70 ms to learn nothing.
    So the session is issued here, through the same cookie the sign-in path sets,
    and the response is the same envelope — which is why the SPA has one code path
    for "you are now signed in" instead of two.

    **`must_change_password` is false and A-110 is not being weakened.** That flag
    is about a credential an Admin chose and read out loud; a password somebody
    typed into this form is the one case it was never about. See
    `commands.INSERT_SELF_REGISTERED_USER`.

    **The rate limit is the source-address window and deliberately not the email
    one** (`LoginLimiter.record_source_failure`). Counting a failed registration
    against the email would hand anybody who can reach the port an account-lockout
    primitive: five attempts to register an address a real person owns would fill
    their sign-in window. Bulk probing is what is bounded here; a specific victim
    is what must not be reachable.

    **A taken email answers `409` and that is a disclosure, recorded rather than
    hidden.** See `commands.register_account`, which carries the whole argument and
    names `OQ-139`. Sign-in has no such oracle; this route does, and the honest fix
    needs the outbound channel A-071 refuses.
    """
    source_address = _source_address(request)
    refused = process_limiter.check(
        email=payload.email, source_address=source_address, now=None
    )
    if refused is not None:
        # The same refusal a bad sign-in gets, for the same reason the three
        # sign-in failures share one: a distinguishable rate-limit response is an
        # oracle for how much budget is left, which is the first thing a script
        # would read.
        raise ManagementRefusal(
            status_code=401,
            code=ErrorCode.AUTHENTICATION_FAILED,
            message="those credentials are not valid",
        )

    try:
        account = await commands.register_account(
            sessionmaker,
            display_name=payload.display_name,
            email=payload.email,
            password=payload.password,
            now=_utc_now(),
        )
    except ManagementRefusal:
        # Counted against the address only, and counted on **every** refusal
        # rather than only the duplicate-email one: a caller enumerating with
        # malformed workspaces would otherwise probe for free.
        process_limiter.record_source_failure(source_address=source_address)
        raise

    result = await sign_in(
        sessionmaker,
        email=payload.email,
        password=payload.password,
        source_address=source_address,
        user_agent=request.headers.get("user-agent"),
    )
    if result.session is None or result.session_id is None:
        # The account exists and is usable; only the automatic sign-in did not
        # happen, and the one way that is reachable is the address having exhausted
        # its window mid-request. Refusing with the account already committed is
        # correct — the person signs in at the sign-in screen — and inventing a
        # session here would mean issuing one on a path the limiter just refused.
        raise ManagementRefusal(
            status_code=401,
            code=ErrorCode.AUTHENTICATION_FAILED,
            message="those credentials are not valid",
        )

    envelope = await _read_session(
        sessionmaker, session_id=result.session_id, workspace_id=account.workspace_id
    )
    if envelope is None:
        raise ManagementRefusal(
            status_code=401,
            code=ErrorCode.AUTHENTICATION_FAILED,
            message="those credentials are not valid",
        )

    _issue_session_cookie(response, result.session_id, secure=secure_cookie)
    return envelope


@router.get(
    "/auth/session",
    response_model=LoginResponse,
    dependencies=[Depends(declares_action(ManagementAction.AUTH_SESSION))],
)
async def read_session(
    session: Annotated[Session, Depends(require_session)],
    session_cookie: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> LoginResponse:
    """Who the cookie belongs to. **The SPA's first request after every page load.**

    A same-origin `HttpOnly` cookie is invisible to the script that is going to be
    authorised by it, so the SPA cannot know whether it holds a session by looking:
    it has to ask. Without this route the only way to find out is to fire the first
    real request and read the `401`, which means every reload renders the signed-out
    shell for a moment before correcting itself.

    **It is exempt from A-110's forced password change**, and that is required
    rather than convenient: the change-password screen needs the person's name and
    workspace to draw itself, and a session read that answered `403
    password_change_required` would leave the SPA unable to render the one screen
    it is being told to send them to. See
    `session_auth.PASSWORD_CHANGE_EXEMPT_ACTIONS`, which now names three actions.

    **It reads live and caches nothing** (A-114, ADR-0022). `require_session`
    has already performed INT-005's row read; this adds the display fields hanging
    off it, under the tenant the session named.

    A `401` here is the ordinary refusal from `require_session` and means the SPA
    should render the sign-in screen — which is what its `getSession()` treats a
    `401` as, rather than as an error worth showing.
    """
    envelope = None
    if session_cookie:
        envelope = await _read_session(
            sessionmaker, session_id=session_cookie, workspace_id=session.workspace_id
        )

    if envelope is None:
        # `require_session` already answered on this cookie, so reaching here means
        # the row went away between its read and this one. Same refusal, same code:
        # the client's next move is the sign-in screen either way.
        raise ManagementRefusal(
            status_code=401,
            code=SESSION_REQUIRED,
            message="no live session for the presented cookie",
        )
    return envelope


def _source_address(request: Request) -> str:
    """A-144's second bucket key. **`X-Forwarded-For` is deliberately not read.**

    Caddy is the single ingress (A-129), so every request the application sees
    arrives from the proxy and `request.client.host` is the proxy's address —
    which makes this one bucket for the whole install rather than one per client.
    That is **stricter** than A-144 intends: 20 failures per 15 minutes across
    everybody, not per attacker.

    Reading the forwarded header instead would give per-client buckets and would
    also hand the attacker the key: a header trusted without a configured proxy
    allowlist is a limiter turned off by sending a different value each time,
    which is worse than a limiter that is merely blunt. The allowlist is knowable
    — there is exactly one proxy — but it is deployment configuration this phase
    has not written, and the per-email bucket (5 per 15 minutes) is the one doing
    the account-targeted work meanwhile.

    Being wrong in this direction fails loudly: a busy Monday morning locks
    everybody out and somebody notices within minutes. The other direction fails
    silently. `OQ-138` carries the header trust boundary.
    """
    client = request.client
    return client.host if client is not None else "unattributed"


@router.post(
    "/auth/logout",
    status_code=204,
    dependencies=[Depends(declares_action(ManagementAction.AUTH_LOGOUT))],
)
async def logout(
    response: Response,
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
    secure_cookie: Annotated[bool, Depends(cookie_secure)],
) -> None:
    """Delete the session row. **Effective immediately, not at expiry** (ADR-0022).

    Sessions are server-side rows precisely so this is true: there is no token to
    wait out and no cache to invalidate, so the next request presenting the cookie
    gets the same `401` as one presenting a cookie that never existed.

    Deleting **every** session this person holds in this workspace rather than the
    one presented. Signing out is an act somebody performs when they are worried,
    and honouring it narrowly — ending the tab they are looking at and leaving the
    one on the machine they left behind — is the opposite of what they asked for.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await delete_user_sessions(db, session.user_id)

    # The attributes must match the ones the cookie was SET with or the browser
    # keeps it — a delete that quietly failed would leave a dead credential in the
    # jar and the SPA convinced it was still signed in. That is why `secure` is
    # threaded here too rather than left hard-coded: on the laptop target the two
    # would otherwise disagree.
    response.delete_cookie(
        key=SESSION_COOKIE, path="/", httponly=True, secure=secure_cookie, samesite="lax"
    )


@router.post(
    "/auth/password",
    status_code=204,
    dependencies=[Depends(declares_action(ManagementAction.AUTH_PASSWORD))],
)
async def change_password(
    payload: PasswordChange,
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> None:
    """Change your own password, and clear A-110's forced-change flag.

    One of the two routes reachable while `must_change_password` is set — see
    `session_auth.PASSWORD_CHANGE_EXEMPT_ACTIONS`. Refusing this one too would
    lock somebody out of the only door that clears the condition, which is worse
    than not enforcing it at all.

    **No history event.** A password is a credential, and recording its rotation
    would put an authentication fact into the audit trail for the same reason a
    sign-in is kept out of it (A-044, A-039).
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await commands.change_own_password(
            db,
            user_id=session.user_id,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )


# ---------------------------------------------------------------------------
# /workspaces
# ---------------------------------------------------------------------------


@router.post(
    "/workspaces",
    response_model=WorkspaceRead,
    status_code=201,
    dependencies=[Depends(declares_action(ManagementAction.WORKSPACE_CREATE))],
)
async def create_workspace(
    payload: WorkspaceCreate,
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> WorkspaceRead:
    """Create a workspace and its creator's Admin binding, in one transaction.

    **Checks no permission, and that is deliberate** (`NoPermission.SELF_SCOPED`).
    There is nothing to authorise against: the new workspace does not exist yet,
    so no role binding in it can be consulted, and gating on a permission in the
    caller's *current* workspace would make one tenant's Admin the gatekeeper of
    another tenant's existence.

    A-117 is satisfied by construction: the creator's Admin binding is written in
    the same transaction, so a workspace that exists is a workspace with an Admin.
    """
    created = await commands.create_workspace(
        sessionmaker,
        actor_id=session.user_id,
        name=payload.name,
        slug=payload.slug,
        now=_utc_now(),
    )
    return WorkspaceRead(
        workspace_id=created.workspace_id,
        name=created.name,
        slug=created.slug,
        created_at=created.created_at,
    )


@router.get(
    "/workspaces/{id}/members",
    response_model=MemberPage,
    dependencies=[Depends(declares_action(ManagementAction.MEMBER_LIST))],
)
async def list_members(
    workspace_id: Annotated[str, Depends(path_workspace)],
    session: Annotated[Session, Depends(require_session)],
    status: Annotated[MemberStatusFilter, Query()] = MemberStatusFilter.ACTIVE,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
    cursor: Annotated[str | None, Query()] = None,
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> MemberPage:
    """Cursor-paginated (A-045). Keyset on `user_id`, which is a ULID and therefore ordered.

    **A tombstoned member is listed with `email` and `display_name` NULL** and is
    not filtered out. AC-15 requires that no surface *resolves* a tombstoned actor
    to a name; it does not require pretending the person was never here, and
    hiding the row would leave a workspace's history full of ids the member list
    cannot explain. The client renders the absence through a catalogue key
    (ADR-0053).
    """
    async with workspace_transaction(sessionmaker, workspace_id) as db:
        await require_permission(
            db, session, Action.WORKSPACE_MANAGE_MEMBERS, workspace_subject(session)
        )
        rows = (
            await db.execute(
                LIST_MEMBERS,
                {
                    "status": None if status is MemberStatusFilter.ALL else status.value,
                    "cursor": cursor,
                    "limit": limit,
                },
            )
        ).all()

    items = [
        MemberRead(
            user_id=row.user_id,
            email=row.email,
            display_name=row.display_name,
            status=row.status,
            roles=[Role(role) for role in row.roles],
            added_at=row.added_at,
        )
        for row in rows
    ]
    next_cursor = items[-1].user_id if len(items) == limit else None
    return MemberPage(items=items, next_cursor=next_cursor)


@router.post(
    "/workspaces/{id}/members",
    response_model=AddedMember,
    status_code=201,
    dependencies=[Depends(declares_action(ManagementAction.MEMBER_ADD))],
)
async def add_member(
    payload: MemberCreate,
    workspace_id: Annotated[str, Depends(path_workspace)],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> AddedMember:
    """A-110. The account, the membership, the roles, and their events — one transaction.

    The initial password comes back in **this response and nowhere else**. There
    is no invitation email because there is no outbound channel at all (A-071),
    so an Admin reads it out and `must_change_password` makes it temporary.
    """
    now = _utc_now()
    async with workspace_transaction(sessionmaker, workspace_id) as db:
        await require_permission(
            db, session, Action.WORKSPACE_MANAGE_MEMBERS, workspace_subject(session)
        )
        added = await commands.add_member(
            db,
            workspace_id=workspace_id,
            actor_id=session.user_id,
            email=payload.email,
            display_name=payload.display_name,
            roles=payload.roles,
            now=now,
        )

    return AddedMember(
        user_id=added.user_id,
        email=payload.email,
        display_name=payload.display_name,
        roles=list(added.roles),
        initial_password=added.initial_password,
    )


@router.delete(
    "/workspaces/{id}/members/{user_id}",
    status_code=204,
    dependencies=[Depends(declares_action(ManagementAction.MEMBER_REMOVE))],
)
async def remove_member(
    workspace_id: Annotated[str, Depends(path_workspace)],
    user_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> None:
    """Refused with `409` if it would leave the workspace with zero Admins (A-117)."""
    async with workspace_transaction(sessionmaker, workspace_id) as db:
        await require_permission(
            db, session, Action.WORKSPACE_MANAGE_MEMBERS, workspace_subject(session)
        )
        await commands.remove_member(
            db,
            workspace_id=workspace_id,
            actor_id=session.user_id,
            user_id=user_id,
            now=_utc_now(),
        )


@router.put(
    "/workspaces/{id}/members/{user_id}/roles",
    response_model=MemberRoleSet,
    dependencies=[Depends(declares_action(ManagementAction.MEMBER_ROLES_SET))],
)
async def set_member_roles(
    payload: MemberRoleSet,
    workspace_id: Annotated[str, Depends(path_workspace)],
    user_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> MemberRoleSet:
    """Assign or revoke by replacing the whole set. Same zero-Admin refusal (A-117).

    **Self-demotion is permitted and is the realistic route into A-117's failure**
    — one Admin tidying up their own roles. It is refused by the same check that
    refuses removing somebody else, and there is deliberately no extra rule about
    acting on yourself: A-075 records that no person-level segregation exists
    anywhere in Prope, and inventing one here would be the first.
    """
    async with workspace_transaction(sessionmaker, workspace_id) as db:
        await require_permission(
            db, session, Action.WORKSPACE_MANAGE_MEMBERS, workspace_subject(session)
        )
        roles = await commands.set_member_roles(
            db,
            workspace_id=workspace_id,
            actor_id=session.user_id,
            user_id=user_id,
            roles=payload.roles,
            now=_utc_now(),
        )
    return MemberRoleSet(roles=list(roles))


# ---------------------------------------------------------------------------
# /prompts/{prompt_id}/grants — rendered by the registry, written here
# ---------------------------------------------------------------------------


def _prompt_subject(
    session: Session,
    prompt_id: str,
    owner_id: str | None,
    access_level: AccessLevel | None,
) -> Subject:
    """ADR-0020 over HTTP: the SPA passes the attributes it just read.

    In-process callers hand `may()` the row they already have. The SPA is in the
    same position — it rendered the prompt's screen a moment ago — so it passes
    `owner_id` and `access_level` as query parameters and this module still reads
    no table it does not own.

    **A client that lies gets the answer it asked for**, and this is the one place
    where "a caller that would forge it could have skipped the check" is *not* the
    whole defence, because the caller is a browser rather than a module in the
    same process. What bounds it: forging `owner_id` buys only the actions in
    `permissions.OWNER_ACTIONS`, all of which are already available to the Owner
    role workspace-wide; and forging `access_level=workspace` buys read, which is
    what an owner opting a prompt to the workspace grants anyway. Neither reaches
    approve, release, or the credential-bearing actions, because no grant and no
    ownership confers those (A-112). Recorded as `OQ-139` — the honest fix is for
    the registry to proxy these two writes, which contradicts INT-029's own
    placement of them.
    """
    return Subject(
        type=SubjectType.PROMPT,
        id=prompt_id,
        workspace_id=session.workspace_id,
        owner_id=owner_id,
        access_level=access_level,
    )


@router.get(
    "/prompts/{prompt_id}/grants",
    response_model=list[GrantRead],
    dependencies=[Depends(declares_action(ManagementAction.GRANT_LIST))],
)
async def list_grants(
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    owner_id: Annotated[str | None, Query()] = None,
    access_level: Annotated[AccessLevel | None, Query()] = None,
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> list[GrantRead]:
    """Who has been granted access, and at what level.

    Gated on `prompt.read` rather than on `prompt.grant`: seeing who else can see
    a prompt is a read, and requiring the grant permission would hide the list
    from the viewers whose own access it explains.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        subject = _prompt_subject(session, prompt_id, owner_id, access_level)
        await require_permission(db, session, Action.PROMPT_READ, subject)
        rows = (await db.execute(LIST_GRANTS, {"prompt_id": prompt_id})).all()

    return [
        GrantRead(
            prompt_id=row.prompt_id,
            grantee_user_id=row.grantee_user_id,
            level=GrantLevel(row.level),
            granted_by=row.granted_by,
            granted_at=row.granted_at,
        )
        for row in rows
    ]


@router.post(
    "/prompts/{prompt_id}/grants",
    response_model=GrantRead,
    status_code=201,
    dependencies=[Depends(declares_action(ManagementAction.GRANT_CREATE))],
)
async def create_grant(
    payload: GrantCreate,
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    owner_id: Annotated[str | None, Query()] = None,
    access_level: Annotated[AccessLevel | None, Query()] = None,
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> GrantRead:
    """Grant viewer or editor. The grant and its event share one transaction (AC-12)."""
    now = _utc_now()
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        subject = _prompt_subject(session, prompt_id, owner_id, access_level)
        await require_permission(db, session, Action.PROMPT_GRANT, subject)
        level = await commands.grant_access(
            db,
            workspace_id=session.workspace_id,
            actor_id=session.user_id,
            prompt_id=prompt_id,
            grantee_user_id=payload.grantee_user_id,
            level=payload.level,
            now=now,
        )

    return GrantRead(
        prompt_id=prompt_id,
        grantee_user_id=payload.grantee_user_id,
        level=level,
        granted_by=session.user_id,
        granted_at=now,
    )


@router.delete(
    "/prompts/{prompt_id}/grants/{user_id}",
    status_code=204,
    dependencies=[Depends(declares_action(ManagementAction.GRANT_REVOKE))],
)
async def revoke_grant(
    prompt_id: Annotated[str, Path()],
    user_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    owner_id: Annotated[str | None, Query()] = None,
    access_level: Annotated[AccessLevel | None, Query()] = None,
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> None:
    """Revoke. **Effective on the next request**, with no TTL elapsed (A-114, AC-6)."""
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        subject = _prompt_subject(session, prompt_id, owner_id, access_level)
        await require_permission(db, session, Action.PROMPT_GRANT, subject)
        await commands.revoke_access(
            db,
            workspace_id=session.workspace_id,
            actor_id=session.user_id,
            prompt_id=prompt_id,
            grantee_user_id=user_id,
            now=_utc_now(),
        )


# ---------------------------------------------------------------------------
# /workspaces/{id}/keys
# ---------------------------------------------------------------------------


@router.get(
    "/workspaces/{id}/keys",
    response_model=list[KeyRead],
    dependencies=[Depends(declares_action(ManagementAction.KEY_LIST))],
)
async def list_keys(
    workspace_id: Annotated[str, Depends(path_workspace)],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> list[KeyRead]:
    """`id, name, last_four, scope, last_used_at, created_by`. **Never the secret.**

    This list is the reason `api_key` keeps its tenant policy rather than being
    exempted along with the authentication path (ADR-0042): a forgotten filter
    here is precisely the silent cross-tenant read ADR-0035 exists to convert into
    zero rows. There is no `WHERE workspace_id = ...` below, and that is not an
    omission — the policy is the filter, and it applies whether or not anybody
    remembered it.
    """
    async with workspace_transaction(sessionmaker, workspace_id) as db:
        await require_permission(
            db, session, Action.WORKSPACE_MANAGE_KEYS, workspace_subject(session)
        )
        rows = (await db.execute(LIST_KEYS)).all()

    return [
        KeyRead(
            key_id=row.id,
            name=row.name,
            last_four=row.last_four,
            scope_model_names=list(row.scope_model_names),
            created_by=row.created_by,
            created_at=row.created_at,
            revoked_at=row.revoked_at,
            last_used_at=row.last_used_at,
        )
        for row in rows
    ]


@router.post(
    "/workspaces/{id}/keys",
    response_model=CreatedKey,
    status_code=201,
    dependencies=[Depends(declares_action(ManagementAction.KEY_CREATE))],
)
async def create_key(
    payload: KeyCreate,
    workspace_id: Annotated[str, Depends(path_workspace)],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> CreatedKey:
    """**The plaintext appears in this response and nowhere else, ever** (A-113, AC-7)."""
    now = _utc_now()
    async with workspace_transaction(sessionmaker, workspace_id) as db:
        await require_permission(
            db, session, Action.WORKSPACE_MANAGE_KEYS, workspace_subject(session)
        )
        minted = await commands.create_api_key(
            db,
            workspace_id=workspace_id,
            actor_id=session.user_id,
            name=payload.name,
            scope_model_names=payload.scope_model_names,
            now=now,
        )

    return CreatedKey(
        key_id=minted.key_id,
        name=payload.name,
        last_four=minted.last_four,
        scope_model_names=list(payload.scope_model_names),
        created_at=now,
        secret=minted.plaintext,
    )


@router.delete(
    "/workspaces/{id}/keys/{key_id}",
    status_code=204,
    dependencies=[Depends(declares_action(ManagementAction.KEY_REVOKE))],
)
async def revoke_key(
    workspace_id: Annotated[str, Depends(path_workspace)],
    key_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> None:
    """Revoke, effective on the next request (A-114). The row survives with a timestamp."""
    async with workspace_transaction(sessionmaker, workspace_id) as db:
        await require_permission(
            db, session, Action.WORKSPACE_MANAGE_KEYS, workspace_subject(session)
        )
        await commands.revoke_api_key(
            db,
            workspace_id=workspace_id,
            actor_id=session.user_id,
            key_id=key_id,
            now=_utc_now(),
        )


# ---------------------------------------------------------------------------
# /permissions and /users/{user_id}/tombstone
# ---------------------------------------------------------------------------


@router.get(
    "/permissions",
    response_model=PermissionMatrix,
    dependencies=[Depends(declares_action(ManagementAction.PERMISSION_MATRIX_READ))],
)
async def read_permission_matrix(
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> PermissionMatrix:
    """The running `(role, action)` matrix, as data. **This is OQ-006's check.**

    Reads `access.role_permission` rather than serialising the `Action` enum,
    because the point is to see what is *installed* — including a row a migration
    added that this build has never heard of, which is exactly the drift worth
    surfacing.

    No permission (`NoPermission.PUBLIC_TO_MEMBERS`). The matrix is a global table
    with no tenant column and no secret in it, and gating it would make the check
    that proves OQ-006's answer was applied readable only by the role the answer
    is about.
    """
    async with sessionmaker() as db:
        rows = (await db.execute(LOAD_PERMISSION_MATRIX)).all()

    permissions = [PermissionRow(role=Role(row.role), action=row.action) for row in rows]
    return PermissionMatrix(
        roles=sorted({row.role for row in permissions}, key=lambda role: role.value),
        actions=sorted({row.action for row in permissions}),
        permissions=permissions,
    )


@router.post(
    "/users/{user_id}/tombstone",
    status_code=204,
    dependencies=[Depends(declares_action(ManagementAction.USER_TOMBSTONE))],
)
async def tombstone_user(
    user_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> None:
    """ADR-0054. **The only route in Prope that destroys data, and it is irreversible.**

    Gated on `user.tombstone`, which is a separate action from
    `workspace.manage_members` on purpose: removing a person from a workspace is
    reversible and workspace-scoped, while erasing an account is neither, and one
    permission covering both would let a workspace admin erase somebody who still
    works elsewhere in the group (A-115).

    Refused with `409` while the person still holds an **active membership**
    anywhere. Each removal writes its own `member_removed` event in its own
    workspace; the tombstone is the account-level act that follows, and keeping
    them separate is what stops one ambiguous event standing for both.

    **It touches no `history_event` row that already exists**, which is the whole
    of the decision. `prope_app` could not do so if it tried (ADR-0025), and
    `tests/integration/test_tombstone_leaves_the_trail_intact.py` asserts the
    count of rows naming that actor is unchanged.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await require_permission(db, session, Action.USER_TOMBSTONE, workspace_subject(session))

    await commands.tombstone_user(
        sessionmaker, actor_id=session.user_id, user_id=user_id, now=_utc_now()
    )
