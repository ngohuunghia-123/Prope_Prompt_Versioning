"""INT-001, INT-002, INT-004 — the three questions this module answers about authority.

**Every function here takes the CALLER's session, not a sessionmaker.** That is
the opposite of `bootstrap.py` one file over, and the asymmetry is the design:
the caller has already opened a `workspace_transaction` around the row it read,
and an oracle that opened its own would answer from a different snapshot — so a
grant committed between the two reads would produce an allow for a row the caller
never saw. `bootstrap.py` opens its own because it runs *before* a tenant exists.

**Nothing here is cached and no caller may cache an answer** (A-114, ADR-0022).
Two indexed reads over small tables is what a permission check costs, and paying
it every time is what makes *"revocation is effective on the next request"* a
sentence Prope can say without a footnote.

**No query below carries a `workspace_id` predicate, and that is not an
omission.** `role_binding`, `prompt_grant` and `api_key` are all policied, and the
caller's transaction has already set `app.workspace_id` — so the tenant filter is
the policy's, applied to every one of these reads whether or not somebody
remembered it. That is ADR-0035's inversion working the way it was designed to:
a query written without the filter answers **zero rows** rather than another
tenant's. `may()` still compares the actor's workspace to the subject's before
issuing anything, but that comparison is there to make a cross-tenant question
*fast and legible*, not to make it safe.

**This module reads only `access` tables.** `owner_id` and `access_level` arrive
as parameters on :class:`~prope.access_control.domain.Subject`, from the row the
caller has already read (ADR-0020) — which is what keeps this module's dependency
list at one entry and makes six would-be cycles unnecessary rather than merely
forbidden. `tests/contract/test_may_reads_no_subject.py` asserts it over the
statements this file issues, not over its docstring.

**Errors propagate.** There is no `try` in this file, and there is none in any
caller either (A-142 §2, INT-001). An unavailable oracle becomes a 5xx and never
an allow, and the absence of an `except` is the whole mechanism — a caller that
wrapped `may()` in one would have introduced the bug this seam is shaped to make
impossible.
"""

import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from prope.access_control.actions import Action, parse_action
from prope.access_control.domain import (
    AccessLevel,
    Actor,
    ActorType,
    GrantLevel,
    Subject,
    SubjectType,
    VisibleFilter,
)
from prope.access_control.observability import (
    check_duration_seconds,
    check_total,
    key_scope_refusal_total,
    unknown_action_total,
    visible_filter_duration_seconds,
    visible_filter_ids_size,
)

__all__ = [
    "GRANT_ACTIONS",
    "may",
    "may_resolve",
    "visible_subject_filter",
]

#: A-111's first half: what a role binding grants. One query, joining the
#: actor's bindings to the seeded matrix — the union across several bindings is
#: `EXISTS`, so an actor holding two roles where one grants and one does not is
#: an **allow** (AC-3). Nothing subtracts, and there is no deny-override branch to
#: write, because a rule that removed a permission somebody else added is a rule
#: whose outcome depends on evaluation order.
ROLE_GRANTS_ACTION = text(
    """
    SELECT EXISTS (
        SELECT 1
        FROM   access.role_binding AS rb
        JOIN   access.role_permission AS rp ON rp.role = rb.role
        WHERE  rb.user_id = :user_id AND rp.action = :action
    )
    """
)

#: A-111's second half. Scoped to one prompt, and the level is compared in Python
#: against :data:`GRANT_ACTIONS` rather than in SQL — the mapping from a level to
#: the actions it confers is a **policy** statement, and policy that lives half in
#: a query is policy nobody can read in one place.
GRANT_LEVEL_FOR_SUBJECT = text(
    """
    SELECT level
    FROM   access.prompt_grant
    WHERE  prompt_id = :prompt_id AND grantee_user_id = :user_id
    """
)

