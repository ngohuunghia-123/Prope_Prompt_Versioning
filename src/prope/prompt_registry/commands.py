"""Every write in the module, each appending its history event in the caller's transaction.

**Nothing here opens a transaction and nothing here commits** (ADR-0023). The
route opens a ``workspace_transaction``; release-control opens its own and its
release row, its history append and the write below share it. That is what makes
INT-013's *"there is no release without a trail"* true by transaction rather than
by convention — and it is why every raise in this file is allowed to abort a
caller's work.

**The three inbound commands take the caller's session for the same reason
``may()`` does.** A command that opened its own would commit a released pointer
whose release record could still roll back, which is the one ordering this
product cannot survive.

**BR-03 is not re-implemented here.** :func:`set_released_revision` contains no
check that the target revision is ``Approved``: the composite foreign key in
revision 0008 is what refuses that write, and an ``if`` beside it would be a
second answer that can disagree with the first — and the one that a code path
nobody reviewed could skip.
"""

import json
from datetime import UTC, datetime

import structlog
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from prope.errors import ErrorCode
from prope.prompt_registry import events, repository
from prope.prompt_registry.domain import (
    STATUS_TRANSITIONS,
    IllegalTransition,
    NothingReleased,
    NothingToUpdate,
    PromptRow,
    ReleasedPointerConflict,
    RevisionConflict,
    RevisionDraft,
    RevisionRead,
    RevisionStatus,
)
from prope.prompt_registry.observability import revision_conflict_total, revision_created_total
from prope.session_auth import ManagementRefusal

log = structlog.get_logger(__name__)

__all__ = [
    "PROMPT_ID_PREFIX",
    "REVISION_ID_PREFIX",
    "clear_released_revision",
    "create_prompt",
    "create_revision",
    "retire_prompt",
    "set_released_revision",
    "set_revision_status",
    "update_prompt",
]

#: A-045 / ADR-0003. Minted at the one site that inserts, so no caller can
#: collide on a primary key it chose.
PROMPT_ID_PREFIX = "prm_"

REVISION_ID_PREFIX = "rev_"

#: How many times a revision-number collision is retried before the author is
#: told somebody else saved first. **One**, and the failure mode says why: the
#: loser retries once automatically, and on a second collision the editor
#: reloads with both bodies preserved client-side. A longer loop turns a
#: two-writer race into a queue nobody asked for.
REVISION_RETRIES = 1

INSERT_PROMPT_PROPERTY = text(
    """
    INSERT INTO registry.prompt_property (
        id, workspace_id, namespace, name, title, purpose, owner_id,
        access_level, status, tags, created_at, updated_at
    ) VALUES (
        :id, :workspace_id, :namespace, :name, :title, :purpose, :owner_id,
        :access_level, 'active', CAST(:tags AS text[]), :now, :now
    )
    """
)

#: Every optional field switches itself off with a NULL parameter, so one
#: statement serves a title-only edit and a five-field one. ``updated_at`` moves
#: unconditionally — a PATCH that changed nothing still updated nothing, and the
#: caller only reaches this statement when something did change.
UPDATE_PROMPT_PROPERTY = text(
    """
    UPDATE registry.prompt_property
       SET title        = COALESCE(CAST(:title AS text), title),
           purpose      = COALESCE(CAST(:purpose AS text), purpose),
           owner_id     = COALESCE(CAST(:owner_id AS text), owner_id),
           access_level = COALESCE(CAST(:access_level AS text), access_level),
           tags         = COALESCE(CAST(:tags AS text[]), tags),
           updated_at   = :now
     WHERE id = :prompt_id
    """
)

RETIRE_PROMPT_PROPERTY = text(
    """
    UPDATE registry.prompt_property
       SET status = 'retired', updated_at = :now
     WHERE id = :prompt_id AND released_version_id IS NULL
    """
)

