"""INT-029's wire types. Shape only — every refusal with a *reason* lives in `api.py`.

Same rule `prope.call_ledger.schemas` states and for the same reason: a
`model_validator` collapses every refusal into one `validation_failed`, and
ADR-0053 makes the `code` the thing the client actually renders, so a merged code
is a message the SPA cannot write.

**Three things are absent from every model here and their absence is the
security property.**

* **No password is ever a response field.** `PasswordChange` accepts two and
  returns nothing. The one credential that crosses outward is
  :class:`CreatedKey.secret`, once, and :class:`AddedMember.initial_password`,
  once — both on creation responses, both unrecoverable afterwards (A-113, A-110).
* **No `workspace_id` is ever a request field.** It comes from the session, because
  a caller able to name the workspace is a caller able to name another one, and
  the tenant seam takes exactly one workspace per transaction (ADR-0040).
* **No model carries a `password_hash`, a `key_hash`, or a session id**, and none
  ever may. `tests/security/test_key_secret_shown_once_only.py` asserts the second
  over the assembled OpenAPI schema rather than by inspection.

**Statuses and roles stay literal** (ADR-0053 rule 9). `Draft`, `Admin`,
`tombstoned`, `viewer` are **values**, not words: they are stored as written,
transmitted as written, and translated only at the point of display. No code
anywhere compares a translated label.
"""

from enum import StrEnum
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from prope.access_control.domain import GrantLevel, Role

__all__ = [
    "MAX_INVITE_USES",
    "MAX_KEY_NAME_LENGTH",
    "MAX_PASSWORD_LENGTH",
    "MIN_PASSWORD_LENGTH",
    "AddedMember",
    "Email",
    "CreatedKey",
    "GrantCreate",
    "GrantRead",
    "InviteCreate",
    "InviteCreated",
    "InviteRead",
    "InviteRedeem",
    "InviteRedeemed",
    "KeyCreate",
    "KeyRead",
    "KeyScopeUpdate",
    "LoginRequest",
    "LoginResponse",
    "MemberApproval",
    "MemberPage",
    "MemberRead",
    "MemberRoleSet",
    "MemberCreate",
    "NamespaceGrantCreate",
    "NamespaceGrantRead",
    "PasswordChange",
    "PermissionMatrix",
    "PermissionRow",
    "RegisterRequest",
    "SessionRead",
    "SessionUser",
    "WorkspaceCreate",
    "WorkspaceMembershipList",
    "WorkspaceMembershipRead",
    "WorkspaceRead",
]