#: ADR-0061's fifth source. `prompt_grant`'s twin one scope up, and the level it
#: returns is compared against the same :data:`GRANT_ACTIONS` map for the same
#: reason: what a level confers is one policy statement, and two copies of it is
#: how a folder grant quietly starts conferring more than a prompt grant.
#:
#: The namespace arrives as a **parameter from the caller**, off the row it has
#: already read (ADR-0020). This module never resolves it, never expands it and
#: never reads `registry.folder` — which is possible only because that table is
#: flat. See :class:`~prope.access_control.domain.Subject`.
NAMESPACE_GRANT_LEVEL_FOR_SUBJECT = text(
    """
    SELECT level
    FROM   access.namespace_grant
    WHERE  namespace = :namespace AND grantee_user_id = :user_id
    """
)

#: A-118's `ids` branch: everything the actor owns is unknown to this module, so
#: only the granted ids come from here. Ownership is folded in by the caller's
#: own `owner_id = :actor` clause — see :func:`visible_subject_filter`.
GRANTED_PROMPT_IDS = text(
    "SELECT prompt_id FROM access.prompt_grant WHERE grantee_user_id = :user_id"
)

#: A-118's second dimension, added 2026-08-18. This is the read that ANSWERS the
#: assumption's own revisit condition — *"a workspace's prompt count makes an
#: explicit id list too large to push into a query"* — rather than postponing it.
#: Four folders holding two thousand prompts is four rows here.
GRANTED_NAMESPACES = text(
    "SELECT namespace FROM access.namespace_grant WHERE grantee_user_id = :user_id"
)

#: INT-004. Default-deny by construction **twice over**: an empty
#: `scope_model_names` and an empty `scope_namespaces` each make their `= ANY(...)`
#: false for every input, so a key with neither resolves nothing without a branch
#: anybody could forget to write (A-081, A-158). Adding the second array to the
#: same `OR` does not weaken that — it is the identical mechanism, twice.
#:
#: `:namespace` is supplied by the gateway from the `ModelName` it has already
#: parsed at the edge of the request, so the wider scope costs no extra work here
#: and no extra read anywhere.
KEY_RESOLVES_MODEL = text(
    """
    SELECT EXISTS (
        SELECT 1
        FROM   access.api_key
        WHERE  id = :key_id
          AND  revoked_at IS NULL
          AND  (:model_name = ANY(scope_model_names) OR :namespace = ANY(scope_namespaces))
    )
    """
)

#: ADR-0062's entry rule needs one more fact — *which namespaces does this
#: workspace use* — and **it is deliberately not here.** It is a question about
#: `registry.folder` and `registry.prompt_property`, which this module is
#: forbidden to read (ADR-0020, and the module map's *access-control → anything
#: but property-history*). It lives in `prompt_registry.seams.list_namespaces`
#: and the gateway asks the registry directly, along the edge it already has.
#:
#: Written down as an absence rather than left silent, because the temptation is
#: real: the string is already a parameter to `may_resolve` two functions down,
#: and one `UNION` here would have answered it. That query would have made this
#: module depend on the registry, which is the cycle six modules' locks are
#: shaped to avoid.

#: What each grant level confers, as data rather than as an `if` chain (A-112).
#:
#: `viewer` reads. `editor` reads and writes — which here means creating a
#: revision and editing the prompt, and **not** submitting it for review:
#: `revision.submit` is the first step of the release path, and A-112's ceiling
#: exists so that a workspace's separation of edit / review / release cannot be
#: dissolved one prompt at a time by an owner being helpful.
GRANT_ACTIONS: dict[GrantLevel, frozenset[Action]] = {
    GrantLevel.VIEWER: frozenset({Action.PROMPT_READ, Action.SUITE_READ, Action.RUN_READ}),
    GrantLevel.EDITOR: frozenset(
        {
            Action.PROMPT_READ,
            Action.SUITE_READ,
            Action.RUN_READ,
            Action.PROMPT_EDIT,
            Action.REVISION_CREATE,
        }
    ),
}

