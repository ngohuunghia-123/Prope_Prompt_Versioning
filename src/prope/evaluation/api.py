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
from prope.db.session import workspace_transaction
from prope.dependencies import get_sessionmaker
from prope.errors import ErrorCode
from prope.evaluation import commands, repository, summary
from prope.evaluation.domain import (
    AssertionPatternInvalid,
    AssertionSpec,
    CaseDraft,
    CaseResultRow,
    CaseRow,
    RunRole,
    RunRow,
    SuiteRow,
)
from prope.evaluation.observability import baseline_reused_total
from prope.evaluation.schemas import (
    AssertionRead,
    CaseComparisonRead,
    CaseResultRead,
    ComparisonBlockRead,
    CostDeltaRead,
    EvalCaseRead,
    EvalCaseWrite,
    EvalRunAccepted,
    EvalRunHandle,
    EvalRunRead,
    EvalRunStart,
    EvalSuiteCreate,
    EvalSuiteRead,
    EvalSuiteUpdate,
)
from prope.prompt_registry.seams import PromptRow, get_prompt, get_released_revision, get_revision
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


def _forbidden(action: Action) -> ManagementRefusal:
    return ManagementRefusal(
        status_code=403,
        code=ErrorCode.PERMISSION_DENIED,
        message=f"this action requires the {action.value} permission",
        details={"permission": action.value, "subject_type": SubjectType.PROMPT.value},
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


def _drafts(cases: list[EvalCaseWrite]) -> tuple[CaseDraft, ...]:
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
                cases=_drafts(payload.cases),
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
                cases=_drafts(payload.cases),
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

        released = await get_released_revision(db, prompt_id)
        handles: list[EvalRunHandle] = []

        candidate_ids = await commands.create_runs(
            db,
            workspace_id=session.workspace_id,
            actor_id=session.user_id,
            prompt_id=prompt_id,
            version_id=payload.version_id,
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

        if released is not None and released.version_id != payload.version_id:
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
