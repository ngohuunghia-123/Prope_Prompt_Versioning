"""Every read and write in the module. One hot-path write, six management reads.

**The hot-path write is one statement** (:func:`record_observation`), and it has
to be: it runs after the response has been flushed to a caller who is already
gone, on every forwarded call, and a second round trip there is a second thing
that can fail with nobody to tell. The statement upserts the fingerprint group,
returns what the group looked like *before* the upsert, and Python decides from
that whether the sighting it writes next carries a body.

**Why the prior state comes back from a CTE rather than a `SELECT` first.** The
``prior`` CTE reads the pre-statement snapshot, so the upsert cannot race with
its own lookup. Two workers observing the same changed body at the same instant
will both call it a change and both store a body — which is a duplicate row, not
a wrong one, and the alternative was a lock on the hot path.

**Nothing here checks a permission**, on prompt-registry's repository's rule and
for a sharper reason: the reads take a
:class:`~prope.access_control.domain.VisibleFilter` they cannot be called
without, and the hot-path write is authorised by the key's ``observe_namespace``
long before it gets here — a key writes into the namespace it was issued for and
has no way to name another.

**Only `visible.namespaces` is applied, never `visible.ids`.** An observation is
not a prompt and holds no per-prompt grant, so an actor's three ``prompt_grant``
rows say nothing about it. That is ADR-0061's point restated at the one place it
bites: before namespaces were the unit of authorisation there was no filter this
module could have written, which is what SR-2 recorded.
"""

import time
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from prope.access_control.domain import FilterMode, VisibleFilter
from prope.prompt_observation.domain import (
    AdoptionProposal,
    ObservationDraft,
    ObservationRow,
    ObservationStatus,
    SightingRow,
)
from prope.prompt_observation.fingerprint import (
    body_hash as compute_body_hash,
)
from prope.prompt_observation.fingerprint import (
    fingerprint as compute_fingerprint,
)
from prope.prompt_observation.fingerprint import (
    infer_variables,
    system_message,
)
from prope.prompt_observation.models import observation, sighting

log = structlog.get_logger(__name__)

__all__ = [
    "adopt",
    "delete_observation",
    "dismiss",
    "list_observations",
    "list_sightings",
    "load_observation",
    "propose_adoption",
    "record_observation",
    "redact",
    "suggest_name",
]

#: A-045 / ADR-0003, minted at the one site that inserts.
OBSERVATION_ID_PREFIX = "obs_"

SIGHTING_ID_PREFIX = "sig_"

#: How many bodies the proposal diffs. A group with four hundred sightings has
#: four hundred bodies stored only if it changed four hundred times, which would
#: itself be the finding; in practice the newest handful is where the variables
#: are, and an unbounded diff on a management route is an unbounded diff.
PROPOSAL_SAMPLE = 12

#: The inbox's page. Larger than the registry's because an observation row is a
#: counter and two dates, and the whole point of the screen is *how much is out
#: there* — a first page that cannot show it defeats it.
DEFAULT_LIMIT = 100

MAX_LIMIT = 500


#: The one hot-path statement. `prior` reads the snapshot before the upsert, so
#: the returned `prior_body_hash` is genuinely the previous one and not the row
#: this statement just wrote.
#:
#: `first_seen_at` takes a `LEAST` rather than being left alone, because a
#: forwarded call is written from a background task and arrival order is not
#: clock order — a late-arriving older sighting must not be able to move the
#: group's start forward, and must be able to move it back.
#:
#: A redacted group keeps its counters and refuses the text: `current_body` and
#: `body_hash` are pinned to what they already are, which is what
#: `ck_observation_redacted_body_is_empty` requires and what makes SR-4's redact
#: hold against a caller that is still sending.
RECORD_OBSERVATION = text(
    """
    WITH prior AS (
        SELECT body_hash, redacted_at
        FROM observation.observation
        WHERE workspace_id = :workspace_id AND fingerprint = :fingerprint
    ),
    upsert AS (
        INSERT INTO observation.observation (
            id, workspace_id, namespace, fingerprint, body_hash, current_body,
            sighting_count, first_seen_at, last_seen_at, upstream_models,
            created_at, updated_at
        ) VALUES (
            :id, :workspace_id, :namespace, :fingerprint, :body_hash, :body,
            1, :occurred_at, :occurred_at, ARRAY[:upstream_model]::text[],
            :now, :now
        )
        ON CONFLICT (workspace_id, fingerprint) DO UPDATE SET
            sighting_count = observation.sighting_count + 1,
            first_seen_at  = LEAST(observation.first_seen_at, EXCLUDED.first_seen_at),
            last_seen_at   = GREATEST(observation.last_seen_at, EXCLUDED.last_seen_at),
            upstream_models = CASE
                WHEN EXCLUDED.upstream_models[1] = ANY (observation.upstream_models)
                    THEN observation.upstream_models
                ELSE observation.upstream_models || EXCLUDED.upstream_models
            END,
            current_body = CASE
                WHEN observation.redacted_at IS NOT NULL THEN observation.current_body
                ELSE EXCLUDED.current_body
            END,
            body_hash = CASE
                WHEN observation.redacted_at IS NOT NULL THEN observation.body_hash
                ELSE EXCLUDED.body_hash
            END,
            updated_at = EXCLUDED.updated_at
        RETURNING id
    )
    SELECT
        upsert.id AS observation_id,
        prior.body_hash AS prior_body_hash,
        (prior.redacted_at IS NOT NULL) AS redacted
    FROM upsert LEFT JOIN prior ON true
    """
)

