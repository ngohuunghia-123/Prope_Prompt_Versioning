from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.actions import Action
from prope.access_control.seams import (
    AccessLevel,
    Actor,
    ActorType,
    Subject,
    SubjectType,
    may,
)
from prope.agent_run import repository as agent_run_repository
from prope.agent_run.domain import PlanBasis, RunKind
from prope.db.session import workspace_transaction
from prope.dependencies import get_sessionmaker
from prope.errors import ErrorCode
from prope.evaluation import catalogue, commands, repository, summary
from prope.evaluation.domain import (
    RUN_HISTORY_LIMIT,
    AssertionPatternInvalid,
    AssertionSpec,
    AttachmentRow,
    CaseDraft,
    CaseOutcome,
    CaseResultRow,
    CaseRow,
    DatasetKind,
    DatasetNameTaken,
    DatasetSpec,
    OutputModality,
    RunListing,
    RunRole,
    RunRow,
    SuiteNameTaken,
    SuiteRow,
)
from prope.evaluation.generation import DrafterUnavailableError, draft_cases
from prope.evaluation.observability import baseline_reused_total
from prope.evaluation.schemas import (
    AssertionRead,
    AttachmentRead,
    AttachmentWrite,
    CaseComparisonRead,
    CaseResultRead,
    ComparisonBlockRead,
    CostDeltaRead,
    DatasetCaseRead,
    DatasetDeleted,
    DatasetDetailRead,
    DatasetDraftRequest,
    DatasetRead,
    DatasetWrite,
    EvalCaseRead,
    EvalCaseTraceRead,
    EvalCaseWrite,
    EvalRunAccepted,
    EvalRunHandle,
    EvalRunRead,
    EvalRunStart,
    EvalRunSummaryRead,
    EvalSuiteCreate,
    EvalSuiteRead,
    EvalSuiteUpdate,
    EvalTraceSpanRead,
)
from prope.prompt_registry.seams import (
    PromptRow,
    get_prompt,
    get_released_revision,
    get_revision,
    list_revision_chain,
)
from prope.session_auth import (
    ManagementAction,
    ManagementRefusal,
    Session,
    declares_action,
    require_session,
)

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _not_found() -> ManagementRefusal:
    return ManagementRefusal(
        status_code=404, code=ErrorCode.NOT_FOUND, message="no such prompt"
    )


def _forbidden(
    action: Action, subject_type: SubjectType = SubjectType.PROMPT
) -> ManagementRefusal:
    return ManagementRefusal(
        status_code=403,
        code=ErrorCode.PERMISSION_DENIED,
        message=f"this action requires the {action.value} permission",
        details={"permission": action.value, "subject_type": subject_type.value},
    )


def _actor(session: Session) -> Actor:
    return Actor(type=ActorType.USER, id=session.user_id, workspace_id=session.workspace_id)


def _subject(row: PromptRow) -> Subject:
    return Subject(
        type=SubjectType.PROMPT,
        id=row.id,
        workspace_id=row.workspace_id,
        owner_id=row.owner_id,
        access_level=AccessLevel(row.access_level),
        # ADR-0061. Read off the same row the other two come from, and required
        # for the same reason ADR-0020 requires them: a namespace grant is the
        # fifth source `may()` unions, and a subject that omitted its namespace
        # would silently skip it — which reads as "the grant does not work"
        # rather than as a missing field.
        namespace=row.namespace,
    )


async def _visible_prompt(
    db: AsyncSession, session: Session, action: Action, prompt_id: str
) -> PromptRow:
    row = await get_prompt(db, prompt_id)
    if row is None:
        raise _not_found()

    actor = _actor(session)
    subject = _subject(row)

    if await may(db, actor, action, subject):
        return row

    if await may(db, actor, Action.PROMPT_READ, subject):
        raise _forbidden(action)

    raise _not_found()


def _suite_read(suite: SuiteRow, cases: tuple[CaseRow, ...] | None = None) -> EvalSuiteRead:
    return EvalSuiteRead(
        suite_id=suite.id,
        prompt_id=suite.prompt_id,
        name=suite.name,
        suite_version=suite.suite_version,
        output_modality=suite.output_modality,
        case_count=suite.case_count,
        created_by=suite.created_by,
        created_at=suite.created_at,
        cases=None
        if cases is None
        else [
            EvalCaseRead(
                case_id=case.id,
                ordinal=case.ordinal,
                name=case.name,
                input_messages=list(case.input_messages),
                input_variables=dict(case.input_variables),
                assertions=[
                    AssertionRead(type=spec.type, value=spec.value) for spec in case.assertions
                ],
            )
            for case in cases
        ],
    )


def _run_read(run: RunRow) -> EvalRunRead:
    return EvalRunRead(
        run_id=run.id,
        prompt_id=run.prompt_id,
        version_id=run.version_id,
        suite_id=run.suite_id,
        role=run.role,
        status=run.status,
        refused_reason=run.refused_reason,
        started_at=run.started_at,
        finished_at=run.finished_at,
        pass_count=run.pass_count,
        fail_count=run.fail_count,
        error_count=run.error_count,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        cost_amount=run.cost_amount,
        cost_currency=run.cost_currency,
        priced_at=run.priced_at,
        started_by=run.started_by,
    )


