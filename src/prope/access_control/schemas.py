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
    "MAX_KEY_NAME_LENGTH",
    "MAX_PASSWORD_LENGTH",
    "MIN_PASSWORD_LENGTH",
    "AddedMember",
    "Email",
    "CreatedKey",
    "GrantCreate",
    "GrantRead",
    "KeyCreate",
    "KeyRead",
    "LoginRequest",
    "LoginResponse",
    "MemberPage",
    "MemberRead",
    "MemberRoleSet",
    "MemberCreate",
    "PasswordChange",
    "PermissionMatrix",
    "PermissionRow",
    "WorkspaceCreate",
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


class LoginResponse(BaseModel):
    """What a successful sign-in returns. **The session id is not in it.**

    The cookie carries it, `HttpOnly` so no script can read it (ADR-0052). A body
    field would put a bearer credential somewhere `localStorage` can hold it and a
    crash reporter can ship it, which is the whole reason ADR-0029 chose a cookie.

    `must_change_password` is a hint for the SPA's routing, not the enforcement:
    `require_session` refuses every other route while it is true, so a client that
    ignored this field would get a `403` rather than a working session.
    """

    model_config = ConfigDict(extra="forbid")

    user_id: str
    workspace_id: str
    must_change_password: bool


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
    """`POST /api/v1/workspaces`. Name and slug; the id is the server's (A-045)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    #: Mirrors `ck_workspace_slug_format`, so a malformed slug is refused before a
    #: transaction opens rather than as a driver error two layers down.
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str
    name: str
    slug: str
    created_at: AwareDatetime


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
    """The `status` query parameter on the member list. Closed, like everything else."""

    ACTIVE = "active"
    REMOVED = "removed"
    ALL = "all"
