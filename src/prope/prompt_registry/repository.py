"""Every read in the module, and the only place INT-002's filter is applied.

**Permission filtering lives here, not in handlers, and that is a structural
choice rather than a stylistic one** (A-118, T-019). The failure this shape
exists to prevent is not a developer forgetting a check — it is a developer under
deadline pressure writing the list query with **no filter at all** and adding the
check "later". So :func:`list_prompts` cannot be called without a
:class:`~prope.access_control.domain.VisibleFilter`: there is no default, no
``None``, and no keyword that makes it optional.

**The one bypass is named and it pages.**
:func:`unsafe_list_prompts_without_filter` is the only read here that skips the
filter, and it is the only site that increments
``prope_registry_unfiltered_query_total`` — a counter whose whole job is to stay
0 and which ``RegistryUnfilteredQuery`` pages on immediately. Nothing in
production calls it. It exists so that the next person who needs an unfiltered
management list has to type the word ``unsafe`` and set off an alarm, rather than
deleting a ``WHERE`` clause.

**Two kinds of read are deliberately NOT the tripwire's business**, and both are
declared rather than merely absent from the counter:

*By-id reads.* ADR-0020 makes the caller supply ``owner_id`` and ``access_level``
to ``may()``, which means the row has to be read **before** permission can be
decided. :func:`load_prompt` therefore reads one row inside the tenant policy and
the route gates it immediately afterwards, refusing as **not-found** so that a
prompt the actor may not see is byte-identical to one that does not exist
(A-116). A filter here would be answering a question ``may()`` is about to answer
better.

*INT-009 and INT-010.* The gateway's two reads carry their own written scoping
rule — a consumer key holds no grant and no role, and INT-004 applies the key's
scope after the fact. Counting them on the tripwire would leave it permanently
non-zero, which is the one thing a must-stay-0 metric cannot survive.

**The list path is SQLAlchemy Core, and ``resolve()`` is raw SQL.** A-128's
carve-out names ``resolve()`` and the filter set form; the list query is Core
because it composes five optional predicates, and composing SQL text would put an
f-string inside ``text()`` — which
``tests/architecture/test_no_sql_interpolation.py`` refuses outright, and rightly.

**``search_text`` is never selected.** Not in a ``SELECT *``, not by name, not
into a row object — :class:`~prope.prompt_registry.domain.PromptRow` has no field
that could hold it. It appears in exactly one place in this module, as the left
side of the ``ILIKE`` in :func:`list_prompts`, which is what T-017 permits and
all that it permits.
"""

import time
from typing import Any

from sqlalchemy import Select, or_, select, text, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from prope.access_control.domain import FilterMode, VisibleFilter
from prope.prompt_registry.domain import (
    ModelName,
    PromptRow,
    PromptStatus,
    ReleasedListing,
    ResolveMiss,
    RevisionBinding,
    RevisionRead,
    RevisionStatus,
)
from prope.prompt_registry.models import prompt_property
from prope.prompt_registry.observability import (
    resolve_duration_seconds,
    resolve_miss_total,
    search_duration_seconds,
    unfiltered_query_total,
)

__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "count_revisions_binding_provider",
    "list_prompts",
    "list_released",
    "list_revisions",
    "load_prompt",
    "load_prompt_for_update",
    "load_released_revision",
    "load_revision",
    "next_revision_number",
    "resolve",
    "unsafe_list_prompts_without_filter",
]

#: A-045's page size and its ceiling, the same two numbers
#: ``property_history.read`` and ``call_ledger.api`` already use.
DEFAULT_LIMIT = 50

MAX_LIMIT = 200

#: The columns a prompt row is built from. Written out **once**, and
#: ``search_text`` is not among them. A ``select(prompt_property)`` would carry
#: every column including the second copy of the prompt body, which is precisely
#: T-017's list-endpoint leak with the response model as the only thing standing
#: in its way.
PROMPT_COLUMNS = (
    prompt_property.c.id,
    prompt_property.c.workspace_id,
    prompt_property.c.namespace,
    prompt_property.c.name,
    prompt_property.c.title,
    prompt_property.c.purpose,
    prompt_property.c.owner_id,
    prompt_property.c.access_level,
    prompt_property.c.status,
    prompt_property.c.tags,
    prompt_property.c.released_version_id,
    prompt_property.c.released_at,
    prompt_property.c.created_at,
    prompt_property.c.updated_at,
)

