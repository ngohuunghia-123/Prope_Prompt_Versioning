import json
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

import structlog
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from prope.evaluation import events, repository
from prope.evaluation.assertions import compile_assertions
from prope.evaluation.domain import (
    MAX_CASES_PER_SUITE,
    AssertionOutcome,
    AssertionPatternInvalid,
    AttachmentRow,
    CaseDraft,
    CaseOutcome,
    DatasetKind,
    DatasetNameTaken,
    DatasetSpec,
    OutputModality,
    RefusalReason,
    RunRole,
    SuiteNameTaken,
    SuiteRow,
)

log = structlog.get_logger(__name__)

__all__ = [
    "CASE_ID_PREFIX",
    "CASE_RESULT_ID_PREFIX",
    "DATASET_CASE_ID_PREFIX",
    "DATASET_ID_PREFIX",
    "RUN_ID_PREFIX",
    "SUITE_ID_PREFIX",
    "attach_dataset",
    "create_dataset",
    "create_runs",
    "delete_dataset",
    "detach_dataset",
    "mark_completed",
    "mark_interrupted",
    "mark_refused",
    "materialise_attachment",
    "record_case_result",
    "stamp_case_count",
    "stamp_price",
    "update_dataset",
    "write_suite_version",
]

SUITE_ID_PREFIX = "evs_"

CASE_ID_PREFIX = "evc_"

RUN_ID_PREFIX = "evr_"

CASE_RESULT_ID_PREFIX = "evcr_"

DATASET_ID_PREFIX = "dst_"

DATASET_CASE_ID_PREFIX = "dsc_"

INSERT_SUITE = text(
    """
    INSERT INTO evaluation.eval_suite (
        id, workspace_id, prompt_id, name, suite_version, output_modality,
        case_count, created_by, created_at
    ) VALUES (
        :id, :workspace_id, :prompt_id, :name, :suite_version, :output_modality,
        :case_count, :created_by, :now
    )
    """
)

INSERT_CASE = text(
    """
    INSERT INTO evaluation.eval_case (
        id, workspace_id, suite_id, ordinal, name, input_messages,
        input_variables, assertions, created_at
    ) VALUES (
        :id, :workspace_id, :suite_id, :ordinal, :name,
        CAST(:input_messages AS jsonb), CAST(:input_variables AS jsonb),
        CAST(:assertions AS jsonb), :now
    )
    """
)

INSERT_RUN = text(
    """
    INSERT INTO evaluation.eval_run (
        id, workspace_id, prompt_id, version_id, suite_id, role, status, started_by
    ) VALUES (
        :id, :workspace_id, :prompt_id, :version_id, :suite_id, :role, 'queued', :started_by
    )
    """
)

INSERT_CASE_RESULT = text(
    """
    INSERT INTO evaluation.case_result (
        id, workspace_id, run_id, case_id, outcome, assertion_results,
        output_content, latency_ms, input_tokens, output_tokens, error_code,
        attempt_count, created_at
    ) VALUES (
        :id, :workspace_id, :run_id, :case_id, :outcome,
        CAST(:assertion_results AS jsonb), :output_content, :latency_ms,
        :input_tokens, :output_tokens, :error_code, :attempt_count, :now
    )
    """
)

REFUSE_RUN = text(
    """
    UPDATE evaluation.eval_run
       SET status = 'refused', refused_reason = :reason, finished_at = :now
     WHERE id = :run_id AND status IN ('queued', 'running')
    """
)

COMPLETE_RUN = text(
    """
    UPDATE evaluation.eval_run
       SET status = 'completed',
           finished_at = :now,
           pass_count = :pass_count,
           fail_count = :fail_count,
           error_count = :error_count,
           input_tokens = :input_tokens,
           output_tokens = :output_tokens,
           cost_amount = :cost_amount,
           cost_currency = :cost_currency,
           priced_at = :priced_at
     WHERE id = :run_id AND status = 'running'
    """
)

INTERRUPT_RUN = text(
    """
    UPDATE evaluation.eval_run
       SET status = 'interrupted', finished_at = :now
     WHERE id = :run_id AND status = 'running'
    """
)