#: What owning a subject confers on top of whatever the owner's roles already
#: grant. Ownership is not a role and does not appear in `role_permission`: it is
#: a property of the *subject*, reported by the caller, and A-007 gives the Owner
#: role its permissions workspace-wide rather than per prompt.
#:
#: The set is deliberately the editor set plus the two acts only an owner may
#: perform on their own prompt. It notably does **not** include
#: `prompt.transfer_owner` — handing a prompt away is an Admin act (A-007),
#: because an owner who could transfer could also launder a prompt out of a
#: reviewer's sight.
OWNER_ACTIONS: frozenset[Action] = frozenset(
    {
        Action.PROMPT_READ,
        Action.SUITE_READ,
        Action.RUN_READ,
        Action.PROMPT_EDIT,
        Action.PROMPT_RETIRE,
        Action.PROMPT_GRANT,
        Action.REVISION_CREATE,
        Action.SUITE_EDIT,
        Action.RUN_START,
    }
)

#: What a subject's `access_level = workspace` confers on any member of that
#: workspace. BR-01 makes `private` the default and this is the opt-out: the
#: owner has opened the prompt to their colleagues, which is a *read*, and never
#: more than a read. An access level that granted edit would be a grant table
#: with one row and no grantee.
WORKSPACE_VISIBLE_ACTIONS: frozenset[Action] = frozenset(
    {Action.PROMPT_READ, Action.SUITE_READ, Action.RUN_READ}
)


async def may(db: AsyncSession, actor: Actor, action: Action | str, subject: Subject) -> bool:
    """INT-001. `allow` or `deny`, and **nothing else** — no reason, no partial answer.

    The answer is the **union** of five independent sources, and the first one
    that says yes ends it (A-111):

    * the actor's role bindings, through the seeded `(role, action)` matrix;
    * ownership of the subject, as the caller reported it;
    * the subject's access level, as the caller reported it;
    * a per-prompt grant;
    * a per-**namespace** grant, since ADR-0061 — the same two levels through the
      same policy map, one scope up.

    Nothing subtracts, and there is still no deny-override branch to write. The
    fifth source does not change that: a rule that removed a permission somebody
    else's grant added is a rule whose outcome depends on evaluation order, and
    adding a wider scope is exactly where that temptation arrives.

    **An action outside the closed vocabulary is a deny, never an error and never
    an allow** (A-115, AC-4). It increments `unknown_action_total`, which must
    stay 0 and which `AccessControlUnknownAction` pages on — the safe failure is
    also the silent one, so the counter is what makes it audible.

    **A consumer key is denied every action in the vocabulary.** A key holds no
    role binding and no grant; its entire authority is `may_resolve`, which is a
    different question against a different table. Answering it here on the union
    rule would be answering "no" the slow way, and it would mean a future grant
    to a `key_` id silently worked.

    **An actor and a subject in different workspaces is a deny**, checked before
    any query. The policy would answer zero rows anyway, so this is not what makes
    it safe — it is what makes it *fast*, and what stops a cross-tenant question
    looking like a permission that merely has not been granted yet.
    """
    started = time.perf_counter()
    resolved = parse_action(action)

    if resolved is None:
        unknown_action_total.inc()
        _observe(str(action), allowed=False, started=started)
        return False

    allowed = (
        actor.type is ActorType.USER
        and actor.workspace_id == subject.workspace_id
        and await _has_permission(db, actor, resolved, subject)
    )
    _observe(resolved.value, allowed=allowed, started=started)
    return allowed


