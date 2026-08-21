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

from sqlalchemy import Select, and_, func, or_, select, text, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from prope.access_control.domain import FilterMode, VisibleFilter
from prope.prompt_registry.domain import (
    FolderRow,
    ModelName,
    PromptRow,
    PromptStatus,
    ReleasedListing,
    ResolveMiss,
    RevisionBinding,
    RevisionRead,
    RevisionStatus,
    default_folder_color,
)
from prope.prompt_registry.models import folder, prompt_property, revision
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
    "count_prompts_in_namespace",
    "list_folders",
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
    # ADR-0067's four. On the SELECT list rather than pulled per caller because
    # `prompt-readiness` reads them on every card and the alternative is a second
    # round trip per prompt on the aggregate import view.
    prompt_property.c.audience,
    prompt_property.c.untrusted_input,
    prompt_property.c.acts,
    prompt_property.c.sensitivity,
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

#: ADR-0062's entry rule, second half. The namespaces this workspace USES — the
#: union of declared folder rows and namespaces observed on prompts, which is the
#: same union :func:`list_folders` computes for the folder grid, minus everything
#: the grid needs and the gateway does not.
#:
#: **The union is why the folder table has no foreign key** (migration 0016): a
#: prompt may sit in a namespace nobody has named, and a rule that only knew about
#: declared rows would forward calls addressed to real, in-use namespaces.
LIST_NAMESPACES = text(
    """
    SELECT slug AS namespace
    FROM   registry.folder
    WHERE  workspace_id = :workspace_id
    UNION
    SELECT DISTINCT namespace
    FROM   registry.prompt_property
    WHERE  workspace_id = :workspace_id
    """
)

LOAD_REVISION = text(
    """
    SELECT version_id, prompt_id, workspace_id, revision_number, body,
           original_body, original_format, original_filename,
           conversion_model, conversion_schema_version,
           provider_config_id, upstream_model, parameters, fallback_answer,
           change_summary, tags, author_id, status,
           audience, untrusted_input, acts, sensitivity, created_at
    FROM   registry.revision
    WHERE  version_id = :version_id
    """
)

#: The prompt's newest revision by number, released or not.
#:
#: `LOAD_RELEASED_REVISION` below answers a different question and prompt-search
#: needs both: what production serves, and what the author last saved. Ordering
#: by `revision_number` rather than `created_at` because the number is allocated
#: inside the writing transaction (A-048) and is therefore the only total order
#: two concurrent saves agree on.
LOAD_LATEST_REVISION = text(
    """
    SELECT version_id, prompt_id, workspace_id, revision_number, body,
           original_body, original_format, original_filename,
           conversion_model, conversion_schema_version,
           provider_config_id, upstream_model, parameters, fallback_answer,
           change_summary, tags, author_id, status,
           audience, untrusted_input, acts, sensitivity, created_at
    FROM   registry.revision
    WHERE  prompt_id = :prompt_id
    ORDER  BY revision_number DESC
    LIMIT  1
    """
)

#: The newest revision of each of several prompts, in one round trip.
#:
#: ``DISTINCT ON`` rather than a window function because it is the shape Postgres
#: optimises for exactly this — the index on ``(prompt_id, revision_number)``
#: answers it by walking one entry per prompt. The caller is the comparison
#: funnel, which holds up to twenty candidates and needs every body to compare
#: blocks; twenty sequential ``load_latest_revision`` calls would put twenty
#: round trips on a request that already sits behind an embedding call.
LOAD_LATEST_REVISIONS = text(
    """
    SELECT DISTINCT ON (prompt_id)
           version_id, prompt_id, workspace_id, revision_number, body,
           original_body, original_format, original_filename,
           conversion_model, conversion_schema_version,
           provider_config_id, upstream_model, parameters, fallback_answer,
           change_summary, tags, author_id, status,
           audience, untrusted_input, acts, sensitivity, created_at
    FROM   registry.revision
    WHERE  prompt_id = ANY(:prompt_ids)
    ORDER  BY prompt_id, revision_number DESC
    """
)