INSERT_SIGHTING = text(
    """
    INSERT INTO observation.sighting (
        id, workspace_id, observation_id, body_hash, body,
        call_id, consumer_key_id, upstream_model, occurred_at
    ) VALUES (
        :id, :workspace_id, :observation_id, :body_hash, :body,
        :call_id, :consumer_key_id, :upstream_model, :occurred_at
    )
    """
)

#: The proposal's raw material. Newest first and bounded: only body-CHANGING
#: sightings carry a body, so this is already the short list of distinct bodies
#: rather than a scan of the traffic.
SELECT_SIGHTING_BODIES = text(
    """
    SELECT body
    FROM observation.sighting
    WHERE workspace_id = :workspace_id
      AND observation_id = :observation_id
      AND body IS NOT NULL
    ORDER BY occurred_at DESC
    LIMIT :limit
    """
)

#: Written back so the inbox can say "3 variables" without re-diffing per row.
#: It is a cache of a PROPOSAL and never of a decision — A-154's
#: propose-never-apply is not weakened by storing what was proposed, only by
#: acting on it.
UPDATE_INFERRED_VARIABLES = text(
    """
    UPDATE observation.observation
    SET inferred_variables = CAST(:variables AS text[]), updated_at = :now
    WHERE workspace_id = :workspace_id AND id = :observation_id
    """
)

MARK_ADOPTED = text(
    """
    UPDATE observation.observation
    SET adopted_prompt_id = :prompt_id,
        adopted_by = :actor_id,
        adopted_at = :now,
        dismissed_by = NULL,
        dismissed_at = NULL,
        dismissal_reason = NULL,
        updated_at = :now
    WHERE workspace_id = :workspace_id AND id = :observation_id
    RETURNING id
    """
)

MARK_DISMISSED = text(
    """
    UPDATE observation.observation
    SET dismissed_by = :actor_id,
        dismissed_at = :now,
        dismissal_reason = :reason,
        updated_at = :now
    WHERE workspace_id = :workspace_id
      AND id = :observation_id
      AND adopted_at IS NULL
    RETURNING id
    """
)

#: SR-4. The counters, the dates and the models survive; the text does not. The
#: sightings lose their bodies in the same statement, because a redaction that
#: left the drift view intact would have removed nothing.
REDACT_OBSERVATION = text(
    """
    WITH cleared AS (
        UPDATE observation.sighting
        SET body = NULL
        WHERE workspace_id = :workspace_id AND observation_id = :observation_id
        RETURNING id
    )
    UPDATE observation.observation
    SET current_body = '', redacted_at = :now, updated_at = :now
    WHERE workspace_id = :workspace_id AND id = :observation_id
    RETURNING id
    """
)

#: The only DELETE in the module, and it is **not** a history delete. An
#: observation records what somebody else's code sent, not what a person in
#: Prope decided, and the non-negotiable that forbids deleting history is about
#: the second thing. The sightings go with it by `ON DELETE CASCADE`.
DELETE_OBSERVATION = text(
    """
    DELETE FROM observation.observation
    WHERE workspace_id = :workspace_id AND id = :observation_id
    RETURNING id
    """
)