INSERT_REVISION = text(
    """
    INSERT INTO registry.revision (
        version_id, workspace_id, prompt_id, revision_number, body,
        original_body, original_format, original_filename,
        conversion_model, conversion_schema_version,
        provider_config_id, upstream_model, parameters, fallback_answer,
        change_summary, author_id, status, created_at
    ) VALUES (
        :version_id, :workspace_id, :prompt_id, :revision_number, :body,
        :original_body, :original_format, :original_filename,
        :conversion_model, :conversion_schema_version,
        :provider_config_id, :upstream_model, CAST(:parameters AS jsonb),
        :fallback_answer, :change_summary, :author_id, 'Draft', :now
    )
    """
)

#: INT-012's write. The status column is the ONLY one ``prope_app`` may update on
#: this table — revision 0008 grants it column-level and nothing else — so a
#: statement here that touched a second column would be refused by the engine
#: rather than by review.
UPDATE_REVISION_STATUS = text(
    """
    UPDATE registry.revision
       SET status = :status
     WHERE version_id = :version_id
    """
)

LOAD_REVISION_STATUS = text(
    """
    SELECT status
    FROM   registry.revision
    WHERE  version_id = :version_id
    FOR    UPDATE
    """
)

#: INT-013's compare-and-set, as one statement. ``IS NOT DISTINCT FROM`` rather
#: than ``=`` because the expected value is legitimately NULL on a first release,
#: and ``NULL = NULL`` is NULL — which would make every first release look like a
#: lost race.
SET_RELEASED_REVISION = text(
    """
    UPDATE registry.prompt_property
       SET released_version_id = :version_id,
           released_at         = :now,
           updated_at          = :now
     WHERE id = :prompt_id
       AND released_version_id IS NOT DISTINCT FROM CAST(:expected AS text)
    """
)

CLEAR_RELEASED_REVISION = text(
    """
    UPDATE registry.prompt_property
       SET released_version_id = NULL,
           released_at         = NULL,
           updated_at          = :now
     WHERE id = :prompt_id AND released_version_id IS NOT NULL
    """
)

LOAD_RELEASED_POINTER = text(
    """
    SELECT released_version_id
    FROM   registry.prompt_property
    WHERE  id = :prompt_id
    FOR    UPDATE
    """
)


def _model_name_taken(namespace: str, name: str) -> ManagementRefusal:
    return ManagementRefusal(
        status_code=409,
        code=ErrorCode.REGISTRY_MODEL_NAME_TAKEN,
        message="a prompt in this workspace already uses that model name",
        details={"namespace": namespace, "name": name},
    )


def _unknown_provider_config(provider_config_id: str) -> ManagementRefusal:
    return ManagementRefusal(
        status_code=422,
        code=ErrorCode.REGISTRY_UNKNOWN_PROVIDER_CONFIG,
        message="no provider configuration with that id exists in this workspace",
        details={"provider_config_id": provider_config_id},
    )


async def create_prompt(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    namespace: str,
    name: str,
    title: str,
    purpose: str,
    owner_id: str,
    access_level: str,
    tags: list[str],
    now: datetime,
) -> PromptRow:
    """Register a prompt property. Private by default unless the caller says otherwise.

    ``owner_id`` is a parameter rather than always the actor: A-007 lets an Admin
    register a prompt on somebody's behalf, and the route defaults it to the
    actor. It is a **value**, not a foreign key into ``access.user`` — the same
    posture ``history_event.actor_id`` takes, and what makes ADR-0054's tombstone
    cost this module nothing.

    ``search_text`` is not written here. The ``BEFORE INSERT`` trigger fills it,
    which is what makes a freshly registered prompt findable by its own title
    before it has a single revision.
    """
    prompt_id = f"{PROMPT_ID_PREFIX}{ULID()}"

    try:
        await db.execute(
            INSERT_PROMPT_PROPERTY,
            {
                "id": prompt_id,
                "workspace_id": workspace_id,
                "namespace": namespace,
                "name": name,
                "title": title,
                "purpose": purpose,
                "owner_id": owner_id,
                "access_level": access_level,
                "tags": tags,
                "now": now,
            },
        )
    except IntegrityError as error:
        raise _model_name_taken(namespace, name) from error

    await events.property_created(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        prompt_id=prompt_id,
        occurred_at=now,
    )

    row = await repository.load_prompt(db, prompt_id)
    if row is None:
        raise RuntimeError(
            f"{prompt_id} was inserted and cannot be read back in the same transaction; the "
            "tenant policy's WITH CHECK accepted a workspace_id that its USING clause refuses"
        )
    return row