#: INT-009's hot path, and the one statement in this module written for a
#: latency target rather than for legibility. One index seek on
#: ``uq_prompt_property_namespace`` and one primary-key lookup through the
#: ``LEFT JOIN``, so *unknown name* and *known name, nothing released* are
#: distinguishable without a second round trip: no row at all is the first, a row
#: whose joined ``version_id`` is NULL is the second.
#:
#: ``workspace_id`` is in the predicate **alongside** the tenant policy, never
#: instead of it — the same posture ``property_history.read`` states for its own.
RESOLVE_RELEASED = text(
    """
    SELECT p.id           AS prompt_id,
           r.version_id,
           r.revision_number,
           r.body,
           r.provider_config_id,
           r.upstream_model,
           r.parameters,
           r.fallback_answer
    FROM   registry.prompt_property AS p
    LEFT   JOIN registry.revision AS r ON r.version_id = p.released_version_id
    WHERE  p.workspace_id = :workspace_id
      AND  p.namespace = :namespace
      AND  p.name = :name
    """
)

#: The pinned form of the above. The pin is two parameters rather than one
#: because ``@3`` and ``@rev_01J…`` are different columns, and a single
#: parameter compared against both would make ``revision_number = 'rev_01J…'``
#: a cast error on the hot path instead of a miss.
#:
#: ``r.status`` is selected because BR-03 guards the *pointer*, not a pin: a pin
#: naming a Draft revision is refused here, which is INT-009's
#: *"a pin whose revision is not Approved is refused"*.
RESOLVE_PINNED = text(
    """
    SELECT p.id           AS prompt_id,
           r.version_id,
           r.revision_number,
           r.body,
           r.provider_config_id,
           r.upstream_model,
           r.parameters,
           r.fallback_answer,
           r.status
    FROM   registry.prompt_property AS p
    LEFT   JOIN registry.revision AS r
           ON  r.prompt_id = p.id
           AND (r.revision_number = CAST(:pin_number AS integer)
                OR r.version_id = CAST(:pin_version_id AS text))
    WHERE  p.workspace_id = :workspace_id
      AND  p.namespace = :namespace
      AND  p.name = :name
    """
)

#: INT-010. Released only, no cursor, no filters — deliberately not the
#: management list query. Reads
#: ``ix_prompt_property_workspace_id_released_version_id``, which is partial on
#: exactly this predicate.
LIST_RELEASED = text(
    """
    SELECT p.namespace, p.name, r.version_id, r.revision_number
    FROM   registry.prompt_property AS p
    JOIN   registry.revision AS r ON r.version_id = p.released_version_id
    WHERE  p.workspace_id = :workspace_id
    ORDER  BY p.namespace, p.name
    """
)

LOAD_REVISION = text(
    """
    SELECT version_id, prompt_id, workspace_id, revision_number, body,
           original_body, original_format, original_filename,
           conversion_model, conversion_schema_version,
           provider_config_id, upstream_model, parameters, fallback_answer,
           change_summary, author_id, status, created_at
    FROM   registry.revision
    WHERE  version_id = :version_id
    """
)

LOAD_RELEASED_REVISION = text(
    """
    SELECT r.version_id, r.prompt_id, r.workspace_id, r.revision_number, r.body,
           r.original_body, r.original_format, r.original_filename,
           r.conversion_model, r.conversion_schema_version,
           r.provider_config_id, r.upstream_model, r.parameters, r.fallback_answer,
           r.change_summary, r.author_id, r.status, r.created_at
    FROM   registry.prompt_property AS p
    JOIN   registry.revision AS r ON r.version_id = p.released_version_id
    WHERE  p.id = :prompt_id
    """
)

