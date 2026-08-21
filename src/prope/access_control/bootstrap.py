"""INT-003 and INT-005 — the two reads that run *before* a tenant is known.

**These are the only two code paths in Prope that bypass row-level security, and
they bypass it through named functions rather than through an absent policy or a
role** (ADR-0042). `access.session` and `access.api_key` both carry
`workspace_id` and both are policied; but the reads below are what *produce*
`app.workspace_id`, so they cannot consume it. Under the policy with nothing set,
`current_setting('app.workspace_id', true)` is NULL, the predicate is NULL, and
the row is filtered out — which would make **every authenticated request in
Prope fail, gateway included**.

`access.lookup_session` and `access.lookup_api_key` are the escape, and every
property of them is a mitigation: owned by `prope_migrate`, empty `search_path`,
`REVOKE`d from `PUBLIC`, and returning an **identity tuple** rather than a row
set. See revision 0006.

**The hash comparison stays here, in Python, and that is load-bearing.**
`lookup_api_key` returns the stored hash; it does not authenticate. A
`SECURITY DEFINER` object with a security decision inside it is a much worse
thing than a lookup — a defect in its body is an authentication bypass with the
policy already off. So the function finds the row and this module decides
(ADR-0042, A-113).

**Both open their own session with no tenant set**, which is the opposite of
`may()` one file over. That asymmetry is the whole reason this file is separate:
a seam that runs before tenancy exists cannot take a caller's tenant-scoped
transaction, and a seam that runs after must not open a second one.

**Nothing here is cached** (A-114, ADR-0022). A revoked key's `revoked_at` comes
back in the same tuple as the hash, and the refusal is this module's, on the next
request, with no TTL to wait out.
"""

import time
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.keys import parse_presented_key, secrets_match
from prope.access_control.observability import (
    key_auth_duration_seconds,
    key_auth_total,
)
from prope.db.session import workspace_transaction
from prope.session_auth import ActorSession

__all__ = [
    "AuthenticatedKey",
    "authenticate_api_key",
    "authenticate_session",
    "record_key_use",
]

#: INT-005. Two columns, and the function itself applies `expires_at > now()` —
#: an expired row is never returned even while it is still present, which is what
#: lets this module have no scheduled job (the lock file's `deployment_target`).
LOOKUP_SESSION = text("SELECT user_id, workspace_id FROM access.lookup_session(:id)")

#: INT-003. `revoked_at` travels with the hash rather than being filtered inside
#: the function, so a revoked key is a *decision* here and not an absent row —
#: the two are counted differently (`result=revoked` vs `result=unknown`) even
#: though they answer identically on the wire.
LOOKUP_API_KEY = text(
    """
    SELECT workspace_id, key_id, key_hash, scope_model_names, scope_namespaces,
           observe_provider_config_id, observe_namespace, revoked_at
    FROM   access.lookup_api_key(:key_id)
    """
)

#: The one write on the authentication path, and it is deliberately NOT issued by
#: :func:`authenticate_api_key`. See :func:`record_key_use`.
TOUCH_API_KEY = text(
    "UPDATE access.api_key SET last_used_at = now() WHERE id = ANY(:key_ids)"
)

#: A person's whole authority is this row, and the row is read live on every
#: request (ADR-0022, ADR-0029). `must_change_password` rides along because
#: A-110 forces a change at first sign-in and the enforcement has to happen at
#: the session boundary — a person who never visits the change-password screen
#: must not simply keep the password an Admin read out to them.
#:
#: `access."user"` carries no tenant column and no policy (ADR-0045), so this
#: needs no `SECURITY DEFINER` escape and gets none.
LOAD_SESSION_USER = text(
    """
    SELECT must_change_password
    FROM   access."user"
    WHERE  id = :user_id AND status = 'active'
    """
)