async def update_prompt(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    title: str | None,
    purpose: str | None,
    owner_id: str | None,
    access_level: str | None,
    tags: list[str] | None,
    now: datetime,
) -> PromptRow:
    """PATCH the mutable half of a prompt property, and record what deserves an event.

    Three of the five editable fields have no history event of their own — a
    title, a purpose and a tag list are not decisions. The two that do,
    ``owner_id`` and ``access_level``, get one each, and only when the value
    actually moved: an event saying the owner changed to the owner it already had
    is noise in the one place noise is expensive.

    The model name is **not** editable and is not a parameter here. A-021 makes it
    immutable once created, because it is what a consuming product calls and
    renaming it breaks every caller silently.
    """
    current = await repository.load_prompt_for_update(db, prompt_id)
    if current is None:
        raise NothingToUpdate(prompt_id)

    await db.execute(
        UPDATE_PROMPT_PROPERTY,
        {
            "prompt_id": prompt_id,
            "title": title,
            "purpose": purpose,
            "owner_id": owner_id,
            "access_level": access_level,
            "tags": tags,
            "now": now,
        },
    )

    if owner_id is not None and owner_id != current.owner_id:
        await events.owner_changed(
            db,
            workspace_id=workspace_id,
            actor_id=actor_id,
            prompt_id=prompt_id,
            occurred_at=now,
        )

    if access_level is not None and access_level != current.access_level:
        await events.access_level_changed(
            db,
            workspace_id=workspace_id,
            actor_id=actor_id,
            prompt_id=prompt_id,
            occurred_at=now,
        )

    updated = await repository.load_prompt(db, prompt_id)
    assert updated is not None
    return updated


async def retire_prompt(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    now: datetime,
) -> PromptRow:
    """A-052. Refused while a release is active, and the refusal names the release.

    The guard is in the statement's ``WHERE`` clause rather than in a preceding
    ``if``, so the check and the write are one atomic act: a release landing
    between a check and an update would otherwise retire a prompt the gateway is
    still serving. A zero row count is the refusal, and the pointer is read
    afterwards only to say **which** release it was.

    INT-014 is the only way to clear that pointer. This module cannot withdraw a
    release on its own behalf, which is A-041 and ADR-0001 in the one place
    somebody would be tempted to work around them.
    """
    result = await db.execute(RETIRE_PROMPT_PROPERTY, {"prompt_id": prompt_id, "now": now})

    if result.rowcount == 0:
        current = await repository.load_prompt(db, prompt_id)
        if current is None:
            raise NothingToUpdate(prompt_id)
        raise ManagementRefusal(
            status_code=409,
            code=ErrorCode.REGISTRY_ACTIVE_RELEASE,
            message="this prompt has an active release and cannot be retired until it is withdrawn",
            details={
                "released_version_id": current.released_version_id,
                "model_name": current.model_name,
            },
        )

    await events.retired(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        prompt_id=prompt_id,
        occurred_at=now,
    )

    retired_row = await repository.load_prompt(db, prompt_id)
    assert retired_row is not None
    return retired_row