STAMP_PRICE = text(
    """
    UPDATE evaluation.eval_run
       SET cost_amount = :cost_amount,
           cost_currency = :cost_currency,
           priced_at = :priced_at
     WHERE id = :run_id
    """
)

STAMP_CASE_COUNT = text(
    "UPDATE evaluation.eval_suite SET case_count = :case_count WHERE id = :suite_id"
)

INSERT_DATASET = text(
    """
    INSERT INTO evaluation.dataset (
        id, workspace_id, folder, name, description, kind, tags, output_modality,
        case_count, created_by, created_at, updated_at
    ) VALUES (
        :id, :workspace_id, :folder, :name, :description, :kind, :tags, :output_modality,
        :case_count, :created_by, :now, :now
    )
    """
)

UPDATE_DATASET = text(
    """
    UPDATE evaluation.dataset
       SET folder = :folder,
           name = :name,
           description = :description,
           kind = :kind,
           tags = :tags,
           output_modality = :output_modality,
           case_count = :case_count,
           updated_at = :now
     WHERE id = :id
    """
)

INSERT_DATASET_CASE = text(
    """
    INSERT INTO evaluation.dataset_case (
        id, workspace_id, dataset_id, ordinal, name, input_messages,
        input_variables, assertions, created_at
    ) VALUES (
        :id, :workspace_id, :dataset_id, :ordinal, :name,
        CAST(:input_messages AS jsonb), CAST(:input_variables AS jsonb),
        CAST(:assertions AS jsonb), :now
    )
    """
)

#: An edit replaces the case list rather than reconciling it. Reconciling would
#: need a case id stable across a changed input, and a stable id over changed
#: content is exactly the lie the fingerprint exists to see through.
DELETE_DATASET_CASES = text(
    "DELETE FROM evaluation.dataset_case WHERE dataset_id = :dataset_id"
)

DELETE_DATASET = text("DELETE FROM evaluation.dataset WHERE id = :id")

#: Not a database cascade — ``dataset_attachment.dataset_id`` is a value with no
#: foreign key, because it sometimes names a file in the image. This is the
#: deliberate half of :func:`delete_dataset`.
DELETE_ATTACHMENTS_FOR_DATASET = text(
    "DELETE FROM evaluation.dataset_attachment WHERE dataset_id = :dataset_id"
)

#: ``ON CONFLICT DO NOTHING`` on the primary key, so ticking a dataset twice is
#: the same as ticking it once. The suite-name collision is a *different*
#: constraint and is deliberately not swallowed here — two datasets sharing a
#: suite lineage is a refusal somebody has to see, not an idempotent no-op.
INSERT_ATTACHMENT = text(
    """
    INSERT INTO evaluation.dataset_attachment (
        workspace_id, prompt_id, dataset_id, suite_name, attached_by, attached_at
    ) VALUES (
        :workspace_id, :prompt_id, :dataset_id, :suite_name, :attached_by, :now
    )
    ON CONFLICT (workspace_id, prompt_id, dataset_id) DO NOTHING
    """
)

DELETE_ATTACHMENT = text(
    """
    DELETE FROM evaluation.dataset_attachment
     WHERE prompt_id = :prompt_id AND dataset_id = :dataset_id
    """
)

STAMP_MATERIALISATION = text(
    """
    UPDATE evaluation.dataset_attachment
       SET materialised_suite_id = :suite_id,
           materialised_fingerprint = :fingerprint
     WHERE prompt_id = :prompt_id AND dataset_id = :dataset_id
    """
)


def _new_id(prefix: str) -> str:
    return f"{prefix}{ULID()}"