#: An email as Prope treats it: **an identifier, not an address.**
#:
#: `pydantic.EmailStr` was the obvious choice and is not taken. It requires the
#: `email-validator` package, whose job is to assert an address is *deliverable* —
#: syntax against RFC 5321, and optionally a DNS lookup. Prope has **no outbound
#: channel at all** (A-071): no invitation email, no notification, no password
#: reset. Nothing here will ever send to this string; it exists to be typed into a
#: sign-in box and matched against `uq_user_email`. Buying a dependency, and a
#: dependency that can reach DNS, to validate a property the product does not use
#: is the wrong trade — and a stricter validator would refuse addresses a group's
#: internal mail system happily issues, which is a support ticket for no benefit.
#:
#: So: bounded length, exactly one `@`, no whitespace. That is enough to catch a
#: transposed field or a pasted display name, and it makes no claim it cannot
#: keep. Revisit if A-071 is ever reversed — the moment Prope sends mail,
#: deliverability becomes a property worth asserting.
Email = Annotated[str, Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+$")]

#: **A floor and no complexity rule.** OWASP's own guidance is that length is the
#: property worth requiring and that character-class rules push people toward
#: `Password1!` — a pattern an attacker's dictionary already contains. argon2id at
#: ADR-0043's cost is what makes a 12-character passphrase expensive to attack;
#: a symbol requirement would make it memorable instead, which is the opposite.
MIN_PASSWORD_LENGTH = 12

#: A ceiling, because argon2id hashes whatever it is given and a 10 MB "password"
#: is a request that allocates 46 MiB *and* reads 10 MB before it does. The
#: limiter bounds how many of those the box will run; this bounds how big one is.
MAX_PASSWORD_LENGTH = 256

MAX_KEY_NAME_LENGTH = 120

#: A ceiling on a code invitation's `max_uses`, and it is a bound on a number the
#: caller supplies rather than a policy about team size. `None` still means
#: unlimited within the hour — the field exists for an Admin who wants "this code
#: admits three people", and a caller sending 2**31 would be storing an integer
#: nobody meant.
MAX_INVITE_USES = 1000


class LoginRequest(BaseModel):
    """`POST /api/v1/auth/login`. The one unauthenticated body in the management API.

    `email` is validated for shape and **not normalised**. It deliberately does
    **not** lower-case: the limiter is keyed on this string, and folding case here
    while `access.user.email` stores it as written would give one account two
    limiter buckets — five attempts against `A@x` and five more against `a@x`.
    Callers send what the person typed and the unique index decides.
    """

    model_config = ConfigDict(extra="forbid")

    email: Email
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class RegisterRequest(BaseModel):
    """`POST /api/v1/auth/register`. The **second** unauthenticated body, and the last.

    Self-serve sign-up creates **a person and nothing else** (ADR-0056). Prope has
    no outbound channel (A-071), so this is the only door into an install that has
    no accounts yet — without it, `POST /api/v1/workspaces` requires a session that
    nothing can issue, and the product has no first user.

    **There is no workspace field, because registration creates no workspace.** It
    used to mint one named after the person, which meant somebody whose only reason
    for signing up was to join a colleague owned a junk workspace forever. The
    session it issues names none and the chooser is the next screen.

    **One exception, and it is invisible from here**: if an Admin has reserved a
    seat for this address (`InviteCreate` with an `email`),
    `commands.claim_email_invites` turns it into a membership before the session is
    issued — so the person lands in the workspace they were invited to rather than
    on the chooser. Nothing in this body says so, which is correct: the client
    reads `user.workspace_id` from the response either way.

    `email` is not normalised, for `LoginRequest`'s reason exactly: the limiter is
    keyed on this string and the unique index decides. The invitation lookup folds
    **its own** copy rather than this one.
    """

    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=200)
    email: Email
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)


class SessionUser(BaseModel):
    """Who the session belongs to, as the SPA's chrome needs them.

    **`roles` is a list and not a role.** A person holds a set of role bindings in
    a workspace (`access.role_binding` has no uniqueness on `user_id`), and
    collapsing them to one here would mean this module deciding which of somebody's
    roles is *the* one — a product judgement dressed as a serialisation detail, and
    one that would quietly disagree with `GET /api/v1/permissions`. The SPA picks
    what to print on the account chip; the API reports what is bound.

    **No permission set travels with it.** A client that received one would render
    from it, and then the enforcement question — which `may()` answers per subject,
    against a row it reads at the moment of the act — would have a second, stale
    answer somebody could be tempted to trust (A-114).

    **`workspace_id` and `workspace_name` are `None` together, and that is the
    lobby** (ADR-0056). The person is signed in and in no workspace — because they
    belong to none yet, or belong to several and have not picked. The SPA reads
    this pair to decide between the chooser and the app shell, which is why it is
    two nullable fields rather than an absent object: a client that had to
    distinguish "key missing" from "key null" would have two ways to get one
    question wrong. `roles` is empty in that state for the same reason it is empty
    for a member nobody has assigned yet — there is no workspace for a binding to
    exist in.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    display_name: str
    email: str
    roles: list[Role] = Field(default_factory=list)
    workspace_id: str | None = None
    workspace_name: str | None = None


class SessionRead(BaseModel):
    """What `GET /api/v1/auth/session` answers, and what a sign-in returns.

    **One shape for three routes** — session read, login, register — because the
    SPA's session store is populated from all three and a client that had to
    normalise two shapes into one would be a client with two places to get it
    wrong. `LoginResponse` is an alias of this class for that reason.

    **The session id in `id` is not the cookie.** `access.session.id` *is* the
    bearer credential (ADR-0029), so what travels here is a non-reversible digest
    prefix of it: enough for the SPA to tell one session from another across a
    re-authentication, useless to anybody who intercepts the body. A client that
    only needs "did the session change" gets that; a client that wanted to
    authenticate with it cannot. The cookie remains the only carrier of the real
    value, `HttpOnly` so no script reads it.

    `expires_at` is the row's own ceiling and not a heartbeat — sign-out, member
    removal and the tombstone all delete the row and take effect on the next
    request (ADR-0022), so the SPA may use this to pre-empt an expiry and may
    never treat it as proof the session is still live.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    expires_at: AwareDatetime
    must_change_password: bool
    user: SessionUser


