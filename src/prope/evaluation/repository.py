from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from prope.evaluation.assertions import parse_assertions
from prope.evaluation.domain import (
    RUN_HISTORY_LIMIT,
    AssertionOutcome,
    AssertionType,
    AttachmentRow,
    CaseDraft,
    CaseOutcome,
    CaseResultRow,
    CaseRow,
    DatasetKind,
    DatasetSpec,
    OutputModality,
    RefusalReason,
    RunListing,
    RunRole,
    RunRow,
    RunStatus,
    SuiteRow,
    fingerprint_cases,
)

__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "count_attachments_for_dataset",
    "count_queued_runs",
    "find_baseline_run",
    "latest_completed_run",
    "list_attachments",
    "list_workspace_datasets",
    "load_workspace_dataset",
    "list_case_results",
    "list_cases",
    "list_current_suites",
    "list_runs_for_prompt",
    "list_runs_for_version",
    "list_stalled_runs",
    "list_suite_versions",
    "load_attachment",
    "load_current_suite",
    "load_run",
    "run_status",
    "load_suite",
    "next_suite_version",
]

DEFAULT_LIMIT = 50

MAX_LIMIT = 200

LOAD_SUITE = text(
    """
    SELECT id, workspace_id, prompt_id, name, suite_version, output_modality,
           case_count, created_by, created_at
    FROM   evaluation.eval_suite
    WHERE  id = :suite_id
    """
)

LOAD_CURRENT_SUITE = text(
    """
    SELECT id, workspace_id, prompt_id, name, suite_version, output_modality,
           case_count, created_by, created_at
    FROM   evaluation.eval_suite
    WHERE  prompt_id = :prompt_id AND name = :name
    ORDER  BY suite_version DESC
    LIMIT  1
    """
)

LIST_CURRENT_SUITES = text(
    """
    SELECT DISTINCT ON (name)
           id, workspace_id, prompt_id, name, suite_version, output_modality,
           case_count, created_by, created_at
    FROM   evaluation.eval_suite
    WHERE  prompt_id = :prompt_id
    ORDER  BY name, suite_version DESC
    """
)

LIST_SUITE_VERSIONS = text(
    """
    SELECT id, workspace_id, prompt_id, name, suite_version, output_modality,
           case_count, created_by, created_at
    FROM   evaluation.eval_suite
    WHERE  prompt_id = :prompt_id AND name = :name
    ORDER  BY suite_version DESC
    LIMIT  :limit
    """
)

NEXT_SUITE_VERSION = text(
    """
    SELECT coalesce(max(suite_version), 0) + 1
    FROM   evaluation.eval_suite
    WHERE  prompt_id = :prompt_id AND name = :name
    """
)

LIST_CASES = text(
    """
    SELECT id, workspace_id, suite_id, ordinal, name, input_messages,
           input_variables, assertions, created_at
    FROM   evaluation.eval_case
    WHERE  suite_id = :suite_id
    ORDER  BY ordinal
    """
)

LOAD_RUN = text(
    """
    SELECT id, workspace_id, prompt_id, version_id, suite_id, role, status,
           refused_reason, started_at, finished_at, pass_count, fail_count,
           error_count, input_tokens, output_tokens, cost_amount, cost_currency,
           priced_at, started_by
    FROM   evaluation.eval_run
    WHERE  id = :run_id
    """
)

#: One column of LOAD_RUN, read per case while a run executes: the executor
#: checks between dispatches whether a cancel (or a reap) has ended the run, so
#: every skipped case is a provider call that was never spent.
RUN_STATUS = text(
    """
    SELECT status
    FROM   evaluation.eval_run
    WHERE  id = :run_id
    """
)