async def create_revision(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    draft: RevisionDraft,
    now: datetime,
) -> RevisionRead:
    """A-002's immutable next revision, with its number allocated in this transaction.

    **A savepoint per attempt, not a bare retry** (A-048). A unique-constraint
    violation poisons the enclosing transaction, so a retry that simply re-issued
    the INSERT would fail on a connection that can no longer execute anything.
    ``begin_nested`` gives each attempt its own rollback point, which is what
    makes *the loser retries once automatically* implementable at all.

    The retry deliberately does **not** re-read the body or re-check permission:
    the same author is saving the same text, one revision number higher.

    **Only ``uq_revision_prompt_id`` is a conflict.** Every other integrity
    violation on this INSERT is re-raised untouched, because a retry cannot help
    with any of them and calling one a conflict tells the author *somebody else
    saved first* about a row nobody else touched — a message they cannot act on,
    on top of a metric that now counts it as contention.

    The history append is outside the savepoint loop, in the caller's
    transaction, so a rollback leaves neither the revision nor the event —
    ADR-0023's whole point, and a hole in the audit trail is what the alternative
    buys.
    """
    parameters = _json(draft.parameters)

    for attempt in range(REVISION_RETRIES + 1):
        revision_number = await repository.next_revision_number(db, prompt_id)
        version_id = f"{REVISION_ID_PREFIX}{ULID()}"
        try:
            async with db.begin_nested():
                await db.execute(
                    INSERT_REVISION,
                    {
                        "version_id": version_id,
                        "workspace_id": workspace_id,
                        "prompt_id": prompt_id,
                        "revision_number": revision_number,
                        "body": draft.body,
                        "original_body": draft.original_body or draft.body,
                        "original_format": draft.original_format,
                        "original_filename": draft.original_filename,
                        "conversion_model": draft.conversion_model,
                        "conversion_schema_version": draft.conversion_schema_version,
                        "provider_config_id": draft.provider_config_id,
                        "upstream_model": draft.upstream_model,
                        "parameters": parameters,
                        "fallback_answer": draft.fallback_answer,
                        "change_summary": draft.change_summary,
                        "author_id": actor_id,
                        "now": now,
                    },
                )
        except IntegrityError as error:
            if _violates(error, "fk_revision_provider_config_id"):
                raise _unknown_provider_config(str(draft.provider_config_id)) from error
            if not _violates(error, "uq_revision_prompt_id"):
                raise
            revision_conflict_total.inc()
            if attempt == REVISION_RETRIES:
                raise RevisionConflict(prompt_id, revision_number) from error
            continue
        break

    await events.revision_created(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        prompt_id=prompt_id,
        version_id=version_id,
        occurred_at=now,
    )

    revision_created_total.inc()

    created = await repository.load_revision(db, version_id)
    assert created is not None
    return created


def _json(parameters: dict[str, object]) -> str:
    """``parameters`` as a jsonb literal.

    A raw ``text()`` carries no type information, so a bound dict would reach
    asyncpg's jsonb encoder and raise from inside a codec — the same reason
    ``property_history.append`` serialises its ``details`` by hand and casts in
    the statement.
    """
    return json.dumps(parameters)


def _violates(error: IntegrityError, constraint: str) -> bool:
    """Which constraint refused, read from the driver's own exception.

    The name is matched rather than parsed out of a message because
    ``prope.db.metadata``'s naming convention makes every constraint name
    deterministic — that is what the convention is for, and it is what lets a
    caller branch on *which* rule was broken instead of on the fact that
    something was.
    """
    return constraint in str(getattr(error, "orig", error))