async def _has_permission(
    db: AsyncSession, actor: Actor, action: Action, subject: Subject
) -> bool:
    """The union, cheapest source first.

    Ownership and access level are already in memory — the caller passed them —
    so they are checked before any query runs. The role query comes next because
    it answers most actions in the vocabulary; the two grant queries come last
    because they apply to prompts alone and are the only ones that can be skipped
    entirely. The namespace grant is fifth rather than fourth because a subject
    that carries no namespace skips it for free, which is every subject written
    before ADR-0061.
    """
    if subject.owner_id is not None and subject.owner_id == actor.id and action in OWNER_ACTIONS:
        return True

    if subject.access_level is AccessLevel.WORKSPACE and action in WORKSPACE_VISIBLE_ACTIONS:
        return True

    granted_by_role = await db.scalar(
        ROLE_GRANTS_ACTION, {"user_id": actor.id, "action": action.value}
    )
    if granted_by_role:
        return True

    if subject.type is not SubjectType.PROMPT:
        return False

    level = await db.scalar(
        GRANT_LEVEL_FOR_SUBJECT, {"prompt_id": subject.id, "user_id": actor.id}
    )
    if level is not None and action in GRANT_ACTIONS[GrantLevel(level)]:
        return True

    # ADR-0061's fifth source, and last for the same reason the fourth was: it is
    # the only other query that can be skipped entirely. A subject with no
    # namespace — every subject that existed before this decision — never issues
    # it, so the cost of the wider scope is paid only by callers who opted into
    # supplying the attribute.
    if subject.namespace is None:
        return False

    namespace_level = await db.scalar(
        NAMESPACE_GRANT_LEVEL_FOR_SUBJECT,
        {"namespace": subject.namespace, "user_id": actor.id},
    )
    if namespace_level is None:
        # A-157: an ungranted namespace confers NOTHING. There is no fallback to
        # workspace-visible here, and the direction is chosen rather than
        # inherited — a typo in a namespace must make a prompt invisible to
        # colleagues, which is annoying and correctable, never visible to
        # everybody, which is silent and is what BR-01 is a non-negotiable to
        # prevent.
        return False

    return action in GRANT_ACTIONS[GrantLevel(namespace_level)]


def _observe(action: str, *, allowed: bool, started: float) -> None:
    """One site for both metrics, so a branch cannot count one and not the other.

    `result` is `allow` or `deny` and never `error`: an error is the absence of an
    answer, it is counted on `check_error_total`, and putting it here would make
    the deny rate `AccessControlDenyRateSpike` watches quietly include failures.
    """
    result = "allow" if allowed else "deny"
    check_total.labels(action=action, result=result).inc()
    check_duration_seconds.labels(action=action, result=result).observe(
        time.perf_counter() - started
    )


async def visible_subject_filter(
    db: AsyncSession, actor: Actor, subject_type: SubjectType | str
) -> VisibleFilter:
    """INT-002. A **set** for the caller's own `WHERE` clause, never a predicate.

    Modes (A-118, extended by ADR-0061):

    * `all` — a role binding grants `prompt.read` workspace-wide, so there is no
      set to hand over and returning one would be a lie about what the actor can
      genuinely see in full.
    * `ids` / `namespaces` — visibility comes from grants, and the caller adds its
      own `owner_id = <actor>` and `access_level = 'workspace'` clauses. **This
      module cannot see ownership**, so what comes back is the granted set only;
      the caller ORs in the two predicates it can evaluate itself. That split is
      ADR-0020 again, and it is why this is a *filter* rather than an answer.
    * `none` — none of the above. It must render as an empty list, never as an
      error and never as an unfiltered query.

    **The two granted dimensions come back together, not as alternatives.** An
    actor can hold three per-prompt grants and two folder grants at once, so a
    caller applies `ids` and `namespaces` in the same disjunction and never
    branches on `mode` beyond the `all` short-circuit. `mode` names whichever
    dimension is populated so the metric stays legible, and a caller that has
    never heard of `namespaces` narrows rather than widens.

    **Why a set at all.** The alternative is not fifty `may()` calls; it is a
    developer under deadline pressure writing the list query with no filter and
    adding the check "later". The shape exists to make the correct implementation
    the easy one, which is prompt-registry's own stated worst case avoided by
    construction.

    A consumer key gets `none`: keys hold no grants, and a list endpoint is not a
    surface a key reaches.
    """
    started = time.perf_counter()
    parsed_type = subject_type if isinstance(subject_type, SubjectType) else None
    if parsed_type is None:
        try:
            parsed_type = SubjectType(subject_type)
        except ValueError:
            # Same posture as an unknown action: the narrowest answer, not an
            # exception. A caller asking about a subject type that does not exist
            # gets an empty list rather than a 500, and gets it consistently.
            return _observed(VisibleFilter.none(), started)

    if actor.type is not ActorType.USER or parsed_type is not SubjectType.PROMPT:
        return _observed(VisibleFilter.none(), started)

    reads_everything = await db.scalar(
        ROLE_GRANTS_ACTION, {"user_id": actor.id, "action": Action.PROMPT_READ.value}
    )
    if reads_everything:
        return _observed(VisibleFilter.all(), started)

    granted = (await db.execute(GRANTED_PROMPT_IDS, {"user_id": actor.id})).scalars().all()
    namespaces = (await db.execute(GRANTED_NAMESPACES, {"user_id": actor.id})).scalars().all()
    return _observed(VisibleFilter.of(granted, namespaces), started)