def _run_summary_read(listing: RunListing) -> EvalRunSummaryRead:
    """The run's own fields from the one mapper that owns them, plus the labels.

    ``**_run_read(...).model_dump()`` rather than a second spelled-out copy of
    nineteen fields: there is one definition of how a ``RunRow`` becomes wire
    form, and a field added there appears here without anybody remembering to.
    """
    return EvalRunSummaryRead(
        **_run_read(listing.run).model_dump(),
        suite_name=listing.suite_name,
        suite_version=listing.suite_version,
        dataset_id=listing.dataset_id,
        dataset_name=listing.dataset_name,
    )


def _case_result_read(result: CaseResultRow) -> CaseResultRead:
    return CaseResultRead(
        case_result_id=result.id,
        run_id=result.run_id,
        case_id=result.case_id,
        outcome=result.outcome,
        assertion_results=[entry.as_json() for entry in result.assertion_results],
        output_content=result.output_content,
        latency_ms=result.latency_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        error_code=result.error_code,
        attempt_count=result.attempt_count,
        created_at=result.created_at,
    )


def _case_drafts(cases: list[EvalCaseWrite]) -> tuple[CaseDraft, ...]:
    """Wire cases into domain drafts. Named for the noun, not for the agent —
    ``generation.py`` also produces ``CaseDraft``s and the two must not read as
    the same path."""
    return tuple(
        CaseDraft(
            name=case.name,
            input_messages=tuple(case.input_messages),
            input_variables=dict(case.input_variables),
            assertions=tuple(
                AssertionSpec(type=entry.type, value=entry.value) for entry in case.assertions
            ),
        )
        for case in cases
    )


def _refuse_invalid_assertion(error: AssertionPatternInvalid) -> ManagementRefusal:
    return ManagementRefusal(
        status_code=422,
        code=ErrorCode.VALIDATION_FAILED,
        message="an assertion in this suite cannot be compiled",
        details={"ordinal": error.ordinal, "detail": error.detail},
    )


def _dataset_read(dataset: DatasetSpec) -> DatasetRead:
    return DatasetRead(
        dataset_id=dataset.id,
        name=dataset.name,
        description=dataset.description,
        kind=dataset.kind,
        tags=list(dataset.tags),
        output_modality=dataset.output_modality,
        case_count=dataset.case_count,
        folder=dataset.folder,
        read_only=dataset.read_only,
        applicability=dataset.applicability,
        fingerprint=dataset.fingerprint,
    )


async def _resolve_dataset(db: AsyncSession, dataset_id: str) -> DatasetSpec | None:
    """The library dataset behind an id, whatever kind of id it is.

    Two sources, one type. A ``builtin:`` id resolves to a YAML file in the
    image; a ``dst_`` id resolves to rows under RLS. Everything above this
    function — the tree, the attachment, materialisation — stays ignorant of
    which, and that is the reason the lookup is a function rather than a
    branch repeated at each use site.

    The prefix check comes first so a workspace can never shadow a shipped set
    by minting a row with a colliding id: the ``dst_`` shape CHECK on
    ``dataset`` makes that impossible anyway, and this makes it impossible
    twice.
    """
    if dataset_id.startswith(catalogue.BUILTIN_PREFIX):
        return catalogue.resolve_builtin(dataset_id)
    return await repository.load_workspace_dataset(db, dataset_id)


def _dataset_detail_read(dataset: DatasetSpec) -> DatasetDetailRead:
    return DatasetDetailRead(
        **_dataset_read(dataset).model_dump(),
        cases=[
            DatasetCaseRead(
                ordinal=ordinal,
                name=case.name,
                input_messages=list(case.input_messages),
                input_variables=dict(case.input_variables),
                assertions=[
                    AssertionRead(type=spec.type, value=spec.value) for spec in case.assertions
                ],
            )
            for ordinal, case in enumerate(dataset.cases, start=1)
        ],
    )


async def _may_edit_library(db: AsyncSession, session: Session) -> None:
    """Gate the library on ``suite.edit``, asked about the workspace.

    A dataset belongs to no prompt, so there is no per-subject grant to consult
    and ``SubjectType.WORKSPACE`` resolves on role bindings alone — which is the
    right shape: whoever may author yardsticks in this workspace may author
    library sets in it. Deliberately not a new member of ``Action``; that
    vocabulary is closed and growing it costs a migration, a database CHECK and
    a matrix row, which is a lot to spend on a distinction nobody has asked for.
    """
    allowed = await may(
        db,
        _actor(session),
        Action.SUITE_EDIT,
        Subject(
            type=SubjectType.WORKSPACE,
            id=session.workspace_id,
            workspace_id=session.workspace_id,
        ),
    )
    if not allowed:
        raise _forbidden(Action.SUITE_EDIT, SubjectType.WORKSPACE)


def _refuse_read_only(dataset_id: str) -> ManagementRefusal:
    return ManagementRefusal(
        status_code=409,
        code=ErrorCode.EVAL_DATASET_READ_ONLY,
        message=(
            "this dataset ships with Prope and is the same in every workspace; "
            "copy it into a folder to change it"
        ),
        details={"dataset_id": dataset_id},
    )


def _no_such_dataset(dataset_id: str) -> ManagementRefusal:
    return ManagementRefusal(
        status_code=404,
        code=ErrorCode.NOT_FOUND,
        message="no such dataset",
        details={"dataset_id": dataset_id},
    )