LOAD_RELEASED_REVISION = text(
    """
    SELECT r.version_id, r.prompt_id, r.workspace_id, r.revision_number, r.body,
           r.original_body, r.original_format, r.original_filename,
           r.conversion_model, r.conversion_schema_version,
           r.provider_config_id, r.upstream_model, r.parameters, r.fallback_answer,
           r.change_summary, r.tags, r.author_id, r.status,
           r.audience, r.untrusted_input, r.acts, r.sensitivity, r.created_at
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
           change_summary, tags, author_id, status,
           audience, untrusted_input, acts, sensitivity, created_at
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
           audience, untrusted_input, acts, sensitivity,
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
        audience=row["audience"],
        untrusted_input=row["untrusted_input"],
        acts=row["acts"],
        sensitivity=row["sensitivity"],
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
        tags=tuple(row.get("tags") or ()),
        author_id=row["author_id"],
        status=RevisionStatus(row["status"]),
        audience=row["audience"],
        untrusted_input=row["untrusted_input"],
        acts=row["acts"],
        sensitivity=row["sensitivity"],
        created_at=row["created_at"],
    )


def _visible(statement: Select[Any], visible: VisibleFilter, actor_id: str) -> Select[Any]:
    """INT-002, ORed with the two predicates this module can evaluate itself.

    ``ALL`` adds nothing: a role binding grants ``prompt.read`` workspace-wide and
    RLS is what bounds *workspace-wide* to one tenant.

    **Every other mode falls through to the same disjunction, and there is only
    one branch in this function.** That is the design rather than an oversight,
    and ADR-0061 is what makes it load-bearing. access-control cannot see
    ownership (ADR-0020), so its `ids` are the **granted** ones only; the caller
    ORs in ``owner_id = actor`` and ``access_level = 'workspace'``, which are the
    two predicates it can answer itself. ``NONE`` is that same disjunction with
    both sets empty — never an error, and never an unfiltered query.

    ``namespaces`` is a fourth disjunct rather than a fourth branch, because an
    actor can hold three per-prompt grants **and** two folder grants and both
    have to count. A mutually-exclusive fourth mode could not have expressed that
    — which is a correction to how INT-002 was first written up, found here.
    Applying both unconditionally is also the safe direction: a consumer that had
    never heard of ``namespaces`` would narrow rather than widen.
    """
    if visible.mode is FilterMode.ALL:
        return statement

    return statement.where(
        or_(
            prompt_property.c.owner_id == actor_id,
            prompt_property.c.access_level == "workspace",
            prompt_property.c.id.in_(visible.ids) if visible.ids else False,
            prompt_property.c.namespace.in_(visible.namespaces)
            if visible.namespaces
            else False,
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


#: The latest revision of every prompt in the tenant, one row each.
#:
#: ``DISTINCT ON`` rather than a correlated ``max(revision_number)`` because the
#: status and the number have to come off the **same** row: a prompt whose r4 is
#: a Draft and whose r3 is Approved is a Draft, and a subquery that took the
#: number from one row and the status from another would call it Approved.
_LATEST_REVISION = (
    select(revision.c.prompt_id, revision.c.status)
    .distinct(revision.c.prompt_id)
    .order_by(revision.c.prompt_id, revision.c.revision_number.desc())
    .subquery("latest_revision")
)

#: What the folder cards count, and the same fold the client applies to a single
#: prompt (``promptListStatus``) — restated in SQL because the counts must be
#: over every prompt in the namespace, not over the page the client happened to
#: fetch. A retired prompt is in none of the three buckets and in
#: ``prompt_count``: it is still in the drawer, it is just not in flight.
_IS_RETIRED = prompt_property.c.status == PromptStatus.RETIRED.value
_IS_RELEASED = prompt_property.c.released_version_id.isnot(None)
_LATEST_STATUS = _LATEST_REVISION.c.status

#: "In use" counts as approved, exactly as the client's folder derivation does.
#: A-065 makes in-use a derived state of an Approved revision, so a card that
#: listed them apart would be splitting one revision across two numbers.
_APPROVED = and_(
    ~_IS_RETIRED, or_(_IS_RELEASED, _LATEST_STATUS == RevisionStatus.APPROVED.value)
)
_IN_REVIEW = and_(~_IS_RETIRED, ~_IS_RELEASED, _LATEST_STATUS == RevisionStatus.IN_REVIEW.value)
_DRAFT = and_(
    ~_IS_RETIRED,
    ~_IS_RELEASED,
    or_(_LATEST_STATUS == RevisionStatus.DRAFT.value, _LATEST_STATUS.is_(None)),
)


async def list_folders(
    db: AsyncSession, *, actor_id: str, visible: VisibleFilter
) -> tuple[FolderRow, ...]:
    """The folder list: declared rows ∪ observed namespaces, counted in SQL.

    **A full outer join, because both halves are optional.** A row in
    ``registry.folder`` with no prompts is the empty folder the registration flow
    creates before its first prompt exists; a namespace with no folder row is
    every prompt created through the API, and every prompt that predates this
    table. Dropping either side would break one of those, and an inner join
    breaks both.

    **The counts run through :func:`_visible`, so they are per-actor.** This is
    the one thing in the query that is not merely arithmetic: a card reading "12
    prompt" on a folder whose list shows two would disclose the existence of ten
    private prompts, which is exactly what BR-01 closes as not-found. The
    consequence is that a folder can count zero and still refuse deletion — the
    delete path counts without the filter, on purpose, because emptiness is a
    fact about the namespace rather than about the reader.

    Undeclared rows get their stand-ins here rather than in the client: the name
    is the capitalised slug and the description is the ``slug/*`` model-name
    pattern, so the two halves of the union arrive in one shape and the caller
    never branches on which it got.
    """
    counts = (
        select(
            prompt_property.c.namespace.label("slug"),
            func.count().label("prompt_count"),
            func.count().filter(_APPROVED).label("approved_count"),
            func.count().filter(_IN_REVIEW).label("in_review_count"),
            func.count().filter(_DRAFT).label("draft_count"),
            func.max(prompt_property.c.updated_at).label("updated_at"),
        )
        .select_from(
            prompt_property.outerjoin(
                _LATEST_REVISION, _LATEST_REVISION.c.prompt_id == prompt_property.c.id
            )
        )
        .group_by(prompt_property.c.namespace)
    )
    observed = _visible(counts, visible, actor_id).subquery("observed")

    slug = func.coalesce(folder.c.slug, observed.c.slug).label("slug")
    statement = (
        select(
            slug,
            folder.c.name,
            folder.c.description,
            folder.c.color,
            func.coalesce(observed.c.prompt_count, 0).label("prompt_count"),
            func.coalesce(observed.c.approved_count, 0).label("approved_count"),
            func.coalesce(observed.c.in_review_count, 0).label("in_review_count"),
            func.coalesce(observed.c.draft_count, 0).label("draft_count"),
            # GREATEST ignores NULLs, which is what makes one expression serve an
            # empty declared folder (no prompt timestamp) and an observed one (no
            # row timestamp) without a CASE.
            func.greatest(folder.c.updated_at, observed.c.updated_at).label("updated_at"),
        )
        .select_from(folder.join(observed, folder.c.slug == observed.c.slug, full=True))
        .order_by(func.coalesce(observed.c.prompt_count, 0).desc(), slug.asc())
    )

    rows = (await db.execute(statement)).mappings().all()
    return tuple(_folder(row) for row in rows)


def _folder(row: Any) -> FolderRow:
    slug = row["slug"]
    declared = row["name"] is not None
    return FolderRow(
        slug=slug,
        name=row["name"] if declared else slug[:1].upper() + slug[1:],
        # A model-name pattern, not prose, so it needs no catalogue key.
        description=row["description"] if declared else f"{slug}/*",
        color=row["color"] if declared else default_folder_color(slug),
        declared=declared,
        prompt_count=row["prompt_count"],
        approved_count=row["approved_count"],
        in_review_count=row["in_review_count"],
        draft_count=row["draft_count"],
        updated_at=row["updated_at"],
    )


async def count_prompts_in_namespace(db: AsyncSession, namespace: str) -> int:
    """How many prompts carry this namespace, tenant-wide. Bounded by RLS only.

    **No visibility filter, and that is the point.** :func:`list_folders` counts
    what the reader may see; this counts what is *there*. A delete that succeeded
    because the caller could not see the three prompts in the namespace would
    unname a folder somebody else is working in, and the emptiness the refusal
    turns on is a fact about the namespace rather than about the reader.
    """
    total = await db.scalar(
        select(func.count())
        .select_from(prompt_property)
        .where(prompt_property.c.namespace == namespace)
    )
    return int(total or 0)


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


async def load_latest_revision(db: AsyncSession, prompt_id: str) -> RevisionRead | None:
    """The newest revision of a prompt. ``None`` when it has none yet."""
    row = (
        await db.execute(LOAD_LATEST_REVISION, {"prompt_id": prompt_id})
    ).mappings().first()
    return None if row is None else _revision(row)


async def load_latest_revisions(
    db: AsyncSession, prompt_ids: list[str]
) -> dict[str, RevisionRead]:
    """The newest revision of each prompt, keyed by ``prompt_id``. One round trip.

    Prompts with no revision yet are simply absent from the mapping — the same
    answer ``load_latest_revision`` gives as ``None``, and the caller must handle
    it either way. RLS bounds the read exactly as it bounds the single-prompt
    version; the caller has already resolved visibility for these ids.
    """
    if not prompt_ids:
        return {}
    rows = (
        await db.execute(LOAD_LATEST_REVISIONS, {"prompt_ids": list(prompt_ids)})
    ).mappings().all()
    return {row["prompt_id"]: _revision(row) for row in rows}


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


#: **INT-044, added 2026-08-20 (ADR-0068).** Every prompt in the workspace that
#: currently has a released revision, whole rows, no cursor and no visibility
#: filter.
#:
#: **It is not `list_prompts` with arguments, for `LIST_RELEASED`'s reason
#: turned around.** That query is the management list and takes a
#: `VisibleFilter` it will not run without — A-118's argument as a signature.
#: This one has no reader to filter for: its caller is `prompt-improvement`'s
#: daily sweep, which runs in `worker` as the system, inside a workspace
#: transaction opened by `access.list_workspaces()` (ADR-0051). Handing it
#: `VisibleFilter.all()` would be lying to a parameter whose whole purpose is to
#: make a caller state whose eyes it is reading through.
#:
#: **BR-01 is not weakened by this**, and the reason is where the output goes:
#: the sweep writes `improvement.finding` rows and never a response, and the
#: inbox that reads them authorises every prompt individually before returning
#: one. A flat list inside a background job is not a disclosure; a flat list on a
#: route is, which is what ADR-0055 refused.
#:
#: `released_version_id IS NOT NULL` is the whole predicate. A prompt that has
#: never been released has no production traffic to have degraded.
LIST_RELEASED_PROMPTS = text(
    """
    SELECT id, workspace_id, namespace, name, title, purpose, owner_id, access_level,
           status, tags, released_version_id, released_at,
           audience, untrusted_input, acts, sensitivity,
           created_at, updated_at
    FROM   registry.prompt_property
    WHERE  workspace_id = :workspace_id
      AND  released_version_id IS NOT NULL
    ORDER  BY id
    LIMIT  :limit
    """
)


async def list_released_prompts(
    db: AsyncSession, workspace_id: str, *, limit: int = 500
) -> tuple[PromptRow, ...]:
    """INT-044. The sweep's worklist: prompts with something in production.

    Bounded rather than exhaustive. A workspace with more than ``limit`` released
    prompts gets the first page by id and the rest on the next pass — which is a
    real gap and is stated rather than hidden: it means a very large workspace's
    tail is swept less often than daily. Fixing it properly is a cursor on the
    sweep, and it is not worth the complexity until a workspace exists that needs
    one.
    """
    rows = (
        await db.execute(
            LIST_RELEASED_PROMPTS, {"workspace_id": workspace_id, "limit": limit}
        )
    ).mappings().all()
    return tuple(_prompt(row) for row in rows)


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


async def list_namespaces(db: AsyncSession, workspace_id: str) -> frozenset[str]:
    """INT-036. Every namespace this workspace uses, declared or merely observed.

    Backs ADR-0062's entry rule: the gateway forwards a call only when the model
    string is **not addressed to a namespace this workspace uses**, and this is
    the set it tests against. A name inside one of these resolves or refuses
    exactly as it always did, for every key.

    **Why it is here and not in access-control.** The obvious home looked like
    `may_resolve`, which already takes the namespace as a parameter — and that
    would have made access-control read `registry.folder`, which ADR-0020 and the
    module map both forbid. The edge that already exists runs gateway ->
    prompt-registry, so the gateway asks here.

    **A `frozenset`, and the gateway caches it** on ADR-0012's existing 30 s TTL.
    A workspace has folders, not thousands of them, so the set is small; a newly
    created namespace is therefore not recognised for up to one TTL, during which
    a call to it is forwarded and observed rather than refused. That is the same
    staleness ADR-0012 already accepts for the released pointer, in the same
    direction, and it costs one observation row somebody dismisses.

    **Not permission-filtered, and it must not be.** This answers *is Prope
    holding anything under this name* — a fact about the tenant, not about an
    actor — and the caller is a consumer key rather than a person. A-159 prices
    what that discloses: an observe-enabled key can learn which namespaces exist
    and still nothing about which prompt names do.
    """
    rows = (await db.execute(LIST_NAMESPACES, {"workspace_id": workspace_id})).scalars().all()
    return frozenset(rows)


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