#: One prompt's run history, with the two labels a reader needs to tell the runs
#: apart.
#:
#: **The joins are left joins and that is not defensiveness.** A suite is
#: versioned by row: editing one writes a new `eval_suite` with the next
#: `suite_version`, and the old row stays because the runs against it must keep
#: meaning something. But a run whose suite row was never written — or was written
#: in a workspace this reader cannot see, which under RLS is the same thing —
#: still happened and still has counts, and dropping it would make the history
#: quietly shorter than the truth. So the run is the driving table and the labels
#: are allowed to be null.
#:
#: `dataset_attachment` is joined on `(prompt_id, materialised_suite_id)` rather
#: than through `suite_name`: a person can rename a dataset, and the attachment
#: is the only row that records *this suite was built from that dataset*. A suite
#: authored by hand has no attachment and therefore no dataset name, which is the
#: honest answer rather than a missing one.
#:
#: `role = 'candidate'` is deliberately **not** filtered here, unlike
#: `LIST_RUNS_FOR_VERSION`. That query feeds a comparison, which is about one
#: side; this one feeds a history, and a baseline run is part of the history.
LIST_RUNS_FOR_PROMPT = text(
    """
    SELECT r.id, r.workspace_id, r.prompt_id, r.version_id, r.suite_id, r.role,
           r.status, r.refused_reason, r.started_at, r.finished_at, r.pass_count,
           r.fail_count, r.error_count, r.input_tokens, r.output_tokens,
           r.cost_amount, r.cost_currency, r.priced_at, r.started_by,
           s.name          AS suite_name,
           s.suite_version AS suite_version,
           a.dataset_id    AS dataset_id,
           d.name          AS dataset_name
    FROM   evaluation.eval_run r
    LEFT   JOIN evaluation.eval_suite s
           ON  s.id = r.suite_id
    LEFT   JOIN evaluation.dataset_attachment a
           ON  a.prompt_id = r.prompt_id AND a.materialised_suite_id = r.suite_id
    LEFT   JOIN evaluation.dataset d
           ON  d.id = a.dataset_id
    WHERE  r.prompt_id = :prompt_id
      AND  (CAST(:version_id AS text) IS NULL OR r.version_id = CAST(:version_id AS text))
    ORDER  BY r.id DESC
    LIMIT  :limit
    """
)

LIST_RUNS_FOR_VERSION = text(
    """
    SELECT id, workspace_id, prompt_id, version_id, suite_id, role, status,
           refused_reason, started_at, finished_at, pass_count, fail_count,
           error_count, input_tokens, output_tokens, cost_amount, cost_currency,
           priced_at, started_by
    FROM   evaluation.eval_run
    WHERE  prompt_id = :prompt_id AND version_id = :version_id AND role = 'candidate'
    ORDER  BY id DESC
    """
)

LATEST_COMPLETED_RUN = text(
    """
    SELECT id, workspace_id, prompt_id, version_id, suite_id, role, status,
           refused_reason, started_at, finished_at, pass_count, fail_count,
           error_count, input_tokens, output_tokens, cost_amount, cost_currency,
           priced_at, started_by
    FROM   evaluation.eval_run
    WHERE  version_id = :version_id AND suite_id = :suite_id AND status = 'completed'
    ORDER  BY id DESC
    LIMIT  1
    """
)

LIST_CASE_RESULTS = text(
    """
    SELECT id, workspace_id, run_id, case_id, outcome, assertion_results,
           output_content, latency_ms, input_tokens, output_tokens, error_code,
           attempt_count, created_at
    FROM   evaluation.case_result
    WHERE  run_id = :run_id
    ORDER  BY created_at, id
    """
)

COUNT_QUEUED_RUNS = text("SELECT count(*) FROM evaluation.eval_run WHERE status = 'queued'")

LIST_STALLED_RUNS = text(
    """
    SELECT r.id
    FROM   evaluation.eval_run AS r
    WHERE  r.status = 'running'
      AND  coalesce(
               (SELECT max(c.created_at) FROM evaluation.case_result AS c WHERE c.run_id = r.id),
               r.started_at
           ) < :cutoff
    ORDER  BY r.id
    """
)


#: The workspace's own datasets. Folder then name, which is the order the tree
#: renders them in — sorting here rather than in the client means the Chung
#: group's shipped sets are the only thing the page has to merge.
LIST_DATASETS = text(
    """
    SELECT id, workspace_id, folder, name, description, kind, tags, output_modality,
           case_count, created_by, created_at, updated_at
    FROM   evaluation.dataset
    ORDER  BY folder, name
    """
)

LOAD_DATASET = text(
    """
    SELECT id, workspace_id, folder, name, description, kind, tags, output_modality,
           case_count, created_by, created_at, updated_at
    FROM   evaluation.dataset
    WHERE  id = :dataset_id
    """
)