#: Reads ``ix_revision_prompt_id_revision_number``. ``before_number`` switches
#: its own disjunct off when NULL, so one statement serves page one and a
#: cursored page — ``property_history.read``'s shape, and the ``CAST`` is there
#: for its reason: without it asyncpg has no type to infer for a NULL parameter.
LIST_REVISIONS = text(
    """
    SELECT version_id, prompt_id, workspace_id, revision_number, body,
           original_body, original_format, original_filename,
           conversion_model, conversion_schema_version,
           provider_config_id, upstream_model, parameters, fallback_answer,
           change_summary, author_id, status, created_at
    FROM   registry.revision
    WHERE  prompt_id = :prompt_id
      AND  (CAST(:before_number AS integer) IS NULL
            OR revision_number < CAST(:before_number AS integer))
    ORDER  BY revision_number DESC
    LIMIT  :limit
    """
)

#: A-048. Allocated **inside the creating transaction** and arbitrated by
#: ``uq_revision_prompt_id`` — this read is the optimistic half and the unique
#: constraint is the pessimistic one. It deliberately takes no lock: locking the
#: parent row would serialise every save on a busy prompt to prevent a collision
#: that the constraint already catches and the caller already retries.
NEXT_REVISION_NUMBER = text(
    """
    SELECT COALESCE(MAX(revision_number), 0) + 1
    FROM   registry.revision
    WHERE  prompt_id = :prompt_id
    """
)

#: INT-016's forbidden direction, answered from THIS side of the boundary.
#: provider-access refuses a delete on the foreign key and then wants to say *how
#: many* revisions bind the configuration without naming them; this is the count
#: it would read if it could, and it is here rather than there because the table
#: belongs to this module.
COUNT_REVISIONS_BINDING_PROVIDER = text(
    """
    SELECT count(*)
    FROM   registry.revision
    WHERE  provider_config_id = :provider_config_id
    """
)

#: The by-id read the write paths take. ``FOR UPDATE`` because every caller is
#: about to write the row it read and the read-modify-write is what a lost update
#: looks like — an owner transfer and an access-level change landing together,
#: with one of them silently gone.
LOAD_PROMPT_FOR_UPDATE = text(
    """
    SELECT id, workspace_id, namespace, name, title, purpose, owner_id,
           access_level, status, tags, released_version_id, released_at,
           created_at, updated_at
    FROM   registry.prompt_property
    WHERE  id = :prompt_id
    FOR    UPDATE
    """
)