async def record_observation(db: AsyncSession, draft: ObservationDraft) -> str | None:
    """INT-034. File one forwarded call against its fingerprint group.

    Returns the observation's id, or ``None`` when there was nothing to observe.

    **A call with no system message is not observed at all**, and that is the
    honest answer rather than a degenerate group: ADR-0011 makes the revision's
    body the system message, so a call that carries none carries no prompt of
    anybody's — it is a bare conversation, and filing it would put a row in the
    inventory that can never become a prompt.

    **The user turns never reach the database.** Only the system message is
    hashed and only the system message is stored, which is OQ-148 §4's
    conservative reading taken before the policy question is answered rather
    than after.
    """
    body = system_message(draft.messages)
    if body is None:
        return None

    started = time.perf_counter()
    now = datetime.now(UTC)
    fingerprint = compute_fingerprint(body)
    body_hash = compute_body_hash(body)

    row = (
        await db.execute(
            RECORD_OBSERVATION,
            {
                "id": f"{OBSERVATION_ID_PREFIX}{ULID()}",
                "workspace_id": draft.workspace_id,
                "namespace": draft.namespace,
                "fingerprint": fingerprint,
                "body_hash": body_hash,
                "body": body,
                "upstream_model": draft.upstream_model,
                "occurred_at": draft.occurred_at,
                "now": now,
            },
        )
    ).one()

    # A sighting carries a body only when it CHANGED one. Everything else is a
    # counter increment that already happened above, plus a row saying which
    # call it was — which is what keeps this table from becoming
    # `ledger.call_body` under another name on the readable side of ADR-0018.
    #
    # A redacted group stores no body either. Somebody removed that text on
    # purpose and the caller is still sending it; writing it back into a
    # sighting would undo the redaction by the next request.
    changed = row.prior_body_hash is None or row.prior_body_hash != body_hash
    await db.execute(
        INSERT_SIGHTING,
        {
            "id": f"{SIGHTING_ID_PREFIX}{ULID()}",
            "workspace_id": draft.workspace_id,
            "observation_id": row.observation_id,
            "body_hash": body_hash,
            "body": body if changed and not row.redacted else None,
            "call_id": draft.call_id,
            "consumer_key_id": draft.consumer_key_id,
            "upstream_model": draft.upstream_model,
            "occurred_at": draft.occurred_at,
        },
    )

    # `first_sighting` and `body_changed` were here and are gone. Both are
    # booleans, both carry no content, and neither is in `LOGGABLE_FIELDS` — and
    # the right response to that was to drop them rather than to widen a
    # project-wide allow-list for two flags one module wanted. What they answered
    # is better answered by the table itself: `sighting_count = 1` is a first
    # sighting, and a sighting row with a non-NULL body is a body that changed.
    log.debug(
        "observation.recorded",
        observation_id=row.observation_id,
        namespace=draft.namespace,
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    return str(row.observation_id)


async def list_observations(
    db: AsyncSession,
    workspace_id: str,
    visible: VisibleFilter,
    *,
    status: ObservationStatus | None = None,
    namespace: str | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> list[ObservationRow]:
    """The inbox. There is no default for ``visible`` and there must not be.

    Prompt-registry's repository is shaped this way for A-118's reason — the
    failure being designed out is a list query written with no filter at all —
    and this module inherits it rather than re-deciding it.
    """
    if visible.mode is FilterMode.NONE:
        return []

    query = select(observation).where(observation.c.workspace_id == workspace_id)
    if visible.mode is not FilterMode.ALL:
        # `ids` is deliberately unread here; see the module docstring. An empty
        # `namespaces` under a bounded mode is an actor holding only per-prompt
        # grants, and a per-prompt grant conveys nothing about an observation.
        query = query.where(observation.c.namespace.in_(visible.namespaces))
    if namespace is not None:
        query = query.where(observation.c.namespace == namespace)
    if status is ObservationStatus.OPEN:
        query = query.where(
            observation.c.adopted_at.is_(None), observation.c.dismissed_at.is_(None)
        )
    elif status is ObservationStatus.ADOPTED:
        query = query.where(observation.c.adopted_at.is_not(None))
    elif status is ObservationStatus.DISMISSED:
        query = query.where(observation.c.dismissed_at.is_not(None))

    query = query.order_by(observation.c.last_seen_at.desc(), observation.c.id.desc())
    query = query.limit(min(max(limit, 1), MAX_LIMIT)).offset(max(offset, 0))

    return [_observation_row(row) for row in (await db.execute(query)).mappings()]


async def load_observation(
    db: AsyncSession, workspace_id: str, observation_id: str
) -> ObservationRow | None:
    """One group by id, unfiltered — the route gates it against ``namespace``.

    Unfiltered for prompt-registry's ``load_prompt`` reason, which ADR-0020 makes
    unavoidable: permission is decided from the subject, and the subject has to
    be read before there is one. The route refuses **not-found** afterwards, so
    an observation in a namespace the actor cannot see is byte-identical to one
    that never existed (A-116).
    """
    query = select(observation).where(
        observation.c.workspace_id == workspace_id, observation.c.id == observation_id
    )
    row = (await db.execute(query)).mappings().one_or_none()
    return None if row is None else _observation_row(row)


async def list_sightings(
    db: AsyncSession,
    workspace_id: str,
    observation_id: str,
    *,
    limit: int = DEFAULT_LIMIT,
) -> list[SightingRow]:
    """The drift view: every occurrence, newest first.

    The ones that changed the body carry it; the rest are the counter, itemised.
    """
    query = (
        select(sighting)
        .where(
            sighting.c.workspace_id == workspace_id,
            sighting.c.observation_id == observation_id,
        )
        .order_by(sighting.c.occurred_at.desc(), sighting.c.id.desc())
        .limit(min(max(limit, 1), MAX_LIMIT))
    )
    return [
        SightingRow(
            id=row["id"],
            observation_id=row["observation_id"],
            body_hash=row["body_hash"],
            body=row["body"],
            call_id=row["call_id"],
            consumer_key_id=row["consumer_key_id"],
            upstream_model=row["upstream_model"],
            occurred_at=row["occurred_at"],
        )
        for row in (await db.execute(query)).mappings()
    ]


async def propose_adoption(db: AsyncSession, row: ObservationRow) -> AdoptionProposal:
    """A-154's proposal, computed from the group's stored bodies. **Not a write.**

    It writes ``inferred_variables`` back and nothing else — a cache of what was
    proposed, so the inbox can say *3 variables* without diffing every group on
    every page load. Storing what was proposed is not applying it; the body it
    returns goes to a person, who posts it through prompt-registry's own create
    routes or does not.

    ``suggested_name`` is a suggestion in the strict sense: A-021 makes a model
    name immutable, so the field a person is most likely to accept unread is the
    one they can least afford to get wrong. It is derived from the body's own
    opening words rather than invented, so an obviously-wrong suggestion looks
    obviously wrong.
    """
    bodies = (
        (
            await db.execute(
                SELECT_SIGHTING_BODIES,
                {
                    "workspace_id": row.workspace_id,
                    "observation_id": row.id,
                    "limit": PROPOSAL_SAMPLE,
                },
            )
        )
        .scalars()
        .all()
    )
    # `current_body` first, so the template the slots are cut out of is the body
    # the caller is sending TODAY. A proposal shaped around a body that was
    # replaced last week reads as authoritative and is out of date.
    candidates = [row.current_body, *bodies] if row.current_body else list(bodies)
    body, variables = infer_variables(candidates)

    if tuple(variables) != row.inferred_variables:
        await db.execute(
            UPDATE_INFERRED_VARIABLES,
            {
                "workspace_id": row.workspace_id,
                "observation_id": row.id,
                "variables": variables,
                "now": datetime.now(UTC),
            },
        )

    return AdoptionProposal(
        observation_id=row.id,
        body=body,
        variables=tuple(variables),
        suggested_name=suggest_name(row.current_body, row.fingerprint),
    )


async def adopt(
    db: AsyncSession,
    workspace_id: str,
    observation_id: str,
    *,
    prompt_id: str,
    actor_id: str,
) -> bool:
    """Record that this group became a prompt. The PROMPT already exists.

    Prompt-registry created it, through its own routes, writing the
    ``property_created`` and ``revision_created`` events it always writes. This
    statement only points the inventory at the result — which is
    prompt-conversion's *conversion never saves a revision* rule, held for the
    reason non-negotiable #1 exists: adoption has to be an act somebody
    performed, and a module that could create the prompt itself would be a
    second way into production with its own approval story.

    Adopting clears a prior dismissal. Somebody dismissed it and somebody
    changed their mind; leaving both stamps would make ``status`` a question
    about precedence rather than a fact.
    """
    row = (
        await db.execute(
            MARK_ADOPTED,
            {
                "workspace_id": workspace_id,
                "observation_id": observation_id,
                "prompt_id": prompt_id,
                "actor_id": actor_id,
                "now": datetime.now(UTC),
            },
        )
    ).one_or_none()
    return row is not None


async def dismiss(
    db: AsyncSession,
    workspace_id: str,
    observation_id: str,
    *,
    actor_id: str,
    reason: str | None = None,
) -> bool:
    """*Somebody looked and this is not a prompt worth registering.*

    Refuses an already-adopted group — ``adopted_at IS NULL`` is in the
    statement rather than checked first, so two people acting at once cannot
    produce a row that is both. Returns ``False`` in that case, which the route
    renders as a conflict rather than as a silent success.
    """
    row = (
        await db.execute(
            MARK_DISMISSED,
            {
                "workspace_id": workspace_id,
                "observation_id": observation_id,
                "actor_id": actor_id,
                "reason": reason,
                "now": datetime.now(UTC),
            },
        )
    ).one_or_none()
    return row is not None


async def redact(db: AsyncSession, workspace_id: str, observation_id: str) -> bool:
    """SR-4. Remove the text, keep the fact that there was text.

    This exists **before** the retention policy does, and deliberately: OQ-148 is
    open, and a workspace that discovers its own product interpolating something
    sensitive into a system message needs an answer today rather than an answer
    in the release that settles retention. The group goes on counting, so the
    inventory does not quietly lose an entry.
    """
    row = (
        await db.execute(
            REDACT_OBSERVATION,
            {
                "workspace_id": workspace_id,
                "observation_id": observation_id,
                "now": datetime.now(UTC),
            },
        )
    ).one_or_none()
    return row is not None


async def delete_observation(
    db: AsyncSession, workspace_id: str, observation_id: str
) -> bool:
    """Remove the group and its sightings outright.

    Redact is the softer answer and the one the UI leads with; this is here for
    the case redact does not cover — an entire fingerprint group that should
    never have been collected. See :data:`DELETE_OBSERVATION` for why this is not
    the history delete the non-negotiables forbid.
    """
    row = (
        await db.execute(
            DELETE_OBSERVATION,
            {"workspace_id": workspace_id, "observation_id": observation_id},
        )
    ).one_or_none()
    return row is not None


#: The longest suggestion offered. A model name is typed by hand into somebody
#: else's client afterwards, so a long one is a transcription error waiting to
#: happen — and `NAME_PATTERN` caps it at 63 regardless.
_SUGGESTED_NAME_MAX = 40


def suggest_name(body: str, fingerprint: str) -> str:
    """A name derived from the body's opening words, in `NAME_PATTERN`'s shape.

    Falls back to the fingerprint's first characters when the body yields
    nothing usable — a body of pure punctuation, or a redacted group. That
    fallback is deliberately ugly: an unhelpful suggestion is one a person
    replaces, and a plausible-looking wrong one is one they accept.
    """
    words: list[str] = []
    length = 0
    for raw in body.lower().split():
        word = "".join(character for character in raw if character.isalnum())
        # A pure number is dropped rather than kept, because the numbers in an
        # observed system message are the interpolated ones — a suggestion built
        # from them names the request rather than the prompt.
        if not word or word.isdigit():
            continue
        # Whole words only. Truncating mid-word gives `today-i`, which reads as a
        # typo somebody made rather than as a suggestion somebody should replace.
        if length and length + len(word) + 1 > _SUGGESTED_NAME_MAX:
            break
        length += len(word) + (1 if length else 0)
        words.append(word)

    candidate = "-".join(words)[:_SUGGESTED_NAME_MAX].strip("-")
    if candidate and candidate[0].isalnum():
        return candidate
    return f"observed-{fingerprint[:8]}"


def _observation_row(row: Any) -> ObservationRow:
    return ObservationRow(
        id=row["id"],
        workspace_id=row["workspace_id"],
        namespace=row["namespace"],
        fingerprint=row["fingerprint"],
        body_hash=row["body_hash"],
        current_body=row["current_body"],
        inferred_variables=tuple(row["inferred_variables"] or ()),
        sighting_count=row["sighting_count"],
        first_seen_at=row["first_seen_at"],
        last_seen_at=row["last_seen_at"],
        upstream_models=tuple(row["upstream_models"] or ()),
        adopted_prompt_id=row["adopted_prompt_id"],
        adopted_by=row["adopted_by"],
        adopted_at=row["adopted_at"],
        dismissed_by=row["dismissed_by"],
        dismissed_at=row["dismissed_at"],
        dismissal_reason=row["dismissal_reason"],
        redacted_at=row["redacted_at"],
    )