LIST_DATASET_CASES = text(
    """
    SELECT id, workspace_id, dataset_id, ordinal, name, input_messages,
           input_variables, assertions, created_at
    FROM   evaluation.dataset_case
    WHERE  dataset_id = :dataset_id
    ORDER  BY ordinal
    """
)

#: Every case of every dataset in one round trip. The tree needs a fingerprint
#: per dataset, a fingerprint is over the cases, and N+1 queries to render a
#: sidebar is the shape that is fine with five datasets and awful with fifty.
LIST_ALL_DATASET_CASES = text(
    """
    SELECT id, workspace_id, dataset_id, ordinal, name, input_messages,
           input_variables, assertions, created_at
    FROM   evaluation.dataset_case
    ORDER  BY dataset_id, ordinal
    """
)

#: Which prompts have chosen this dataset. Read before a delete so the answer
#: can say how many ticks it is about to remove.
COUNT_ATTACHMENTS_FOR_DATASET = text(
    "SELECT count(*) FROM evaluation.dataset_attachment WHERE dataset_id = :dataset_id"
)

#: Ordered by ``attached_at`` rather than by name, so the tick order is the
#: order the eval workspace lists them in and a set somebody just added appears
#: where they are looking. ``dataset_id`` breaks the tie, because two ticks
#: inside one request share a timestamp.
LIST_ATTACHMENTS = text(
    """
    SELECT workspace_id, prompt_id, dataset_id, suite_name,
           materialised_suite_id, materialised_fingerprint, attached_by, attached_at
    FROM   evaluation.dataset_attachment
    WHERE  prompt_id = :prompt_id
    ORDER  BY attached_at, dataset_id
    """
)

LOAD_ATTACHMENT = text(
    """
    SELECT workspace_id, prompt_id, dataset_id, suite_name,
           materialised_suite_id, materialised_fingerprint, attached_by, attached_at
    FROM   evaluation.dataset_attachment
    WHERE  prompt_id = :prompt_id AND dataset_id = :dataset_id
    """
)


def _dataset_case_draft(row: Any) -> CaseDraft:
    return CaseDraft(
        name=row.name,
        input_messages=tuple(row.input_messages),
        input_variables=dict(row.input_variables),
        assertions=parse_assertions(row.assertions),
    )


def _dataset(row: Any, cases: tuple[CaseDraft, ...]) -> DatasetSpec:
    """A workspace row assembled into the same shape a shipped set has.

    One type for both halves of the library is what lets the tree, the
    attachment and materialisation stay ignorant of where a dataset came from.
    ``read_only=False`` and a real ``folder`` are the only two fields that ever
    differ from a builtin's.
    """
    return DatasetSpec(
        id=row.id,
        name=row.name,
        description=row.description,
        kind=DatasetKind(row.kind),
        tags=tuple(str(tag) for tag in (row.tags or [])),
        output_modality=OutputModality(row.output_modality),
        cases=cases,
        fingerprint=fingerprint_cases(cases),
        applicability=None,
        folder=row.folder,
        read_only=False,
    )


def _attachment(row: Any) -> AttachmentRow:
    return AttachmentRow(
        workspace_id=row.workspace_id,
        prompt_id=row.prompt_id,
        dataset_id=row.dataset_id,
        suite_name=row.suite_name,
        materialised_suite_id=row.materialised_suite_id,
        materialised_fingerprint=row.materialised_fingerprint,
        attached_by=row.attached_by,
        attached_at=row.attached_at,
    )


def _suite(row: Any) -> SuiteRow:
    return SuiteRow(
        id=row.id,
        workspace_id=row.workspace_id,
        prompt_id=row.prompt_id,
        name=row.name,
        suite_version=row.suite_version,
        output_modality=OutputModality(row.output_modality),
        case_count=row.case_count,
        created_by=row.created_by,
        created_at=row.created_at,
    )


def _case(row: Any) -> CaseRow:
    return CaseRow(
        id=row.id,
        workspace_id=row.workspace_id,
        suite_id=row.suite_id,
        ordinal=row.ordinal,
        name=row.name,
        input_messages=tuple(row.input_messages),
        input_variables=dict(row.input_variables),
        assertions=parse_assertions(row.assertions),
        created_at=row.created_at,
    )