@dataclass(frozen=True, slots=True)
class AuthenticatedKey:
    """INT-003's return: `{workspace_id, key_id, scope}`. Never the stored hash.

    `scope` is the explicit, **default-deny** list of model names this key may
    resolve (A-081). An empty tuple resolves nothing, and releasing a new prompt
    does not make it callable by an existing key — a cost worth watching in the
    pilot, since a consumer who was never granted it sees a not-found with no
    explanation.

    The hash is absent from this type on purpose. It is read inside
    :func:`authenticate_api_key`, compared, and dropped; a field for it here
    would be a field the gateway could log.
    """

    workspace_id: str
    key_id: str
    scope: tuple[str, ...] = field(default_factory=tuple)
    #: ADR-0061 / A-158. The namespaces this key may resolve, beside the names.
    #: A name resolves when it is in `scope` **or** its namespace is in here, and
    #: both defaulting to empty is what leaves A-081's default-deny exactly where
    #: it was. One entry replaces the thousand `scope` needed for a product that
    #: owns a folder — the friction this module's own lock called "a cost worth
    #: watching in the pilot".
    scope_namespaces: tuple[str, ...] = field(default_factory=tuple)
    #: ADR-0059 / A-152. NULL on every key that has not opted in, which is every
    #: key that exists — and NULL is what makes the gateway behave exactly as it
    #: did before observation was built. Non-NULL enables forwarding for this key
    #: and names the provider configuration whose credential pays for it.
    observe_provider_config_id: str | None = None
    #: ADR-0062 §3. The namespace this key's observations are filed under, which
    #: is what gives an observation a container and closes prompt-observation's
    #: SR-2. Set with its sibling or not at all — `ck_api_key_observe_is_all_or_nothing`
    #: is where that is enforced, because a handler is not what a second insert
    #: path would go through.
    observe_namespace: str | None = None

    @property
    def observes(self) -> bool:
        """Whether ADR-0059's forwarding mode is enabled for this key.

        Both columns or neither, so reading one is enough — but the pair is named
        here rather than at three call sites, so that a future third column joins
        the condition in one place.
        """
        return self.observe_provider_config_id is not None and self.observe_namespace is not None


async def authenticate_session(
    sessionmaker: async_sessionmaker[AsyncSession], cookie: str | None
) -> tuple[ActorSession, bool] | None:
    """INT-005. The session and whether its owner still owes a password change.

    Returns `None` for an absent cookie, an unknown id, an expired row, and a
    row whose user is no longer active — four different facts with one answer,
    because the client may distinguish none of them. A `None` becomes a `401` in
    the A-045 envelope and the SPA routes to sign-in.

    **A live row read, not a token verification.** Sessions are rows precisely so
    that signing out or removing a member takes effect at once rather than at
    expiry (A-108, ADR-0022, ADR-0029), and a self-contained JWT would make that
    promise a lie for the rest of the token's lifetime.

    Two round trips rather than one, and the second is not incidental: the
    definer function returns identifiers **only** (ADR-0051's rule), so
    `must_change_password` cannot ride along inside it without turning an
    identity lookup into a row reader. The second read is against a global table
    with no policy, by primary key.

    No transaction is opened. Both reads are `SELECT`s and neither needs a tenant
    — which is the entire point of the bootstrap.
    """
    if not cookie:
        return None

    async with sessionmaker() as db:
        row = (await db.execute(LOOKUP_SESSION, {"id": cookie})).one_or_none()
        if row is None:
            return None

        user = (await db.execute(LOAD_SESSION_USER, {"user_id": row.user_id})).one_or_none()
        if user is None:
            # The session outlived its account. Reachable only in the window
            # between a tombstone's UPDATE and its DELETE of this row, which is
            # one transaction wide and therefore never observed — but a session
            # dependency that trusted a foreign key it cannot see would be a
            # session dependency with a hole in it the day that changes.
            return None

    # `row.workspace_id` may be NULL from revision 0022: a lobby session. Passed
    # through untouched — deciding what a workspace-less session may do is
    # `require_session`'s, one layer out, and inventing a workspace here would be
    # this function choosing a tenant on somebody's behalf.
    return (
        ActorSession(user_id=row.user_id, workspace_id=row.workspace_id),
        user.must_change_password,
    )