def _constraint_name(error: IntegrityError) -> str | None:
    """The engine's constraint name, for branching on and never for returning.

    The same two-level unwrap ``call_ledger.api._constraint_name`` documents:
    SQLAlchemy's asyncpg dialect re-raises its own ``IntegrityError`` as
    ``error.orig`` and chains the real asyncpg exception onto ``__cause__``, so
    reading only ``error.orig`` finds nothing — silently — and every mapped
    refusal degrades into a 500. Duplicated rather than imported because
    ``evaluation`` importing ``call_ledger``'s API module would be a dependency
    edge for four lines of driver trivia.
    """
    for candidate in (error.orig, getattr(error.orig, "__cause__", None)):
        name = getattr(candidate, "constraint_name", None)
        if name:
            return str(name)
    return None


async def write_suite_version(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    name: str,
    output_modality: OutputModality,
    cases: Sequence[CaseDraft],
    now: datetime,
) -> SuiteRow:
    if len(cases) > MAX_CASES_PER_SUITE:
        raise AssertionPatternInvalid(
            len(cases), f"a suite holds at most {MAX_CASES_PER_SUITE} cases"
        )

    suite_version = await repository.next_suite_version(db, prompt_id, name)
    suite_id = _new_id(SUITE_ID_PREFIX)

    await db.execute(
        INSERT_SUITE,
        {
            "id": suite_id,
            "workspace_id": workspace_id,
            "prompt_id": prompt_id,
            "name": name,
            "suite_version": suite_version,
            "output_modality": output_modality.value,
            "case_count": len(cases),
            "created_by": actor_id,
            "now": now,
        },
    )

    for ordinal, draft in enumerate(cases, start=1):
        compiled = compile_assertions(draft.assertions, output_modality, ordinal)
        await db.execute(
            INSERT_CASE,
            {
                "id": _new_id(CASE_ID_PREFIX),
                "workspace_id": workspace_id,
                "suite_id": suite_id,
                "ordinal": ordinal,
                "name": draft.name,
                "input_messages": json.dumps(list(draft.input_messages)),
                "input_variables": json.dumps(dict(draft.input_variables)),
                "assertions": json.dumps([spec.as_json() for spec in compiled]),
                "now": now,
            },
        )

    await events.eval_suite_updated(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        prompt_id=prompt_id,
        suite_id=suite_id,
        occurred_at=now,
    )

    log.info(
        "evaluation.suite_written",
        workspace_id=workspace_id,
        actor_id=actor_id,
        prompt_id=prompt_id,
        suite_id=suite_id,
        suite_name=name,
        suite_version=suite_version,
    )

    return SuiteRow(
        id=suite_id,
        workspace_id=workspace_id,
        prompt_id=prompt_id,
        name=name,
        suite_version=suite_version,
        output_modality=output_modality,
        case_count=len(cases),
        created_by=actor_id,
        created_at=now,
    )


async def _write_dataset_cases(
    db: AsyncSession,
    *,
    workspace_id: str,
    dataset_id: str,
    cases: Sequence[CaseDraft],
    output_modality: OutputModality,
    now: datetime,
) -> None:
    for ordinal, draft in enumerate(cases, start=1):
        # The same gate a suite goes through. Catching a bad regex here means a
        # dataset that cannot be materialised never enters the library, rather
        # than failing later on somebody else's prompt.
        compiled = compile_assertions(draft.assertions, output_modality, ordinal)
        await db.execute(
            INSERT_DATASET_CASE,
            {
                "id": _new_id(DATASET_CASE_ID_PREFIX),
                "workspace_id": workspace_id,
                "dataset_id": dataset_id,
                "ordinal": ordinal,
                "name": draft.name,
                "input_messages": json.dumps(list(draft.input_messages)),
                "input_variables": json.dumps(dict(draft.input_variables)),
                "assertions": json.dumps([spec.as_json() for spec in compiled]),
                "now": now,
            },
        )