def _observed(result: VisibleFilter, started: float) -> VisibleFilter:
    """Record the mode, the duration, and — for `ids` — how many.

    `visible_filter_ids_size` is A-118's revisit condition made observable:
    *"a workspace's prompt count makes an explicit id list too large to push into
    a query"*. A histogram whose top bucket starts moving is the trigger, which is
    a great deal earlier than a slow query somebody has to go looking for.
    """
    visible_filter_duration_seconds.labels(mode=result.mode.value).observe(
        time.perf_counter() - started
    )
    # Observed whenever ids are present rather than only under `mode is IDS`,
    # because since ADR-0061 a bounded answer can carry both dimensions and the
    # histogram is watching the id list specifically. The namespace list is not
    # instrumented: A-118's revisit condition is about an id list growing without
    # bound, and folder counts do not do that.
    if result.ids:
        visible_filter_ids_size.observe(len(result.ids))
    return result


async def may_resolve(db: AsyncSession, key_id: str, model_name: str, namespace: str) -> bool:
    """INT-004. May this consumer key resolve this model name? **Default-deny.**

    **Two scopes, one `OR`, still one indexed read** (ADR-0061, A-158). The key
    resolves a name listed in `scope_model_names` *or* a name whose namespace is
    listed in `scope_namespaces`. `namespace` is supplied by the gateway from the
    `ModelName` it already parsed at the edge of the request, so the wider scope
    costs nothing here and nothing there.

    The union is additive rather than a replacement, and default-deny is what
    survives it unchanged: both arrays default to `'{}'`, `= ANY('{}')` is false
    for every input, and a key with neither set resolves nothing — the same
    mechanism A-081 always relied on, applied twice. One namespace entry replaces
    the thousand name entries a product that owns a folder used to need.

    A bare `bool`, carrying no reason — deliberately. The gateway must render a
    scope refusal as the **same not-found** it renders for a model name that does
    not exist (A-081, A-116), so that a leaked key cannot enumerate the registry
    by observing which names refuse differently. A result object with a reason
    field would be a reason somebody eventually puts in a response body.

    An empty scope resolves nothing, and releasing a new prompt does not make it
    callable by an existing key. A revoked key resolves nothing either, on the
    very next request after the commit, with no TTL to wait out (ADR-0022, AC-6).

    Counted on refusal only. A counter incremented on every *allowed* resolution
    would be a per-request counter on the gateway's hot path with a `key_id`
    label; the refusals are the ones somebody has to act on.
    """
    allowed = bool(
        await db.scalar(
            KEY_RESOLVES_MODEL,
            {"key_id": key_id, "model_name": model_name, "namespace": namespace},
        )
    )
    if not allowed:
        key_scope_refusal_total.labels(key_id=key_id).inc()
    return allowed