def _refuse_duplicate_name(error: DatasetNameTaken) -> ManagementRefusal:
    return ManagementRefusal(
        status_code=409,
        code=ErrorCode.ALREADY_EXISTS,
        message=(
            "this workspace already has a dataset with that name; names are unique "
            "because a dataset's name becomes the suite name when it is run"
        ),
        details={"name": error.name},
    )


#: What a drafted dataset says about itself in the tree. Deliberately explicit
#: about its provenance: a set nobody has read yet should not look the same as
#: one somebody wrote.
_DRAFTED_DESCRIPTION = (
    "Bản nháp do Prope AI soạn từ nội dung prompt. Hãy đọc và sửa trước khi dùng "
    "làm thước đo."
)


def _drafted_name(prompt_title: str) -> str:
    """A default name for a drafted set, inside the 100-character column."""
    suffix = " — bản nháp AI"
    return f"{prompt_title[: 100 - len(suffix)]}{suffix}"


async def _attachment_read(db: AsyncSession, attachment: AttachmentRow) -> AttachmentRead:
    dataset = await _resolve_dataset(db, attachment.dataset_id)
    return AttachmentRead(
        dataset_id=attachment.dataset_id,
        suite_name=attachment.suite_name,
        suite_id=attachment.materialised_suite_id,
        # An attachment whose dataset no longer resolves is reported stale: the
        # next run cannot reuse a suite it can no longer prove matches anything.
        stale=True if dataset is None else attachment.is_stale(dataset.fingerprint),
        attached_by=attachment.attached_by,
        attached_at=attachment.attached_at,
        dataset=None if dataset is None else _dataset_read(dataset),
    )


async def _run_handles(
    db: AsyncSession,
    session: Session,
    *,
    prompt_id: str,
    version_id: str,
    suites: Sequence[SuiteRow],
    now: datetime,
) -> list[EvalRunHandle]:
    """Candidate runs for these suites, plus any baseline runs still missing.

    Shared by both start endpoints. The only thing that differs between them is
    where the suite list came from — named suites the caller already had, or
    suites just materialised from the prompt's attachments — and that is not a
    difference the baseline rule should have to be written out twice to know
    about.
    """
    released = await get_released_revision(db, prompt_id)
    handles: list[EvalRunHandle] = []

    candidate_ids = await commands.create_runs(
        db,
        workspace_id=session.workspace_id,
        actor_id=session.user_id,
        prompt_id=prompt_id,
        version_id=version_id,
        suite_ids=[suite.id for suite in suites],
        role=RunRole.CANDIDATE,
        now=now,
    )
    for suite, run_id in zip(suites, candidate_ids, strict=True):
        handles.append(
            EvalRunHandle(
                run_id=run_id,
                suite_id=suite.id,
                suite_name=suite.name,
                suite_version=suite.suite_version,
                role=RunRole.CANDIDATE,
            )
        )

    if released is None or released.version_id == version_id:
        return handles

    missing = []
    for suite in suites:
        baseline = await repository.find_baseline_run(db, released.version_id, suite.id)
        if baseline is None:
            missing.append(suite)
            baseline_reused_total.labels(decision="recomputed").inc()
        else:
            baseline_reused_total.labels(decision="reused").inc()

    if missing:
        baseline_ids = await commands.create_runs(
            db,
            workspace_id=session.workspace_id,
            actor_id=session.user_id,
            prompt_id=prompt_id,
            version_id=released.version_id,
            suite_ids=[suite.id for suite in missing],
            role=RunRole.BASELINE,
            now=now,
        )
        for suite, run_id in zip(missing, baseline_ids, strict=True):
            handles.append(
                EvalRunHandle(
                    run_id=run_id,
                    suite_id=suite.id,
                    suite_name=suite.name,
                    suite_version=suite.suite_version,
                    role=RunRole.BASELINE,
                )
            )

    return handles