async def create_dataset(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    folder: str,
    name: str,
    description: str,
    kind: DatasetKind,
    tags: Sequence[str],
    output_modality: OutputModality,
    cases: Sequence[CaseDraft],
    now: datetime,
) -> str:
    """Write a new library dataset and return its id.

    Nothing is attached and no suite is written. A dataset entering the library
    is a library event; choosing it for a prompt is a separate act with a
    separate permission consequence.
    """
    if len(cases) > MAX_CASES_PER_SUITE:
        raise AssertionPatternInvalid(
            len(cases), f"a dataset holds at most {MAX_CASES_PER_SUITE} cases"
        )

    dataset_id = _new_id(DATASET_ID_PREFIX)

    try:
        async with db.begin_nested():
            await db.execute(
                INSERT_DATASET,
                {
                    "id": dataset_id,
                    "workspace_id": workspace_id,
                    "folder": folder,
                    "name": name,
                    "description": description,
                    "kind": kind.value,
                    "tags": json.dumps(list(tags)),
                    "output_modality": output_modality.value,
                    "case_count": len(cases),
                    "created_by": actor_id,
                    "now": now,
                },
            )
    except IntegrityError as error:
        if _constraint_name(error) != "uq_dataset_name":
            raise
        raise DatasetNameTaken(name) from error

    await _write_dataset_cases(
        db,
        workspace_id=workspace_id,
        dataset_id=dataset_id,
        cases=cases,
        output_modality=output_modality,
        now=now,
    )

    log.info(
        "evaluation.dataset_created",
        workspace_id=workspace_id,
        actor_id=actor_id,
        dataset_id=dataset_id,
        folder=folder,
        case_count=len(cases),
    )

    return dataset_id


async def update_dataset(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    dataset_id: str,
    folder: str,
    name: str,
    description: str,
    kind: DatasetKind,
    tags: Sequence[str],
    output_modality: OutputModality,
    cases: Sequence[CaseDraft],
    now: datetime,
) -> None:
    """Replace a dataset's content in place.

    **An edit here cannot disturb a past run**, which is the whole reason a
    dataset and a suite are different objects. Every suite this dataset was ever
    materialised into is a copy taken at that moment and is immutable; what
    changes is the fingerprint, so the *next* run writes a new suite version and
    the tree marks every prompt that attached it as changed since it last ran.
    """
    if len(cases) > MAX_CASES_PER_SUITE:
        raise AssertionPatternInvalid(
            len(cases), f"a dataset holds at most {MAX_CASES_PER_SUITE} cases"
        )

    try:
        async with db.begin_nested():
            await db.execute(
                UPDATE_DATASET,
                {
                    "id": dataset_id,
                    "folder": folder,
                    "name": name,
                    "description": description,
                    "kind": kind.value,
                    "tags": json.dumps(list(tags)),
                    "output_modality": output_modality.value,
                    "case_count": len(cases),
                    "now": now,
                },
            )
    except IntegrityError as error:
        if _constraint_name(error) != "uq_dataset_name":
            raise
        raise DatasetNameTaken(name) from error

    await db.execute(DELETE_DATASET_CASES, {"dataset_id": dataset_id})
    await _write_dataset_cases(
        db,
        workspace_id=workspace_id,
        dataset_id=dataset_id,
        cases=cases,
        output_modality=output_modality,
        now=now,
    )

    log.info(
        "evaluation.dataset_updated",
        workspace_id=workspace_id,
        actor_id=actor_id,
        dataset_id=dataset_id,
        case_count=len(cases),
    )


async def delete_dataset(
    db: AsyncSession, *, workspace_id: str, actor_id: str, dataset_id: str
) -> int:
    """Remove a dataset, its cases, and every tick pointing at it.

    Returns how many attachments went with it, so the answer can say so rather
    than quietly changing what other prompts will be measured with.

    **The attachments go deliberately, not by cascade.** ``dataset_id`` is a
    value with no foreign key, because it sometimes names a file in the image. A
    retired *builtin* version keeps its attachments — the id once resolved and
    the row records that — but a deleted workspace dataset will never resolve
    again, so what would be left is a permanently broken tick on every prompt
    that chose it. The suites and runs it already produced are untouched: those
    are the history, and this is not.
    """
    removed = await db.execute(DELETE_ATTACHMENTS_FOR_DATASET, {"dataset_id": dataset_id})
    # `dataset_case` goes with the parent through `fk_dataset_case_dataset_id`.
    await db.execute(DELETE_DATASET, {"id": dataset_id})

    log.info(
        "evaluation.dataset_deleted",
        workspace_id=workspace_id,
        actor_id=actor_id,
        dataset_id=dataset_id,
        detached=removed.rowcount,
    )

    return int(removed.rowcount or 0)