def _prompt(row: Any) -> PromptRow:
    return PromptRow(
        id=row["id"],
        workspace_id=row["workspace_id"],
        namespace=row["namespace"],
        name=row["name"],
        title=row["title"],
        purpose=row["purpose"],
        owner_id=row["owner_id"],
        access_level=row["access_level"],
        status=PromptStatus(row["status"]),
        tags=tuple(row["tags"]),
        released_version_id=row["released_version_id"],
        released_at=row["released_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _revision(row: Any) -> RevisionRead:
    return RevisionRead(
        version_id=row["version_id"],
        prompt_id=row["prompt_id"],
        workspace_id=row["workspace_id"],
        revision_number=row["revision_number"],
        body=row["body"],
        original_body=row.get("original_body", row["body"]),
        original_format=row.get("original_format", "legacy"),
        original_filename=row.get("original_filename"),
        conversion_model=row.get("conversion_model"),
        conversion_schema_version=row.get("conversion_schema_version"),
        provider_config_id=row["provider_config_id"],
        upstream_model=row["upstream_model"],
        parameters=dict(row["parameters"]),
        fallback_answer=row["fallback_answer"],
        change_summary=row["change_summary"],
        author_id=row["author_id"],
        status=RevisionStatus(row["status"]),
        created_at=row["created_at"],
    )


def _visible(statement: Select[Any], visible: VisibleFilter, actor_id: str) -> Select[Any]:
    """INT-002's three modes, ORed with the two predicates this module can evaluate.

    ``ALL`` adds nothing: a role binding grants ``prompt.read`` workspace-wide and
    RLS is what bounds *workspace-wide* to one tenant.

    ``IDS`` and ``NONE`` both fall through to the same disjunction, and that is
    the design rather than an oversight. access-control cannot see ownership
    (ADR-0020), so its ``ids`` are the **granted** ones only; the caller ORs in
    ``owner_id = actor`` and ``access_level = 'workspace'``, which are the two
    predicates it can answer itself. ``NONE`` is that same disjunction with an
    empty id list — never an error, and never an unfiltered query.
    """
    if visible.mode is FilterMode.ALL:
        return statement

    return statement.where(
        or_(
            prompt_property.c.owner_id == actor_id,
            prompt_property.c.access_level == "workspace",
            prompt_property.c.id.in_(visible.ids) if visible.ids else False,
        )
    )


async def list_prompts(
    db: AsyncSession,
    *,
    actor_id: str,
    visible: VisibleFilter,
    keyword: str | None = None,
    owner_id: str | None = None,
    status: PromptStatus | None = None,
    access_level: str | None = None,
    tag: str | None = None,
    cursor: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> tuple[PromptRow, ...]:
    """The management list, filtered by INT-002 before anything else is applied.

    ``visible`` and ``actor_id`` are keyword-only and have no defaults. A caller
    that has not thought about visibility cannot call this function at all, which
    is the whole of A-118's argument turned into a signature.

    ``keyword`` matches with ``ILIKE '%term%'`` over the trigram-indexed
    ``search_text``, and the term is folded the same way the trigger folded the
    document — lower case and diacritic-stripped — so ``tieu de`` matches
    ``tiêu đề`` (A-150). Substring semantics are the product requirement A-013
    states and ADR-0048 chose the index for; AC-10 asserts them end to end
    precisely so a future "optimisation" to ``tsvector`` fails a test rather than
    quietly changing what search means.

    Ordered ``updated_at DESC, id DESC`` on
    ``ix_prompt_property_workspace_id_updated_at``. The tie-break on ``id`` is
    not decoration: ``updated_at`` alone is not unique — the search trigger moves
    it on every revision save — and a cursor over a non-unique sort key skips
    rows.
    """
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(
            f"limit={limit} is outside A-045's bound of 1..{MAX_LIMIT}; a page of zero renders "
            "an empty registry, and a page above the cap is how one screen turns a whole "
            "workspace into one response"
        )

    started = time.perf_counter()

    statement = _visible(select(*PROMPT_COLUMNS), visible, actor_id)

    if keyword:
        folded = await _fold(db, keyword)
        statement = statement.where(prompt_property.c.search_text.ilike(f"%{folded}%"))
    if owner_id is not None:
        statement = statement.where(prompt_property.c.owner_id == owner_id)
    if status is not None:
        statement = statement.where(prompt_property.c.status == status.value)
    if access_level is not None:
        statement = statement.where(prompt_property.c.access_level == access_level)
    if tag is not None:
        statement = statement.where(prompt_property.c.tags.any(tag))

    if cursor is not None:
        anchor = (
            await db.execute(
                select(prompt_property.c.updated_at, prompt_property.c.id).where(
                    prompt_property.c.id == cursor
                )
            )
        ).first()
        if anchor is None:
            return ()
        statement = statement.where(
            tuple_(prompt_property.c.updated_at, prompt_property.c.id)
            < tuple_(anchor.updated_at, anchor.id)
        )

    statement = statement.order_by(
        prompt_property.c.updated_at.desc(), prompt_property.c.id.desc()
    ).limit(limit)

    rows = (await db.execute(statement)).mappings().all()

    search_duration_seconds.labels(keyword="yes" if keyword else "no").observe(
        time.perf_counter() - started
    )
    return tuple(_prompt(row) for row in rows)


#: The folding the trigger applied, applied again to the search term. It is a
#: round trip to the server rather than a Python ``unicodedata`` normalisation on
#: purpose: the document was folded by ``registry.unaccent`` with a specific
#: dictionary, and a second implementation of "fold" in another language is two
#: implementations that agree until the day they do not — at which point search
#: silently returns fewer rows, which is the exact failure shape ADR-0048 calls
#: the worst available for a register.
FOLD_TERM = text("SELECT lower(registry.unaccent('registry.unaccent'::regdictionary, :term))")


async def _fold(db: AsyncSession, term: str) -> str:
    folded = await db.scalar(FOLD_TERM, {"term": term})
    return folded or term


async def unsafe_list_prompts_without_filter(
    db: AsyncSession, *, limit: int = DEFAULT_LIMIT
) -> tuple[PromptRow, ...]:
    """Every prompt in the tenant, with no visibility filter. **Trips the tripwire.**

    Nothing in production calls this and nothing should. It exists so that the
    unfiltered query has a name, a counter and a page attached to it — the
    alternative is not "nobody writes one", it is somebody writing it inline with
    a ``# TODO`` and no alarm.

    RLS still bounds the answer to one workspace. That is not the point: the
    point is that BR-01 makes prompts private *within* a workspace, and this
    function returns the ones the actor holds no grant for.
    """
    unfiltered_query_total.inc()
    rows = (
        await db.execute(
            select(*PROMPT_COLUMNS)
            .order_by(prompt_property.c.updated_at.desc(), prompt_property.c.id.desc())
            .limit(limit)
        )
    ).mappings().all()
    return tuple(_prompt(row) for row in rows)


async def load_prompt(db: AsyncSession, prompt_id: str) -> PromptRow | None:
    """One prompt by id, inside the tenant policy and **before** permission.

    ADR-0020 makes the caller supply ``owner_id`` and ``access_level`` to
    ``may()``, so the row must be read first. Every caller gates the result
    immediately and refuses as not-found when the gate says no — see
    ``api._require_visible_prompt``, which is the only place that decision is
    made.
    """
    row = (
        await db.execute(select(*PROMPT_COLUMNS).where(prompt_property.c.id == prompt_id))
    ).mappings().first()
    return None if row is None else _prompt(row)


async def load_prompt_for_update(db: AsyncSession, prompt_id: str) -> PromptRow | None:
    """:func:`load_prompt` with the row locked for the write that follows."""
    row = (
        await db.execute(LOAD_PROMPT_FOR_UPDATE, {"prompt_id": prompt_id})
    ).mappings().first()
    return None if row is None else _prompt(row)


async def load_revision(db: AsyncSession, version_id: str) -> RevisionRead | None:
    """INT-011's ``get_revision``. RLS bounds it; the caller has checked permission."""
    row = (await db.execute(LOAD_REVISION, {"version_id": version_id})).mappings().first()
    return None if row is None else _revision(row)


async def load_released_revision(db: AsyncSession, prompt_id: str) -> RevisionRead | None:
    """INT-011's ``get_released_revision``. ``None`` when nothing is released."""
    row = (
        await db.execute(LOAD_RELEASED_REVISION, {"prompt_id": prompt_id})
    ).mappings().first()
    return None if row is None else _revision(row)


async def list_revisions(
    db: AsyncSession,
    prompt_id: str,
    *,
    cursor: int | None = None,
    limit: int = DEFAULT_LIMIT,
) -> tuple[RevisionRead, ...]:
    """One prompt's revision chain, newest first.

    The cursor is a ``revision_number`` rather than an opaque id, and that is
    safe here where ``property_history``'s ``seq`` was not: revision numbers are
    per prompt, so the highest one a caller can read is a fact about a prompt
    they already have permission on, not a volume oracle over the whole install.
    """
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit={limit} is outside A-045's bound of 1..{MAX_LIMIT}")

    rows = (
        await db.execute(
            LIST_REVISIONS, {"prompt_id": prompt_id, "before_number": cursor, "limit": limit}
        )
    ).mappings().all()
    return tuple(_revision(row) for row in rows)


async def next_revision_number(db: AsyncSession, prompt_id: str) -> int:
    """A-048's optimistic half. The unique constraint is the arbiter."""
    return int(await db.scalar(NEXT_REVISION_NUMBER, {"prompt_id": prompt_id}) or 1)


async def count_revisions_binding_provider(db: AsyncSession, provider_config_id: str) -> int:
    """How many revisions bind one provider configuration (INT-016's note)."""
    return int(
        await db.scalar(COUNT_REVISIONS_BINDING_PROVIDER, {"provider_config_id": provider_config_id})
        or 0
    )


async def list_released(db: AsyncSession, workspace_id: str) -> tuple[ReleasedListing, ...]:
    """INT-010, backing ``GET /v1/models``. Released only, no cursor, no filters.

    Deliberately **not** :func:`list_prompts` with arguments. Reusing the
    management query here would leak unreleased and unpermitted prompts into the
    gateway's model list through a default argument nobody reviewed, and the
    caller is a consumer key rather than a person — the gateway applies the key's
    scope (INT-004) to what comes back.
    """
    rows = (await db.execute(LIST_RELEASED, {"workspace_id": workspace_id})).mappings().all()
    return tuple(
        ReleasedListing(
            model_name=f"{row['namespace']}/{row['name']}",
            version_id=row["version_id"],
            revision_number=row["revision_number"],
        )
        for row in rows
    )


def _binding(row: Any) -> RevisionBinding:
    return RevisionBinding(
        prompt_id=row["prompt_id"],
        version_id=row["version_id"],
        revision_number=row["revision_number"],
        body=row["body"],
        provider_config_id=row["provider_config_id"],
        upstream_model=row["upstream_model"],
        parameters=dict(row["parameters"]),
        fallback_answer=row["fallback_answer"],
    )


async def resolve(
    db: AsyncSession, workspace_id: str, model_name: ModelName, pin: str | None = None
) -> RevisionBinding | ResolveMiss:
    """INT-009. The released revision's binding, or **which** kind of miss it was.

    The two misses are one 404 to the caller and two lines in
    ``prope_registry_resolve_miss_total``. A caller that could tell them apart
    could enumerate the registry by observing which names refuse differently
    (A-081, A-116); an operator who could not tell them apart would see a
    withdrawal as a rise in typos, which is ADR-0009's whole complaint.

    ``pin`` is ``@<n>`` or ``@<version_id>`` with the ``@`` already stripped by
    the gateway. A pin naming a revision that is not ``Approved`` is a
    ``NO_RELEASE`` miss: BR-03's constraint guards the released *pointer*, and a
    pin does not go through it.
    """
    started = time.perf_counter()

    if pin is None:
        row = (
            await db.execute(
                RESOLVE_RELEASED,
                {
                    "workspace_id": workspace_id,
                    "namespace": model_name.namespace,
                    "name": model_name.name,
                },
            )
        ).mappings().first()
        status_is_approved = True
    else:
        pin_number = int(pin) if pin.isdigit() else None
        row = (
            await db.execute(
                RESOLVE_PINNED,
                {
                    "workspace_id": workspace_id,
                    "namespace": model_name.namespace,
                    "name": model_name.name,
                    "pin_number": pin_number,
                    "pin_version_id": None if pin_number is not None else pin,
                },
            )
        ).mappings().first()
        status_is_approved = row is not None and row["status"] == RevisionStatus.APPROVED.value

    if row is None:
        return _missed(ResolveMiss.UNKNOWN_MODEL, started)
    if row["version_id"] is None or not status_is_approved:
        return _missed(ResolveMiss.NO_RELEASE, started)

    resolve_duration_seconds.labels(outcome="pinned" if pin else "hit").observe(
        time.perf_counter() - started
    )
    return _binding(row)


def _missed(reason: ResolveMiss, started: float) -> ResolveMiss:
    """One site for both metrics, so a branch cannot count one and not the other."""
    resolve_miss_total.labels(reason=reason.value).inc()
    resolve_duration_seconds.labels(outcome="miss").observe(time.perf_counter() - started)
    return reason