#: What a successful sign-in returns. **The session id is not in it.**
#:
#: The cookie carries it, `HttpOnly` so no script can read it (ADR-0052). A body
#: field would put a bearer credential somewhere `localStorage` can hold it and a
#: crash reporter can ship it, which is the whole reason ADR-0029 chose a cookie —
#: and `SessionRead.id` is a digest for exactly that reason.
#:
#: `must_change_password` is a hint for the SPA's routing, not the enforcement:
#: `require_session` refuses every other route while it is true, so a client that
#: ignored this field would get a `403` rather than a working session.
#:
#: **An alias rather than its own class, since the SPA reads one shape.** It was a
#: distinct three-field model until the SPA existed and needed the person's name
#: and workspace to draw its chrome — at which point login answering less than
#: `GET /auth/session` would have forced a second round trip immediately after
#: every sign-in, to read what the sign-in already knew.
LoginResponse = SessionRead


class PasswordChange(BaseModel):
    """`POST /api/v1/auth/password`. Both passwords, and nothing comes back.

    The current one is required even though the caller holds a session — see
    `commands.change_own_password` for why that second argon2id verification is
    worth its 60 ms on this route and on no other.
    """

    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)


class WorkspaceCreate(BaseModel):
    """`POST /api/v1/workspaces`. A name, optionally a slug; the id is the server's (A-045)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    #: Mirrors `ck_workspace_slug_format`, so a malformed slug is refused before a
    #: transaction opens rather than as a driver error two layers down.
    #:
    #: **Optional since ADR-0056**, and omitting it is what the chooser does. A
    #: slug field on the create-a-workspace form is a field whose refusal — *"that
    #: one is taken"* — tells the person what other workspaces exist in the
    #: install, which is BR-01's disclosure arriving through a door nobody thought
    #: of as a read. `commands.derive_workspace_slug` salts one from the name
    #: instead, so two people who both call their workspace "Marketing" both
    #: succeed. It stays accepted because an Admin naming a second workspace for
    #: colleagues to read is choosing something, and that case is not this one.
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str
    name: str
    slug: str
    created_at: AwareDatetime


class WorkspaceMembershipRead(BaseModel):
    """One row of the workspace chooser. ADR-0056.

    **`status` is `active` or `pending` and never `removed`.** A workspace somebody
    was removed from is not theirs to see; one they have asked to join is, or the
    chooser would say nothing happened while a request sits in somebody's queue.

    **`roles` is empty for every pending row**, because roles are bound at the
    moment of approval. The client renders the difference from `status` and not
    from the emptiness — a member an Admin has not assigned yet has no roles
    either, and the two are not the same state.

    Statuses and roles stay literal (ADR-0053 rule 9): the client translates them,
    and no code anywhere compares a translated label.
    """

    model_config = ConfigDict(extra="forbid")

    workspace_id: str
    name: str
    slug: str
    status: str
    roles: list[Role] = Field(default_factory=list)
    added_at: AwareDatetime


class WorkspaceMembershipList(BaseModel):
    """`GET /api/v1/auth/workspaces`. Every workspace this person is in or waiting on.

    **Not paginated, unlike `MemberPage`.** A-045's cursor rule is about lists that
    grow with a workspace's data; this one grows with how many workspaces one
    person belongs to, which is a number with a human being at the top of it. A
    cursor here would be machinery for a page that will never have a second one.

    `current_workspace_id` is the workspace the caller's session names, or `None`
    in the lobby. It is echoed here so the chooser can mark the current row without
    a second call to `GET /auth/session` — the two are read from the same session,
    in the same request, so they cannot disagree.
    """

    model_config = ConfigDict(extra="forbid")

    items: list[WorkspaceMembershipRead]
    current_workspace_id: str | None = None


class MemberCreate(BaseModel):
    """`POST /api/v1/workspaces/{id}/members`. An Admin creating an account (A-110).

    `roles` may be empty: a member with no role can sign in, see nothing, and be
    given a role later. That is a real state during onboarding and refusing it
    would push Admins toward granting `Viewer` reflexively.
    """

    model_config = ConfigDict(extra="forbid")

    email: Email
    display_name: str = Field(min_length=1, max_length=200)
    roles: list[Role] = Field(default_factory=list)


class AddedMember(BaseModel):
    """The creation response. `initial_password` appears **here and nowhere else**.

    It is `None` when the email already belonged to an account — that person is
    being added to a second workspace and their credentials are untouched. The
    SPA has to render two different screens for the two cases, which is why the
    field is nullable rather than absent.
    """

    model_config = ConfigDict(extra="forbid")

    user_id: str
    email: Email
    display_name: str
    roles: list[Role]
    initial_password: str | None = None


class MemberRead(BaseModel):
    """One row of the member list. **No email for a tombstoned person, ever** (AC-15).

    `display_name` and `email` are `None` for a tombstoned account, because the
    columns are NULL — the absence is rendered by the client through a catalogue
    key rather than by this API inventing a string like "Removed user", which
    would be literal display text crossing the wire against ADR-0053.
    """

    model_config = ConfigDict(extra="forbid")

    user_id: str
    email: Email | None = None
    display_name: str | None = None
    status: str
    roles: list[Role]
    added_at: AwareDatetime


class MemberPage(BaseModel):
    """A-045's cursor pagination. `next_cursor` is `None` on the last page."""

    model_config = ConfigDict(extra="forbid")

    items: list[MemberRead]
    next_cursor: str | None = None