async def set_revision_status(
    db: AsyncSession,
    *,
    version_id: str,
    status: RevisionStatus,
    decision_id: str,
) -> None:
    """INT-012. The transition is validated **here**, so the state machine lives once.

    ADR-0008's whole content: release-control decides *whether* to ask and this
    module decides whether the ask is legal, so release-control writes no table it
    does not own — and ``revision.status`` in particular, which is the value
    BR-03's released-pointer constraint reads.

    **Not idempotent.** ``Approved -> Approved`` is absent from
    :data:`~prope.prompt_registry.domain.STATUS_TRANSITIONS`, so re-issuing a
    transition that already happened raises rather than silently succeeding —
    which is what makes a double-submit visible instead of absorbed.

    **``decision_id`` is recorded, not verified, and that is a limit rather than
    an omission.** INT-012 says the command raises on a ``decision_id`` that does
    not exist; the record it would have to read lives in release-control, and
    prompt-registry reading it is the forbidden edge A-041 and ADR-0001 exist to
    prevent. What is checkable here is that the caller supplied one, and that is
    checked. The existence of the decision is guaranteed by the transaction the
    caller opened around both writes.
    """
    if not decision_id.strip():
        raise ValueError(
            "set_revision_status was called with no decision_id; the transition is only "
            "legitimate because a recorded decision justifies it, and an unattributed status "
            "move is the thing ADR-0008 exists to make impossible"
        )

    current = await db.scalar(LOAD_REVISION_STATUS, {"version_id": version_id})
    if current is None:
        raise IllegalTransition(version_id, None, status)

    resolved = RevisionStatus(current)
    if status not in STATUS_TRANSITIONS[resolved]:
        raise IllegalTransition(version_id, resolved, status)

    await db.execute(
        UPDATE_REVISION_STATUS, {"version_id": version_id, "status": status.value}
    )


async def set_released_revision(
    db: AsyncSession,
    *,
    prompt_id: str,
    version_id: str,
    release_id: str,
    expected_current_version_id: str | None = None,
) -> None:
    """INT-013. The only write to the released pointer in the entire system.

    **There is no ``if`` here checking that the target is Approved**, and its
    absence is the design. ``fk_prompt_property_released_version_id`` refuses
    that write at the engine, which survives a code path nobody reviewed —
    BR-03 is non-negotiable and a constraint is the only enforcement that cannot
    be skipped by the next caller.

    The compare-and-set is the ``WHERE`` clause. A mismatch means somebody
    released something else while this reviewer had the screen open, and
    overwriting it silently is how a release nobody decided reaches production.

    ``release_id`` is not written to this table. The release record is
    release-control's and lives in its schema; what this module stores is the
    pointer, which is A-041's *"a field on the prompt property"* and nothing
    more. The parameter is in the signature because INT-013 puts it there and
    because a caller that has no release id has not made a decision yet.
    """
    if not release_id.strip():
        raise ValueError(
            "set_released_revision was called with no release_id; a released pointer with no "
            "release record behind it is the exact state BR-03 and ADR-0001 exist to prevent"
        )

    result = await db.execute(
        SET_RELEASED_REVISION,
        {
            "prompt_id": prompt_id,
            "version_id": version_id,
            "expected": expected_current_version_id,
            "now": _now(),
        },
    )

    if result.rowcount == 0:
        actual = await db.scalar(LOAD_RELEASED_POINTER, {"prompt_id": prompt_id})
        raise ReleasedPointerConflict(prompt_id, expected_current_version_id, actual)


async def clear_released_revision(db: AsyncSession, *, prompt_id: str, release_id: str) -> None:
    """INT-014. A withdrawal, and a separate command rather than a NULL argument.

    ADR-0009's reason is structural: ``set_released_revision(..., NULL)`` would
    need the Approved-only constraint to grow a NULL carve-out, and a carve-out in
    the constraint enforcing BR-03 is a hole in a non-negotiable rule bought to
    save one function signature. The constraint here needs none — ``MATCH
    SIMPLE`` skips the check when either column is NULL, which is exactly the
    state a withdrawal leaves behind.

    **Raises when nothing is released.** A withdrawal of nothing is a caller bug,
    not a no-op, and absorbing it would let release-control write a
    mandatory-reason ``release_withdrawn`` event describing an act that did not
    happen.

    The cost, stated where it is felt: the gateway may keep serving the withdrawn
    revision for **up to 30 seconds** afterwards. Its resolution cache expires and
    nothing invalidates it (ADR-0012), and this module notifies nobody.
    """
    if not release_id.strip():
        raise ValueError("clear_released_revision was called with no release_id")

    result = await db.execute(
        CLEAR_RELEASED_REVISION, {"prompt_id": prompt_id, "now": _now()}
    )

    if result.rowcount == 0:
        raise NothingReleased(prompt_id)


def _now() -> datetime:
    return datetime.now(UTC)