async def attach_dataset(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    dataset: DatasetSpec,
    now: datetime,
) -> None:
    """Record that this prompt has chosen this dataset. Writes no suite.

    **Nothing in ``eval_suite`` happens here**, which is the whole point of the
    attachment table: ticking a set in the eval workspace costs one row and no
    provider call, and it is reversible by :func:`detach_dataset`. The suite —
    immutable, versioned, the thing a run actually reads — is written by
    :func:`materialise_attachment` the first time somebody asks to measure
    something.

    The savepoint is what lets a suite-name collision come back as a refusal
    instead of poisoning the caller's transaction. ``uq_dataset_attachment_
    suite_name`` is the authority on that collision, not a pre-flight SELECT,
    because two ticks racing would both pass a pre-flight check.
    """
    try:
        async with db.begin_nested():
            await db.execute(
                INSERT_ATTACHMENT,
                {
                    "workspace_id": workspace_id,
                    "prompt_id": prompt_id,
                    "dataset_id": dataset.id,
                    "suite_name": dataset.name,
                    "attached_by": actor_id,
                    "now": now,
                },
            )
    except IntegrityError as error:
        # Only the suite-name collision is a refusal somebody can act on. A
        # length or shape CHECK failing here means the *catalogue* is wrong, and
        # reporting that as "another dataset already uses this name" would send
        # the reader looking for a dataset that does not exist.
        if _constraint_name(error) != "uq_dataset_attachment_suite_name":
            raise
        raise SuiteNameTaken(prompt_id, dataset.name) from error

    log.info(
        "evaluation.dataset_attached",
        workspace_id=workspace_id,
        actor_id=actor_id,
        prompt_id=prompt_id,
        dataset_id=dataset.id,
    )


async def detach_dataset(
    db: AsyncSession, *, workspace_id: str, actor_id: str, prompt_id: str, dataset_id: str
) -> bool:
    """Forget a choice. Returns whether a row was actually removed.

    **A delete here loses no history.** Every suite version this attachment
    materialised stays in ``eval_suite``, and every run still names the exact
    ``suite_id`` it measured with — what goes away is a future intention. That
    is why ``prope_app`` holds DELETE on this table and on no history table.
    """
    result = await db.execute(
        DELETE_ATTACHMENT, {"prompt_id": prompt_id, "dataset_id": dataset_id}
    )
    removed = bool(result.rowcount)

    if removed:
        log.info(
            "evaluation.dataset_detached",
            workspace_id=workspace_id,
            actor_id=actor_id,
            prompt_id=prompt_id,
            dataset_id=dataset_id,
        )

    return removed


async def materialise_attachment(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    attachment: AttachmentRow,
    dataset: DatasetSpec,
    now: datetime,
) -> str:
    """Turn a choice into the immutable suite a run can read. Returns its id.

    **Reuse is the common path and it is what keeps the suite history
    readable.** Running the same unchanged dataset ten times must not leave ten
    versions behind — the version number would then measure how often somebody
    pressed the button rather than how often the yardstick changed, and A-004's
    "the same suite version measured both revisions" would be true only by
    accident. The fingerprint covers the cases and their assertions, so a
    renamed dataset reuses and an edited one restates.
    """
    if not attachment.is_stale(dataset.fingerprint):
        assert attachment.materialised_suite_id is not None  # noqa: S101 - is_stale proved it
        return attachment.materialised_suite_id

    suite = await write_suite_version(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        prompt_id=prompt_id,
        name=attachment.suite_name,
        output_modality=dataset.output_modality,
        cases=dataset.cases,
        now=now,
    )

    await db.execute(
        STAMP_MATERIALISATION,
        {
            "prompt_id": prompt_id,
            "dataset_id": attachment.dataset_id,
            "suite_id": suite.id,
            "fingerprint": dataset.fingerprint,
        },
    )

    log.info(
        "evaluation.dataset_materialised",
        workspace_id=workspace_id,
        actor_id=actor_id,
        prompt_id=prompt_id,
        dataset_id=attachment.dataset_id,
        suite_id=suite.id,
        suite_version=suite.suite_version,
    )

    return suite.id