class MemberApproval(BaseModel):
    """`POST /api/v1/workspaces/{id}/members/{user_id}/approve`. **The human gate.**

    `roles` is the approver's decision and not the invitation's. The invitation's
    `grants_roles` pre-fills this field in the client and binds nothing here — an
    hour can pass between an Admin creating a code and finding out who used it, and
    the person who decides should be the one looking at the name.

    An empty list is legal, for `MemberCreate`'s reason: somebody let in and not yet
    assigned is a real state, and refusing it would push Admins toward granting
    `Viewer` reflexively.
    """

    model_config = ConfigDict(extra="forbid")

    roles: list[Role] = Field(default_factory=list)


class InviteCreate(BaseModel):
    """`POST /api/v1/workspaces/{id}/invites`. **Two kinds, one body, one row.**

    `email` present is an invitation for one named person, claimed the moment that
    address signs in or registers, and it grants `roles` outright — an Admin naming
    somebody is the same decision `POST /members` records.

    `email` absent mints a **code**, which grants nothing on its own: whoever
    redeems it lands in the pending queue and an Admin approves them
    (:class:`MemberApproval`). `roles` on a code is what that approval screen
    pre-selects.

    `max_uses` applies to codes only. `None` is unlimited **within the hour** the
    code lives, which is safe precisely because a redemption is a knock rather than
    an entry. An email invitation is one seat for one person and ignores it.
    """

    model_config = ConfigDict(extra="forbid")

    email: Email | None = None
    roles: list[Role] = Field(default_factory=list)
    max_uses: int | None = Field(default=None, ge=1, le=MAX_INVITE_USES)


class InviteCreated(BaseModel):
    """The creation response. `code` appears **here and nowhere else**.

    Only its SHA-256 is stored, so there is no path that recovers it — losing it
    means creating another, which is one click and the correct outcome. `None` for
    an email invitation, which has no code at all.
    """

    model_config = ConfigDict(extra="forbid")

    invite_id: str
    code: str | None = None
    invited_email: Email | None = None
    roles: list[Role]
    created_at: AwareDatetime
    expires_at: AwareDatetime
    max_uses: int | None = None


class InviteRead(BaseModel):
    """One row of the invitations list. **The code is not in it and cannot be.**

    `status` is derived rather than stored: `live`, `revoked`, `expired` or
    `exhausted`, computed from `revoked_at`, `expires_at` and the two use counts.
    A stored status column would need a job to move it to `expired`, and Prope has
    no scheduled work at all (`access-control.lock.yml`'s `deployment_target`) — so
    the derivation is not a shortcut, it is the only version that cannot go stale.

    Statuses stay literal (ADR-0053 rule 9); the client translates them.
    """

    model_config = ConfigDict(extra="forbid")

    invite_id: str
    invited_email: Email | None = None
    roles: list[Role]
    status: str
    created_by: str
    created_at: AwareDatetime
    expires_at: AwareDatetime
    revoked_at: AwareDatetime | None = None
    max_uses: int | None = None
    use_count: int