def _run_listing(row: Any) -> RunListing:
    return RunListing(
        run=_run(row),
        suite_name=row.suite_name,
        suite_version=row.suite_version,
        dataset_id=row.dataset_id,
        dataset_name=row.dataset_name,
    )


def _run(row: Any) -> RunRow:
    return RunRow(
        id=row.id,
        workspace_id=row.workspace_id,
        prompt_id=row.prompt_id,
        version_id=row.version_id,
        suite_id=row.suite_id,
        role=RunRole(row.role),
        status=RunStatus(row.status),
        refused_reason=None if row.refused_reason is None else RefusalReason(row.refused_reason),
        started_at=row.started_at,
        finished_at=row.finished_at,
        pass_count=row.pass_count,
        fail_count=row.fail_count,
        error_count=row.error_count,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        cost_amount=row.cost_amount,
        cost_currency=row.cost_currency,
        priced_at=row.priced_at,
        started_by=row.started_by,
    )


def _case_result(row: Any) -> CaseResultRow:
    return CaseResultRow(
        id=row.id,
        workspace_id=row.workspace_id,
        run_id=row.run_id,
        case_id=row.case_id,
        outcome=CaseOutcome(row.outcome),
        assertion_results=tuple(
            AssertionOutcome(
                type=AssertionType(entry["type"]),
                passed=bool(entry["passed"]),
                detail=entry.get("detail"),
            )
            for entry in row.assertion_results
        ),
        output_content=row.output_content,
        latency_ms=row.latency_ms,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        error_code=row.error_code,
        attempt_count=row.attempt_count,
        created_at=row.created_at,
    )


async def list_workspace_datasets(db: AsyncSession) -> tuple[DatasetSpec, ...]:
    """The workspace's own datasets, cases included.

    Two queries rather than one per dataset: the tree needs a fingerprint for
    every row and a fingerprint is over the cases, so the alternative is N+1
    round trips to render a sidebar.
    """
    rows = (await db.execute(LIST_DATASETS)).all()
    if not rows:
        return ()

    grouped: dict[str, list[CaseDraft]] = {}
    for case_row in (await db.execute(LIST_ALL_DATASET_CASES)).all():
        grouped.setdefault(case_row.dataset_id, []).append(_dataset_case_draft(case_row))

    return tuple(_dataset(row, tuple(grouped.get(row.id, ()))) for row in rows)


async def load_workspace_dataset(db: AsyncSession, dataset_id: str) -> DatasetSpec | None:
    row = (await db.execute(LOAD_DATASET, {"dataset_id": dataset_id})).first()
    if row is None:
        return None

    case_rows = (await db.execute(LIST_DATASET_CASES, {"dataset_id": dataset_id})).all()
    return _dataset(row, tuple(_dataset_case_draft(case_row) for case_row in case_rows))


async def count_attachments_for_dataset(db: AsyncSession, dataset_id: str) -> int:
    return int(
        await db.scalar(COUNT_ATTACHMENTS_FOR_DATASET, {"dataset_id": dataset_id}) or 0
    )


async def list_attachments(db: AsyncSession, prompt_id: str) -> tuple[AttachmentRow, ...]:
    rows = (await db.execute(LIST_ATTACHMENTS, {"prompt_id": prompt_id})).all()
    return tuple(_attachment(row) for row in rows)


async def load_attachment(
    db: AsyncSession, prompt_id: str, dataset_id: str
) -> AttachmentRow | None:
    row = (
        await db.execute(LOAD_ATTACHMENT, {"prompt_id": prompt_id, "dataset_id": dataset_id})
    ).first()
    return None if row is None else _attachment(row)


async def load_suite(db: AsyncSession, suite_id: str) -> SuiteRow | None:
    row = (await db.execute(LOAD_SUITE, {"suite_id": suite_id})).first()
    return None if row is None else _suite(row)


async def load_current_suite(db: AsyncSession, prompt_id: str, name: str) -> SuiteRow | None:
    row = (await db.execute(LOAD_CURRENT_SUITE, {"prompt_id": prompt_id, "name": name})).first()
    return None if row is None else _suite(row)