async def create_runs(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_id: str,
    prompt_id: str,
    version_id: str,
    suite_ids: Sequence[str],
    role: RunRole,
    now: datetime,
) -> tuple[str, ...]:
    created: list[str] = []

    for suite_id in suite_ids:
        run_id = _new_id(RUN_ID_PREFIX)
        await db.execute(
            INSERT_RUN,
            {
                "id": run_id,
                "workspace_id": workspace_id,
                "prompt_id": prompt_id,
                "version_id": version_id,
                "suite_id": suite_id,
                "role": role.value,
                "started_by": actor_id,
            },
        )
        await events.eval_run_started(
            db,
            workspace_id=workspace_id,
            actor_id=actor_id,
            prompt_id=prompt_id,
            run_id=run_id,
            occurred_at=now,
        )
        created.append(run_id)

    log.info(
        "evaluation.runs_created",
        workspace_id=workspace_id,
        actor_id=actor_id,
        prompt_id=prompt_id,
        version_id=version_id,
        role=role.value,
    )

    return tuple(created)


async def record_case_result(
    db: AsyncSession,
    *,
    workspace_id: str,
    run_id: str,
    case_id: str,
    outcome: CaseOutcome,
    assertion_results: Sequence[AssertionOutcome],
    output_content: str | None,
    latency_ms: int | None,
    input_tokens: int | None,
    output_tokens: int | None,
    error_code: str | None,
    attempt_count: int,
    now: datetime,
) -> str:
    result_id = _new_id(CASE_RESULT_ID_PREFIX)
    await db.execute(
        INSERT_CASE_RESULT,
        {
            "id": result_id,
            "workspace_id": workspace_id,
            "run_id": run_id,
            "case_id": case_id,
            "outcome": outcome.value,
            "assertion_results": json.dumps([entry.as_json() for entry in assertion_results]),
            "output_content": output_content,
            "latency_ms": latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "error_code": error_code,
            "attempt_count": attempt_count,
            "now": now,
        },
    )
    return result_id


async def mark_refused(
    db: AsyncSession, *, run_id: str, reason: RefusalReason, now: datetime
) -> None:
    await db.execute(REFUSE_RUN, {"run_id": run_id, "reason": reason.value, "now": now})


async def mark_completed(
    db: AsyncSession,
    *,
    run_id: str,
    pass_count: int,
    fail_count: int,
    error_count: int,
    input_tokens: int | None,
    output_tokens: int | None,
    cost_amount: Decimal | None,
    cost_currency: str | None,
    priced_at: datetime | None,
    now: datetime,
) -> None:
    await db.execute(
        COMPLETE_RUN,
        {
            "run_id": run_id,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "error_count": error_count,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_amount": cost_amount,
            "cost_currency": cost_currency,
            "priced_at": priced_at,
            "now": now,
        },
    )


async def mark_interrupted(db: AsyncSession, *, run_id: str, now: datetime) -> bool:
    result = await db.execute(INTERRUPT_RUN, {"run_id": run_id, "now": now})
    return bool(result.rowcount)


async def stamp_case_count(db: AsyncSession, *, suite_id: str, case_count: int) -> None:
    await db.execute(STAMP_CASE_COUNT, {"suite_id": suite_id, "case_count": case_count})


async def stamp_price(
    db: AsyncSession,
    *,
    run_id: str,
    cost_amount: Decimal | None,
    cost_currency: str | None,
    priced_at: datetime | None,
) -> None:
    await db.execute(
        STAMP_PRICE,
        {
            "run_id": run_id,
            "cost_amount": cost_amount,
            "cost_currency": cost_currency,
            "priced_at": priced_at,
        },
    )