@router.get(
    "/prompts/{prompt_id}/eval-suites",
    response_model=list[EvalSuiteRead],
    dependencies=[Depends(declares_action(ManagementAction.EVAL_SUITE_LIST))],
)
async def list_eval_suites(
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> list[EvalSuiteRead]:
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _visible_prompt(db, session, Action.SUITE_READ, prompt_id)
        suites = await repository.list_current_suites(db, prompt_id)

    return [_suite_read(suite) for suite in suites]


@router.post(
    "/prompts/{prompt_id}/eval-suites",
    response_model=EvalSuiteRead,
    status_code=201,
    dependencies=[Depends(declares_action(ManagementAction.EVAL_SUITE_CREATE))],
)
async def create_eval_suite(
    payload: EvalSuiteCreate,
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> EvalSuiteRead:
    now = _utc_now()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _visible_prompt(db, session, Action.SUITE_EDIT, prompt_id)

        if await repository.load_current_suite(db, prompt_id, payload.name) is not None:
            raise ManagementRefusal(
                status_code=409,
                code=ErrorCode.ALREADY_EXISTS,
                message="this prompt already has a suite with that name",
                details={"name": payload.name},
            )

        try:
            suite = await commands.write_suite_version(
                db,
                workspace_id=session.workspace_id,
                actor_id=session.user_id,
                prompt_id=prompt_id,
                name=payload.name,
                output_modality=payload.output_modality,
                cases=_case_drafts(payload.cases),
                now=now,
            )
        except AssertionPatternInvalid as error:
            raise _refuse_invalid_assertion(error) from error

    return _suite_read(suite)


@router.get(
    "/eval-suites/{suite_id}",
    response_model=EvalSuiteRead,
    dependencies=[Depends(declares_action(ManagementAction.EVAL_SUITE_READ))],
)
async def read_eval_suite(
    suite_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> EvalSuiteRead:
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        suite = await repository.load_suite(db, suite_id)
        if suite is None:
            raise _not_found()
        await _visible_prompt(db, session, Action.SUITE_READ, suite.prompt_id)
        cases = await repository.list_cases(db, suite_id)

    return _suite_read(suite, cases)


@router.get(
    "/prompts/{prompt_id}/eval-suites/{name}/versions",
    response_model=list[EvalSuiteRead],
    dependencies=[Depends(declares_action(ManagementAction.EVAL_SUITE_VERSIONS))],
)
async def list_eval_suite_versions(
    prompt_id: Annotated[str, Path()],
    name: Annotated[str, Path(max_length=100)],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
    limit: Annotated[int, Query(ge=1, le=repository.MAX_LIMIT)] = repository.DEFAULT_LIMIT,
) -> list[EvalSuiteRead]:
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _visible_prompt(db, session, Action.SUITE_READ, prompt_id)
        versions = await repository.list_suite_versions(db, prompt_id, name, limit=limit)

    return [_suite_read(suite) for suite in versions]


@router.put(
    "/eval-suites/{suite_id}",
    response_model=EvalSuiteRead,
    status_code=201,
    dependencies=[Depends(declares_action(ManagementAction.EVAL_SUITE_UPDATE))],
)
async def update_eval_suite(
    payload: EvalSuiteUpdate,
    suite_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> EvalSuiteRead:
    now = _utc_now()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        existing = await repository.load_suite(db, suite_id)
        if existing is None:
            raise _not_found()

        await _visible_prompt(db, session, Action.SUITE_EDIT, existing.prompt_id)

        try:
            suite = await commands.write_suite_version(
                db,
                workspace_id=session.workspace_id,
                actor_id=session.user_id,
                prompt_id=existing.prompt_id,
                name=existing.name,
                output_modality=payload.output_modality,
                cases=_case_drafts(payload.cases),
                now=now,
            )
        except AssertionPatternInvalid as error:
            raise _refuse_invalid_assertion(error) from error

    return _suite_read(suite)


@router.post(
    "/prompts/{prompt_id}/eval-runs",
    response_model=EvalRunAccepted,
    status_code=202,
    dependencies=[Depends(declares_action(ManagementAction.EVAL_RUN_START))],
)
async def start_eval_runs(
    payload: EvalRunStart,
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> EvalRunAccepted:
    now = _utc_now()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        prompt = await _visible_prompt(db, session, Action.RUN_START, prompt_id)

        revision = await get_revision(db, payload.version_id)
        if revision is None or revision.prompt_id != prompt_id:
            raise _not_found()

        suites = await repository.list_current_suites(db, prompt_id)
        if payload.suite_names is not None:
            wanted = set(payload.suite_names)
            suites = tuple(suite for suite in suites if suite.name in wanted)

        if not suites:
            raise ManagementRefusal(
                status_code=422,
                code=ErrorCode.VALIDATION_FAILED,
                message="this prompt has no eval suite to run",
                details={"prompt_id": prompt_id},
            )

        handles = await _run_handles(
            db,
            session,
            prompt_id=prompt_id,
            version_id=payload.version_id,
            suites=suites,
            now=now,
        )
        await agent_run_repository.create_run(
            db,
            workspace_id=session.workspace_id,
            requested_by=session.user_id,
            kind=RunKind.EVALUATION,
            plan_basis=PlanBasis.EXPLICIT_USER_ACTION,
            idempotency_key=f"evaluation:{handles[0].run_id}",
            prompt_id=prompt_id,
            version_id=payload.version_id,
            source_refs=tuple(f"eval:{handle.run_id}" for handle in handles),
        )

    log.info(
        "evaluation.runs_accepted",
        workspace_id=session.workspace_id,
        actor_id=session.user_id,
        prompt_id=prompt.id,
        version_id=payload.version_id,
    )

    return EvalRunAccepted(
        prompt_id=prompt_id, version_id=payload.version_id, runs=handles
    )


@router.get(
    "/datasets",
    response_model=list[DatasetRead],
    dependencies=[Depends(declares_action(ManagementAction.DATASET_LIST))],
)
async def list_datasets(
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> list[DatasetRead]:
    """The dataset library: the shipped Chung catalogue plus the workspace's own.

    The two halves are merged here and nowhere else. A builtin comes from a file
    in the image because a catalogue identical in every workspace cannot be rows
    under RLS (see ``evaluation.catalogue``); a workspace row comes from
    ``evaluation.dataset`` under the tenant policy. They leave as one list of one
    type, so the tree never has to know which is which — only ``read_only`` says
    so, and that is a fact about what may be edited rather than about where it
    was stored.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        owned = await repository.list_workspace_datasets(db)

    return [
        _dataset_read(dataset)
        for dataset in (*catalogue.list_builtin_datasets(), *owned)
    ]


@router.get(
    "/datasets/{dataset_id}",
    response_model=DatasetDetailRead,
    dependencies=[Depends(declares_action(ManagementAction.DATASET_READ))],
)
async def read_dataset(
    dataset_id: Annotated[str, Path(max_length=100)],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> DatasetDetailRead:
    """One dataset and its cases — what the editor loads, and a read-only preview
    of a shipped set."""
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        dataset = await _resolve_dataset(db, dataset_id)

    if dataset is None:
        raise _no_such_dataset(dataset_id)

    return _dataset_detail_read(dataset)


@router.post(
    "/datasets",
    response_model=DatasetDetailRead,
    status_code=201,
    dependencies=[Depends(declares_action(ManagementAction.DATASET_CREATE))],
)
async def create_dataset(
    payload: DatasetWrite,
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> DatasetDetailRead:
    """Write a dataset into the library, from scratch or by copying a shipped set.

    Copying happens server-side rather than by the client reading a builtin and
    posting it back, so the copy is provably the same set: its fingerprint equals
    the original's, and a prompt attached to either is measured identically until
    somebody edits one.
    """
    now = _utc_now()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _may_edit_library(db, session)

        source: DatasetSpec | None = None
        if payload.copy_from is not None:
            source = await _resolve_dataset(db, payload.copy_from)
            if source is None:
                raise _no_such_dataset(payload.copy_from)

        cases = _case_drafts(payload.cases) if payload.cases else (
            source.cases if source is not None else ()
        )
        if not cases:
            raise ManagementRefusal(
                status_code=422,
                code=ErrorCode.VALIDATION_FAILED,
                message="a dataset with no cases measures nothing",
            )

        modality = source.output_modality if source is not None else payload.output_modality
        kind = source.kind if source is not None else payload.kind

        try:
            dataset_id = await commands.create_dataset(
                db,
                workspace_id=session.workspace_id,
                actor_id=session.user_id,
                folder=payload.folder,
                name=payload.name,
                description=payload.description or (
                    source.description if source is not None else ""
                ),
                kind=kind,
                tags=source.tags if source is not None else tuple(payload.tags),
                output_modality=modality,
                cases=cases,
                now=now,
            )
        except DatasetNameTaken as error:
            raise _refuse_duplicate_name(error) from error
        except AssertionPatternInvalid as error:
            raise _refuse_invalid_assertion(error) from error

        written = await repository.load_workspace_dataset(db, dataset_id)

    assert written is not None  # noqa: S101 - written in the same transaction
    return _dataset_detail_read(written)


@router.put(
    "/datasets/{dataset_id}",
    response_model=DatasetDetailRead,
    dependencies=[Depends(declares_action(ManagementAction.DATASET_UPDATE))],
)
async def update_dataset(
    payload: DatasetWrite,
    dataset_id: Annotated[str, Path(max_length=100)],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> DatasetDetailRead:
    """Replace a dataset's content.

    **An edit cannot reach a past run.** Every suite this dataset was
    materialised into is an immutable copy taken at that moment; what changes is
    the fingerprint, so the next run writes a new suite version and the tree
    marks every prompt that attached it as changed since it last ran. That is
    the whole reason a dataset and a suite are different objects.
    """
    now = _utc_now()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _may_edit_library(db, session)

        existing = await _resolve_dataset(db, dataset_id)
        if existing is None:
            raise _no_such_dataset(dataset_id)
        if existing.read_only:
            raise _refuse_read_only(dataset_id)

        cases = _case_drafts(payload.cases)
        if not cases:
            raise ManagementRefusal(
                status_code=422,
                code=ErrorCode.VALIDATION_FAILED,
                message="a dataset with no cases measures nothing",
            )

        try:
            await commands.update_dataset(
                db,
                workspace_id=session.workspace_id,
                actor_id=session.user_id,
                dataset_id=dataset_id,
                folder=payload.folder,
                name=payload.name,
                description=payload.description,
                kind=payload.kind,
                tags=tuple(payload.tags),
                output_modality=payload.output_modality,
                cases=cases,
                now=now,
            )
        except DatasetNameTaken as error:
            raise _refuse_duplicate_name(error) from error
        except AssertionPatternInvalid as error:
            raise _refuse_invalid_assertion(error) from error

        written = await repository.load_workspace_dataset(db, dataset_id)

    assert written is not None  # noqa: S101 - written in the same transaction
    return _dataset_detail_read(written)


@router.delete(
    "/datasets/{dataset_id}",
    response_model=DatasetDeleted,
    dependencies=[Depends(declares_action(ManagementAction.DATASET_DELETE))],
)
async def delete_dataset(
    dataset_id: Annotated[str, Path(max_length=100)],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> DatasetDeleted:
    """Remove a dataset, its cases, and every tick pointing at it.

    The count of removed ticks comes back rather than being swallowed: deleting
    a dataset changes what *other* prompts will be measured with, and a number
    the interface can put in a sentence is the difference between that being a
    decision and being a surprise. Suites and runs already produced are
    untouched — they are the history, and this is not.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _may_edit_library(db, session)

        existing = await _resolve_dataset(db, dataset_id)
        if existing is None:
            raise _no_such_dataset(dataset_id)
        if existing.read_only:
            raise _refuse_read_only(dataset_id)

        detached = await commands.delete_dataset(
            db,
            workspace_id=session.workspace_id,
            actor_id=session.user_id,
            dataset_id=dataset_id,
        )

    return DatasetDeleted(dataset_id=dataset_id, detached=detached)


@router.post(
    "/prompts/{prompt_id}/datasets/draft",
    response_model=DatasetDetailRead,
    status_code=201,
    dependencies=[Depends(declares_action(ManagementAction.DATASET_DRAFT))],
)
async def draft_dataset(
    payload: DatasetDraftRequest,
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> DatasetDetailRead:
    """Ask the app agent to draft a dataset from this prompt's body.

    **The result lands in the library and is not attached.** A model does not get
    to decide what a prompt is measured against; a person ticks the drafted set,
    or opens it in the editor first. That separation is the same one the whole
    step rests on, and it is what makes an imperfect draft harmless.

    The agent call happens **outside** the database transaction. It is a network
    call to a third party that can take tens of seconds, and holding a Postgres
    connection — with ``SET LOCAL app.workspace_id`` on it — open across that
    would tie tenant isolation's session state to a provider's latency.
    """
    now = _utc_now()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        prompt = await _visible_prompt(db, session, Action.SUITE_EDIT, prompt_id)

        if payload.version_id:
            revision = await get_revision(db, payload.version_id)
        else:
            # Newest first, so one row is the latest — which is the revision
            # somebody standing on this screen has just written.
            chain = await list_revision_chain(db, prompt_id, limit=1)
            revision = chain[0] if chain else None

        if revision is None or revision.prompt_id != prompt_id:
            raise _not_found()

    try:
        outcome = await draft_cases(
            workspace_id=session.workspace_id,
            actor_id=session.user_id,
            prompt_id=prompt_id,
            prompt_title=prompt.title,
            prompt_body=revision.body,
            brief=payload.brief or "",
            case_target=payload.case_target,
        )
    except DrafterUnavailableError as error:
        raise ManagementRefusal(
            status_code=503,
            code=ErrorCode.EVAL_DRAFTER_UNAVAILABLE,
            message="the drafting agent could not be reached; write the dataset by hand or retry",
        ) from error

    if not outcome.cases:
        # A successful call that produced nothing usable. Distinct from the
        # agent being down, and the person can act on only one of the two.
        raise ManagementRefusal(
            status_code=422,
            code=ErrorCode.EVAL_DRAFTER_EMPTY,
            message="the agent returned no case that could be stored; try again or write one by hand",
            details={"dropped_cases": outcome.dropped_cases},
        )

    name = payload.name or _drafted_name(prompt.title)
    folder = payload.folder if payload.folder is not None else prompt.namespace

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _may_edit_library(db, session)
        try:
            dataset_id = await commands.create_dataset(
                db,
                workspace_id=session.workspace_id,
                actor_id=session.user_id,
                folder=folder,
                name=name,
                description=_DRAFTED_DESCRIPTION,
                kind=DatasetKind.GOLDEN,
                tags=("AI draft",),
                output_modality=OutputModality.TEXT,
                cases=outcome.cases,
                now=now,
            )
        except DatasetNameTaken as error:
            raise _refuse_duplicate_name(error) from error

        written = await repository.load_workspace_dataset(db, dataset_id)

    assert written is not None  # noqa: S101 - written in the same transaction
    return _dataset_detail_read(written)


@router.get(
    "/prompts/{prompt_id}/dataset-attachments",
    response_model=list[AttachmentRead],
    dependencies=[Depends(declares_action(ManagementAction.DATASET_ATTACHMENT_LIST))],
)
async def list_dataset_attachments(
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> list[AttachmentRead]:
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _visible_prompt(db, session, Action.SUITE_READ, prompt_id)
        attachments = await repository.list_attachments(db, prompt_id)
        # Inside the transaction: resolving a `dst_` id is a query under the
        # tenant policy, and only a `builtin:` id is answerable from a file.
        return [await _attachment_read(db, attachment) for attachment in attachments]


@router.put(
    "/prompts/{prompt_id}/dataset-attachments",
    response_model=list[AttachmentRead],
    dependencies=[Depends(declares_action(ManagementAction.DATASET_ATTACHMENT_REPLACE))],
)
async def replace_dataset_attachments(
    payload: AttachmentWrite,
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> list[AttachmentRead]:
    """Set which datasets measure this prompt. Writes no suite and runs nothing.

    **Declarative, not incremental.** The body is the whole tick-state, so a tick
    and an untick are the same request and replaying one changes nothing. That
    matches what a checkbox list actually is, and it sidesteps putting a
    ``builtin:<slug>@<n>`` id into a path segment.

    Detaching loses nothing: the suite versions an attachment materialised stay
    in ``eval_suite`` and every run still names the ``suite_id`` it measured
    with. What a detach removes is a future intention.
    """
    now = _utc_now()
    wanted = list(dict.fromkeys(payload.dataset_ids))

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _visible_prompt(db, session, Action.SUITE_EDIT, prompt_id)

        resolved: dict[str, DatasetSpec] = {}
        unknown: list[str] = []
        for dataset_id in wanted:
            dataset = await _resolve_dataset(db, dataset_id)
            if dataset is None:
                unknown.append(dataset_id)
            else:
                resolved[dataset_id] = dataset

        if unknown:
            raise ManagementRefusal(
                status_code=422,
                code=ErrorCode.VALIDATION_FAILED,
                message="no such dataset",
                details={"dataset_ids": unknown},
            )

        existing = {row.dataset_id for row in await repository.list_attachments(db, prompt_id)}

        for dataset_id in existing - set(wanted):
            await commands.detach_dataset(
                db,
                workspace_id=session.workspace_id,
                actor_id=session.user_id,
                prompt_id=prompt_id,
                dataset_id=dataset_id,
            )

        # Detaches run first so that swapping one dataset for another with the
        # same name works in a single request — otherwise the unique constraint
        # on `suite_name` would refuse the incoming half before the outgoing
        # half had gone.
        for dataset_id in wanted:
            if dataset_id in existing:
                continue
            dataset = resolved[dataset_id]
            try:
                await commands.attach_dataset(
                    db,
                    workspace_id=session.workspace_id,
                    actor_id=session.user_id,
                    prompt_id=prompt_id,
                    dataset=dataset,
                    now=now,
                )
            except SuiteNameTaken as error:
                raise ManagementRefusal(
                    status_code=409,
                    code=ErrorCode.ALREADY_EXISTS,
                    message=(
                        "another dataset is already attached under this name; two datasets "
                        "sharing a suite name would overwrite each other's results"
                    ),
                    details={"dataset_id": dataset_id, "suite_name": error.suite_name},
                ) from error

        attachments = await repository.list_attachments(db, prompt_id)
        return [await _attachment_read(db, attachment) for attachment in attachments]


@router.post(
    "/prompts/{prompt_id}/eval-runs/from-attachments",
    response_model=EvalRunAccepted,
    status_code=202,
    dependencies=[Depends(declares_action(ManagementAction.EVAL_RUN_START_FROM_ATTACHMENTS))],
)
async def start_eval_runs_from_attachments(
    payload: EvalRunStart,
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> EvalRunAccepted:
    """Materialise the prompt's attachments into suites and run them.

    **This is where a dataset becomes a yardstick.** Each attachment is
    fingerprinted against the library dataset behind it: unchanged reuses the
    suite version it materialised last time, changed writes the next version.
    Ten runs of an unchanged set therefore leave one suite version behind rather
    than ten, which is what keeps ``suite_version`` a record of how often the
    yardstick moved instead of how often somebody pressed a button.

    ``payload.suite_names`` is ignored here: the attachment list *is* the
    selection, and a second way to narrow it would be two sources of truth for
    one question.
    """
    now = _utc_now()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        prompt = await _visible_prompt(db, session, Action.RUN_START, prompt_id)

        revision = await get_revision(db, payload.version_id)
        if revision is None or revision.prompt_id != prompt_id:
            raise _not_found()

        attachments = await repository.list_attachments(db, prompt_id)
        if not attachments:
            raise ManagementRefusal(
                status_code=422,
                code=ErrorCode.VALIDATION_FAILED,
                message="this prompt has no dataset attached to run",
                details={"prompt_id": prompt_id},
            )

        suites: list[SuiteRow] = []
        unresolved: list[str] = []
        for attachment in attachments:
            dataset = await _resolve_dataset(db, attachment.dataset_id)
            if dataset is None:
                # A retired builtin version. Skipped rather than fatal: one
                # stale row must not stop the other four sets from running, and
                # the workspace already renders it as unresolved.
                unresolved.append(attachment.dataset_id)
                continue

            try:
                suite_id = await commands.materialise_attachment(
                    db,
                    workspace_id=session.workspace_id,
                    actor_id=session.user_id,
                    prompt_id=prompt_id,
                    attachment=attachment,
                    dataset=dataset,
                    now=now,
                )
            except AssertionPatternInvalid as error:
                raise _refuse_invalid_assertion(error) from error

            suite = await repository.load_suite(db, suite_id)
            if suite is not None:
                suites.append(suite)

        if not suites:
            raise ManagementRefusal(
                status_code=422,
                code=ErrorCode.VALIDATION_FAILED,
                message="none of this prompt's attached datasets could be resolved",
                details={"prompt_id": prompt_id, "dataset_ids": unresolved},
            )

        handles = await _run_handles(
            db,
            session,
            prompt_id=prompt_id,
            version_id=payload.version_id,
            suites=suites,
            now=now,
        )
        await agent_run_repository.create_run(
            db,
            workspace_id=session.workspace_id,
            requested_by=session.user_id,
            kind=RunKind.EVALUATION,
            plan_basis=PlanBasis.EXPLICIT_USER_ACTION,
            idempotency_key=f"evaluation:{handles[0].run_id}",
            prompt_id=prompt_id,
            version_id=payload.version_id,
            source_refs=tuple(f"eval:{handle.run_id}" for handle in handles),
        )

    log.info(
        "evaluation.runs_accepted_from_attachments",
        workspace_id=session.workspace_id,
        actor_id=session.user_id,
        prompt_id=prompt.id,
        version_id=payload.version_id,
        suite_count=len(suites),
        unresolved_count=len(unresolved),
    )

    return EvalRunAccepted(prompt_id=prompt_id, version_id=payload.version_id, runs=handles)


@router.get(
    "/eval-runs/{run_id}",
    response_model=EvalRunRead,
    dependencies=[Depends(declares_action(ManagementAction.EVAL_RUN_READ))],
)
async def read_eval_run(
    run_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> EvalRunRead:
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        run = await repository.load_run(db, run_id)
        if run is None:
            raise _not_found()
        await _visible_prompt(db, session, Action.RUN_READ, run.prompt_id)

    return _run_read(run)


@router.get(
    "/prompts/{prompt_id}/eval-runs",
    response_model=list[EvalRunSummaryRead],
    dependencies=[Depends(declares_action(ManagementAction.EVAL_RUN_LIST))],
)
async def list_prompt_eval_runs(
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
    version_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=RUN_HISTORY_LIMIT)] = RUN_HISTORY_LIMIT,
) -> list[EvalRunSummaryRead]:
    """What this prompt's suites have said about it, newest first.

    **The GET that `POST /prompts/{id}/eval-runs` never had.** Every other read
    here needs a `run_id`, which is no use to a screen opening on a prompt it has
    just been handed: it has to be able to ask *what has been run against this*
    before it knows any run.

    `version_id` narrows to one revision — what the tab shows for the revision
    selected in the rail. Omitted, it returns every revision's runs, which is what
    a pass-rate trend across revisions is computed from. Both come from one query
    so the trend and the detail cannot disagree.

    **The refusal is `_visible_prompt`'s**, so a prompt the actor cannot see
    answers not-found before any run is read — the same two shapes as every other
    route in this module, and the reason a run's existence cannot be used to
    infer a private prompt's.

    A prompt with no runs answers `[]`. That is the ordinary state of a prompt
    nobody has evaluated yet, and the tab renders it as an invitation rather than
    as a failure.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _visible_prompt(db, session, Action.RUN_READ, prompt_id)
        listings = await repository.list_runs_for_prompt(
            db, prompt_id, version_id=version_id, limit=limit
        )

    return [_run_summary_read(listing) for listing in listings]


@router.get(
    "/eval-runs/{run_id}/cases",
    response_model=list[CaseResultRead],
    dependencies=[Depends(declares_action(ManagementAction.EVAL_RUN_CASES))],
)
async def read_eval_run_cases(
    run_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> list[CaseResultRead]:
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        run = await repository.load_run(db, run_id)
        if run is None:
            raise _not_found()
        await _visible_prompt(db, session, Action.RUN_READ, run.prompt_id)
        results = await repository.list_case_results(db, run_id)

    return [_case_result_read(result) for result in results]


@router.get(
    "/eval-runs/{run_id}/cases/{case_result_id}/trace",
    response_model=EvalCaseTraceRead,
    dependencies=[Depends(declares_action(ManagementAction.EVAL_CASE_TRACE))],
)
async def read_eval_case_trace(
    run_id: Annotated[str, Path()],
    case_result_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> EvalCaseTraceRead:
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        run = await repository.load_run(db, run_id)
        if run is None:
            raise _not_found()
        await _visible_prompt(db, session, Action.RUN_READ, run.prompt_id)
        results = await repository.list_case_results(db, run_id)
        result = next((entry for entry in results if entry.id == case_result_id), None)
        if result is None:
            raise _not_found()
        revision = await get_revision(db, run.version_id)

    failed = result.outcome == CaseOutcome.ERROR
    root_id = f"{result.id}:root"
    spans = [
        EvalTraceSpanRead(
            span_id=root_id,
            name="evaluation.case",
            kind="span",
            status="error" if failed else "success",
            duration_ms=result.latency_ms,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )
    ]
    if result.latency_ms is not None:
        spans.append(
            EvalTraceSpanRead(
                span_id=f"{result.id}:execution",
                parent_span_id=root_id,
                name="evaluation.dispatch",
                kind="generation",
                status="error" if failed else "success",
                duration_ms=result.latency_ms,
                model=None if revision is None else revision.upstream_model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
            )
        )
    spans.extend(
        EvalTraceSpanRead(
            span_id=f"{result.id}:assertion:{index}",
            parent_span_id=root_id,
            name=f"assertion.{assertion.type.value}",
            kind="event",
            status="success" if assertion.passed else "error",
        )
        for index, assertion in enumerate(result.assertion_results)
    )
    return EvalCaseTraceRead(
        trace_id=result.id,
        status="error" if failed else "success",
        duration_ms=result.latency_ms,
        spans=spans,
    )


@router.get(
    "/prompts/{prompt_id}/comparison",
    response_model=list[ComparisonBlockRead],
    dependencies=[Depends(declares_action(ManagementAction.COMPARISON_READ))],
)
async def read_comparison(
    prompt_id: Annotated[str, Path()],
    session: Annotated[Session, Depends(require_session)],
    *,
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
    candidate: Annotated[str, Query()],
) -> list[ComparisonBlockRead]:
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _visible_prompt(db, session, Action.RUN_READ, prompt_id)
        blocks = await summary.get_comparison(db, prompt_id, candidate)

    return [
        ComparisonBlockRead(
            suite_id=block.suite_id,
            suite_name=block.suite_name,
            suite_version=block.suite_version,
            candidate_run_id=block.candidate_run_id,
            baseline_run_id=block.baseline_run_id,
            baseline_ran_at=block.baseline_ran_at,
            cases=[
                CaseComparisonRead(
                    case_id=case.case_id,
                    name=case.name,
                    baseline_outcome=case.baseline_outcome,
                    candidate_outcome=case.candidate_outcome,
                    changed=case.changed,
                )
                for case in block.cases
            ],
            cost_delta=None
            if block.cost_delta is None
            else CostDeltaRead(
                input_tokens=block.cost_delta.input_tokens,
                output_tokens=block.cost_delta.output_tokens,
                cost=block.cost_delta.cost,
                currency=block.cost_delta.currency,
                ratio=block.cost_delta.ratio,
            ),
            withheld_reason=block.withheld_reason,
            cost_warning=block.cost_warning,
        )
        for block in blocks
    ]