async def list_current_suites(db: AsyncSession, prompt_id: str) -> tuple[SuiteRow, ...]:
    rows = (await db.execute(LIST_CURRENT_SUITES, {"prompt_id": prompt_id})).all()
    return tuple(_suite(row) for row in rows)


async def list_suite_versions(
    db: AsyncSession, prompt_id: str, name: str, *, limit: int = DEFAULT_LIMIT
) -> tuple[SuiteRow, ...]:
    rows = (
        await db.execute(
            LIST_SUITE_VERSIONS, {"prompt_id": prompt_id, "name": name, "limit": limit}
        )
    ).all()
    return tuple(_suite(row) for row in rows)


async def next_suite_version(db: AsyncSession, prompt_id: str, name: str) -> int:
    return int(await db.scalar(NEXT_SUITE_VERSION, {"prompt_id": prompt_id, "name": name}) or 1)


async def list_cases(db: AsyncSession, suite_id: str) -> tuple[CaseRow, ...]:
    rows = (await db.execute(LIST_CASES, {"suite_id": suite_id})).all()
    return tuple(_case(row) for row in rows)


async def load_run(db: AsyncSession, run_id: str) -> RunRow | None:
    row = (await db.execute(LOAD_RUN, {"run_id": run_id})).first()
    return None if row is None else _run(row)


async def run_status(db: AsyncSession, run_id: str) -> RunStatus | None:
    row = (await db.execute(RUN_STATUS, {"run_id": run_id})).first()
    if row is None:
        return None
    try:
        return RunStatus(row[0])
    except ValueError:
        return None


async def list_runs_for_prompt(
    db: AsyncSession,
    prompt_id: str,
    *,
    version_id: str | None = None,
    limit: int = RUN_HISTORY_LIMIT,
) -> tuple[RunListing, ...]:
    """One prompt's runs, newest first, with suite and dataset labels attached.

    `version_id` narrows to one revision; omitted, the caller gets every
    revision's runs, which is what a trend across revisions is made of.

    Bounded rather than paged. A prompt accumulates runs slowly — a suite is run
    on purpose, by a person, and each one spends provider money — so a ceiling
    that covers a year of ordinary use is simpler than a cursor the screen would
    never reach the end of. `RUN_HISTORY_LIMIT` is that ceiling and the caller may
    ask for less.
    """
    if not 1 <= limit <= RUN_HISTORY_LIMIT:
        raise ValueError(f"limit={limit} is outside 1..{RUN_HISTORY_LIMIT}")

    rows = (
        await db.execute(
            LIST_RUNS_FOR_PROMPT,
            {"prompt_id": prompt_id, "version_id": version_id, "limit": limit},
        )
    ).all()
    return tuple(_run_listing(row) for row in rows)


async def list_runs_for_version(
    db: AsyncSession, prompt_id: str, version_id: str
) -> tuple[RunRow, ...]:
    rows = (
        await db.execute(
            LIST_RUNS_FOR_VERSION, {"prompt_id": prompt_id, "version_id": version_id}
        )
    ).all()
    return tuple(_run(row) for row in rows)


async def latest_completed_run(db: AsyncSession, version_id: str, suite_id: str) -> RunRow | None:
    row = (
        await db.execute(LATEST_COMPLETED_RUN, {"version_id": version_id, "suite_id": suite_id})
    ).first()
    return None if row is None else _run(row)


async def find_baseline_run(
    db: AsyncSession, released_version_id: str | None, suite_id: str
) -> RunRow | None:
    if released_version_id is None:
        return None
    return await latest_completed_run(db, released_version_id, suite_id)


async def list_case_results(db: AsyncSession, run_id: str) -> tuple[CaseResultRow, ...]:
    rows = (await db.execute(LIST_CASE_RESULTS, {"run_id": run_id})).all()
    return tuple(_case_result(row) for row in rows)


async def count_queued_runs(db: AsyncSession) -> int:
    return int(await db.scalar(COUNT_QUEUED_RUNS) or 0)


async def list_stalled_runs(db: AsyncSession, cutoff: datetime) -> tuple[str, ...]:
    return tuple((await db.execute(LIST_STALLED_RUNS, {"cutoff": cutoff})).scalars().all())