class InviteRedeem(BaseModel):
    """`POST /api/v1/auth/invites/redeem`. One field, and it is a credential.

    Bounded at a generous length rather than pinned to `CODE_LENGTH`: a body of the
    wrong size must reach the same refusal every other bad code gets, and a `422`
    from pydantic would be a shape the client can tell apart from `404`. Trimming
    is `invites.normalise_code`'s job, and case is preserved — the alphabet is
    case-sensitive.
    """

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=64)


class InviteRedeemed(BaseModel):
    """Where the code led, and what state the caller is now in.

    `status` is `pending` for a code that was accepted and `active` when the caller
    turns out to be a member already. Both are `200`s: re-presenting a code you
    already redeemed must not read as a failure, or a person who reloads the page
    sees an error for something that worked.

    **`workspace_name` crosses to somebody who is not a member yet**, and that is
    the disclosure this route accepts. It is bounded by holding the code: the name
    is what the chooser has to render for a workspace the person is waiting on, and
    a pending row with no name is a row nobody can act on.
    """

    model_config = ConfigDict(extra="forbid")

    workspace_id: str
    workspace_name: str
    status: str


class MemberRoleSet(BaseModel):
    """`PUT .../members/{user_id}/roles`. The whole set, not a patch.

    See `commands.set_member_roles`: with a partial update, *"I did not mention
    Admin"* and *"I want Admin removed"* are indistinguishable, and one of those
    two is the operation A-117 exists to refuse.
    """

    model_config = ConfigDict(extra="forbid")

    roles: list[Role]


class GrantCreate(BaseModel):
    """`POST /api/v1/prompts/{prompt_id}/grants`. Viewer or editor, and no more.

    A-112's ceiling is expressed by the type: `GrantLevel` has two members, so
    there is no request body that could ask for a grant conferring approve,
    release, withdraw or break-glass.
    """

    model_config = ConfigDict(extra="forbid")

    grantee_user_id: str = Field(min_length=1)
    level: GrantLevel


class GrantRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_id: str
    grantee_user_id: str
    level: GrantLevel
    granted_by: str
    granted_at: AwareDatetime


class NamespaceGrantCreate(BaseModel):
    """`POST /api/v1/namespaces/{namespace}/grants`. ADR-0061, A-112's ceiling intact.

    The same two levels as a prompt grant and for the same reason: `GrantLevel`
    has two members, so there is no request body that could ask for a grant
    conferring approve, release, withdraw or break-glass — one scope up, over
    every prompt in a folder, that ceiling matters more rather than less.
    """

    model_config = ConfigDict(extra="forbid")

    grantee_user_id: str = Field(min_length=1)
    level: GrantLevel


class NamespaceGrantRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    namespace: str
    grantee_user_id: str
    level: GrantLevel
    granted_by: str
    granted_at: AwareDatetime