async def authenticate_api_key(
    sessionmaker: async_sessionmaker[AsyncSession], presented: str | None
) -> AuthenticatedKey | None:
    """INT-003. Verify `prope_<key_id>_<secret>` and return the key's identity.

    `None` for every failure — malformed, unknown, revoked, or a hash mismatch —
    and the gateway answers all four in the OpenAI error shape. A **raise** is a
    `5xx` and the gateway does not fall back, does not serve a cached principal
    and does not admit the request: an unavailable oracle is not an allow.

    One indexed read plus one constant-time comparison, which is what makes the
    p95 < 5 ms budget credible rather than aspirational (ADR-0021). The parse
    computes the presented digest and **discards the secret** before this
    function ever holds it — see `keys.parse_presented_key`.

    **A hash mismatch counts as `unknown`.** Telling it apart from an absent row
    in a dashboard would be an oracle for *"this key id is live"*, which is one
    of the two halves of a key an attacker would otherwise have to guess whole.
    """
    started = time.perf_counter()

    parsed = None if presented is None else parse_presented_key(presented)
    if parsed is None:
        key_auth_total.labels(result="unknown").inc()
        key_auth_duration_seconds.observe(time.perf_counter() - started)
        return None

    async with sessionmaker() as db:
        row = (await db.execute(LOOKUP_API_KEY, {"key_id": parsed.key_id})).one_or_none()

    if row is None or not secrets_match(parsed.secret_hash, row.key_hash):
        key_auth_total.labels(result="unknown").inc()
        key_auth_duration_seconds.observe(time.perf_counter() - started)
        return None

    if row.revoked_at is not None:
        key_auth_total.labels(result="revoked").inc()
        key_auth_duration_seconds.observe(time.perf_counter() - started)
        return None

    key_auth_total.labels(result="ok").inc()
    key_auth_duration_seconds.observe(time.perf_counter() - started)
    return AuthenticatedKey(
        workspace_id=row.workspace_id,
        key_id=row.key_id,
        scope=tuple(row.scope_model_names),
        scope_namespaces=tuple(row.scope_namespaces),
        observe_provider_config_id=row.observe_provider_config_id,
        observe_namespace=row.observe_namespace,
    )


async def record_key_use(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspace_id: str,
    key_ids: tuple[str, ...],
) -> None:
    """Stamp `last_used_at`. **Deliberately not called by the authentication path.**

    INT-003 says the update *"is not part of the contract and must never be on
    the request's critical path"*, and the only way to honour that literally is
    to not issue it there. So this exists as a separate, batched, best-effort
    call and `authenticate_api_key` does not make it.

    **Its caller is the gateway, in phase 19**, which already owns a
    post-response hook that never raises — `enqueue()` runs after the response is
    flushed for exactly this class of work (A-037, A-087). Wiring it there rather
    than inventing a second background job here is what keeps this module's
    `deployment_target` line true: *"no process of its own and nothing in
    `worker`"*.

    **Until then `last_used_at` stays NULL, and that is stated rather than
    hidden.** ADR-0021 already calls the column *"the only signal available for
    spotting a key that is being used from somewhere it should not be"* and calls
    it weak; between phase 8 and phase 19 it is absent, and `OQ-136` carries it.

    Takes a batch because a per-request write on the gateway's path is the thing
    being avoided, and a function shaped for one id is a function somebody calls
    once per request.

    **One workspace per call**, because this is the first write in the module and
    it goes through the ordinary tenant seam like every other one (ADR-0040). A
    batch spanning workspaces would have to be grouped by the caller anyway; a
    signature that accepted one would have made the policy return zero rows for
    every id but the current tenant's, silently, which is the loud-failure
    inversion ADR-0035 exists to avoid turning into a quiet one.
    """
    if not key_ids:
        return

    async with workspace_transaction(sessionmaker, workspace_id) as db:
        await db.execute(TOUCH_API_KEY, {"key_ids": list(key_ids)})


#: ADR-0051's generic enumerator, as this module's API rather than as SQL every
#: caller re-spells. Three modules already issue this statement by hand
#: (`sessions.py`, `commands.py`, and `worker.py`'s docstring anticipates a
#: fourth); a fourth copy in prompt-registry would have been the first one
#: written by a module that may not read the `access` schema at all.
LIST_WORKSPACE_IDS = text("SELECT access.list_workspaces()")


async def list_workspace_ids(sessionmaker: async_sessionmaker[AsyncSession]) -> tuple[str, ...]:
    """Every workspace id in the install. **Identifiers only, never rows.**

    That distinction is what makes `access.list_workspaces()` a sanctioned
    escape rather than a hole (ADR-0051): the caller gets a list of tenants and
    then performs every actual read under the ordinary policy, one workspace at
    a time. A function that returned rows would be performing the read with the
    policy off, which is the shape ADR-0051 refuses by name.

    **Opens its own session with no tenant set**, like the two lookups above and
    for the same reason: a sweep that must discover its own work across tenants
    cannot be inside any one tenant's transaction.

    The consumers are background sweeps — the tombstone (A-151), release-control's
    review sweeps in phase 22, and prompt-registry's BR-03 reconciliation, which
    is a cross-tenant count that the runtime role cannot otherwise reach.
    """
    async with sessionmaker() as session:
        return tuple((await session.execute(LIST_WORKSPACE_IDS)).scalars().all())