class KeyCreate(BaseModel):
    """`POST /api/v1/workspaces/{id}/keys`. Explicit, default-deny scope (A-081).

    An empty `scope_model_names` is legal and resolves nothing — useful for
    provisioning a consumer before deciding what it may reach. The failure a
    consumer then sees is a not-found indistinguishable from an unknown model
    name, which is A-116's rule at the gateway and is deliberate.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=MAX_KEY_NAME_LENGTH)
    scope_model_names: list[str] = Field(default_factory=list)
    #: A-158's other half, available at mint time because a folder scope is the
    #: normal way to provision a product that owns one — naming a thousand model
    #: names is what this replaces, and forcing a second call to do it would be
    #: the friction the assumption exists to remove.
    #:
    #: The `observe_*` pair is deliberately NOT here. See `INSERT_API_KEY`.
    scope_namespaces: list[str] = Field(default_factory=list)


class KeyScopeUpdate(BaseModel):
    """`PUT /api/v1/workspaces/{id}/keys/{key_id}/scope`. The whole list, every time.

    Not an add/remove pair, for the reason in `commands.set_api_key_scope`: a
    delta makes the caller's stale view of the scope part of the protocol. An
    empty list is legal and narrows the key to nothing, which is the same
    default-deny state a key is minted in (A-081) — and is the fastest way to
    neutralise a credential without revoking it.
    """

    model_config = ConfigDict(extra="forbid")

    scope_model_names: list[str] = Field(default_factory=list)

    #: A-158. One entry here replaces the thousand `scope_model_names` a product
    #: that owns a folder would otherwise need. Union, not intersection: INT-004
    #: resolves a name in `scope_model_names` OR whose namespace is in this, and
    #: both empty is default-deny by the same mechanism as before — `= ANY('{}')`
    #: is false for every input, so there is still no branch anybody could forget.
    scope_namespaces: list[str] = Field(default_factory=list)

    #: A-152 / ADR-0062 §3. The observe pair, set together or not at all — the
    #: command refuses a half-set pair with a 422 and
    #: `ck_api_key_observe_is_all_or_nothing` refuses it again underneath. Both
    #: absent means the key behaves exactly as it did before ADR-0059: a model
    #: name the registry does not know is a not-found, and nothing is forwarded.
    #:
    #: **A PUT that omits them CLEARS them**, which follows from this route
    #: replacing the whole scope wholesale rather than patching it. That is the
    #: safe direction for a capability whose failure mode is *traffic quietly went
    #: somewhere* — a client that has not been updated turns observation off
    #: rather than leaving it on invisibly.
    observe_provider_config_id: str | None = Field(default=None, min_length=1, max_length=64)
    observe_namespace: str | None = Field(
        default=None, pattern=r"^[a-z0-9][a-z0-9._-]{0,62}$", max_length=63
    )


class CreatedKey(BaseModel):
    """The creation response, and the **only** place `secret` ever appears (AC-7).

    It is not recoverable from the stored row: `access.api_key` keeps a SHA-256
    digest, four display characters and nothing else (ADR-0021). Losing it means
    issuing a new key, which is a two-click operation and the correct outcome —
    and the screen that shows this has to be a copy-once screen rather than a
    toast, or the first support ticket is somebody who closed the tab.
    """

    model_config = ConfigDict(extra="forbid")

    key_id: str
    name: str
    last_four: str
    scope_model_names: list[str]
    scope_namespaces: list[str] = Field(default_factory=list)
    created_at: AwareDatetime
    #: Shown once. Never logged, never in an event, never readable again.
    secret: str


class KeyRead(BaseModel):
    """A key as every *other* endpoint returns it. There is no `secret` field.

    `last_used_at` is the weak signal ADR-0021 calls weak: it shows a key is
    alive, not that it is in the wrong hands. Real detection needs per-key call
    volume, which the ledger already records and no screen yet reads — a later
    feature, not a claim made here. It stays NULL until phase 19 wires
    `bootstrap.record_key_use` (OQ-136).
    """

    model_config = ConfigDict(extra="forbid")

    key_id: str
    name: str
    last_four: str
    scope_model_names: list[str]
    created_by: str
    created_at: AwareDatetime
    revoked_at: AwareDatetime | None = None
    last_used_at: AwareDatetime | None = None
    #: ADR-0061 and ADR-0059. Read back because a key's reach is the one thing
    #: about it that is meant to be visible — `secret` is not here and never will
    #: be (AC-7), and `observe_provider_config_id` names a CONFIGURATION rather
    #: than a credential, so returning it discloses nothing the providers screen
    #: does not already show.
    scope_namespaces: list[str] = Field(default_factory=list)
    observe_provider_config_id: str | None = None
    observe_namespace: str | None = None


class PermissionRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Role
    action: str


class PermissionMatrix(BaseModel):
    """`GET /api/v1/permissions` — the running `(role, action)` matrix as data.

    **This endpoint is how OQ-006's answer gets checked.** The matrix is a seeded
    table so a different matrix is a re-seed rather than a release; this renders
    what is actually installed, so the signed-off matrix can be diffed against the
    running one instead of against a document describing it.

    `action` is a bare `str` and not the `Action` enum on purpose. The point of
    reading the *running* matrix is to see what is really there — including a row
    a migration added that this build's enum has never heard of, which is exactly
    the drift the endpoint exists to surface. Typing it would have hidden it
    behind a validation error.
    """

    model_config = ConfigDict(extra="forbid")

    roles: list[Role]
    actions: list[str]
    permissions: list[PermissionRow]


class MemberStatusFilter(StrEnum):
    """The `status` query parameter on the member list. Closed, like everything else.

    `PENDING` arrived with ADR-0057 and **is the approval queue** — there is no
    endpoint for one, because the member list with a filter already answers the
    question and a second route would be a second projection of the same rows.
    """

    ACTIVE = "active"
    REMOVED = "removed"
    PENDING = "pending"
    ALL = "all"
