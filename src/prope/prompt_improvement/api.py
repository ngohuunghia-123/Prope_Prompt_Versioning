"""INT-045..INT-050 — seven operations, four permissions, and no new action minted.

**The seventh is ``GET .../improvement-schedule``**, added because the setting
was write-only and therefore unrenderable: a toggle cannot read its own state
from a PUT. It mints a ``ManagementAction`` and no ``Action`` — the access-control
vocabulary is untouched at twenty-seven, because reading a spending commitment is
governed by the permission that already governs changing one.


**Nothing here writes a revision, and one route is deliberately shaped so it
cannot.** ``POST /proposals/{id}/accept`` marks a disposition, appends a history
event and returns the candidate body. The write is prompt-registry's
``create_revision``, on a separate and explicit request the person makes
themselves — chat-orchestrator's ``pending_action`` shape and ADR-0066's rule:
*proposed by an agent, performed by a person.*

**Four permissions, all of them already in the vocabulary.** Reading is
``prompt.read``, because a grant confers visibility of the prompt and everything
hanging off it — prompt-registry's argument, unchanged. Dismissing a finding is
``prompt.edit``: it is an editorial act on the prompt's own record, and a reader
who could silence findings on somebody else's prompt could clear the screen they
are meant to be reading. **Accepting is ``revision.create``**, not a read and not
``prompt.edit``: the route hands back a body destined for a revision, and gating
it lower than the act it prefills would be a permission gap wearing a read's
clothes. The schedule is ``spend_ceiling.manage``, because enabling a recurring
charge against the workspace's provider credential is a spending decision before
it is an authoring one.

**The refusal shape.** Not-found when the actor cannot see the prompt; forbidden
naming the missing permission when they can (A-116, A-076). The inbox applies the
same asymmetry at the LIST level: a prompt the reader cannot see contributes
nothing at all, and a workspace where every prompt is invisible answers
byte-identically to one where nothing is wrong (SR-7).
"""

from datetime import UTC, datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.access_control.actions import Action
from prope.access_control.seams import AccessLevel, Actor, ActorType, Subject, SubjectType, may
from prope.db.session import workspace_transaction
from prope.dependencies import get_sessionmaker
from prope.errors import ErrorCode
from prope.prompt_improvement import repository
from prope.prompt_improvement.domain import (
    DEFAULT_CADENCE_DAYS,
    DetectorId,
    ProposalStatus,
    RemedyFamily,
    RemedyKind,
    Severity,
)
from prope.prompt_improvement.observability import proposals_open, proposals_total
from prope.prompt_improvement.schemas import (
    DismissalCreate,
    FindingRead,
    InboxRead,
    ProposalAccepted,
    ProposalDetailRead,
    ProposalRead,
    ScheduleRead,
    ScheduleWrite,
)
from prope.prompt_registry import repository as registry
from prope.prompt_registry.domain import PromptRow
from prope.property_history.append import append
from prope.property_history.domain import ActorType as HistoryActorType
from prope.property_history.domain import HistoryEventDraft
from prope.session_auth import (
    ManagementAction,
    ManagementRefusal,
    Session,
    declares_action,
    require_session,
)

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1")

PROMPT_ID = Annotated[str, Path(min_length=1, max_length=64)]
FINDING_ID = Annotated[str, Path(min_length=1, max_length=64)]
PROPOSAL_ID = Annotated[str, Path(min_length=1, max_length=64)]
WORKSPACE_ID = Annotated[str, Path(min_length=1, max_length=64)]

#: How many prompts the inbox authorises before it stops. Each one is a prompt
#: read plus a ``may()``, so this bounds the work an inbox request can do — and
#: it is separate from the finding limit below because a workspace can have many
#: prompts with one finding each or one prompt with many.
INBOX_PROMPT_LIMIT = 200

INBOX_FINDING_LIMIT = 50


def _not_found() -> ManagementRefusal:
    """A prompt the actor cannot see and an id that never existed answer the same bytes."""
    return ManagementRefusal(status_code=404, code=ErrorCode.NOT_FOUND, message="no such prompt")


def _forbidden(action: Action) -> ManagementRefusal:
    """Names the missing permission. Only ever raised when the actor CAN see the subject."""
    return ManagementRefusal(
        status_code=403, code=ErrorCode.PERMISSION_DENIED, message=f"requires {action.value}"
    )


def _refused(code: str) -> ManagementRefusal:
    """A machine code the client renders. ADR-0053 — no sentence crosses the wire."""
    return ManagementRefusal(status_code=409, code=ErrorCode.VALIDATION_FAILED, message=code)


def _actor(session: Session) -> Actor:
    return Actor(type=ActorType.USER, id=session.user_id, workspace_id=session.workspace_id)


def _subject(row: PromptRow) -> Subject:
    """ADR-0020's contract: the subject is passed in, never read by access-control.

    Carries ``namespace`` because ADR-0061 makes a namespace grant the fifth
    source ``may()`` unions, and a subject that omitted it would silently skip
    that source — which reads as *the grant does not work* rather than as a
    missing field.
    """
    return Subject(
        type=SubjectType.PROMPT,
        id=row.id,
        workspace_id=row.workspace_id,
        owner_id=row.owner_id,
        access_level=AccessLevel(row.access_level),
        namespace=row.namespace,
    )


async def _visible_prompt(db: AsyncSession, session: Session, prompt_id: str) -> PromptRow:
    """Load, authorise, return — in that order. Nothing leaves before ``may()``."""
    row = await registry.load_prompt(db, prompt_id)
    if row is None or row.workspace_id != session.workspace_id:
        raise _not_found()
    if not await may(db, _actor(session), Action.PROMPT_READ, _subject(row)):
        raise _not_found()
    return row


def _finding_read(row: dict[str, Any]) -> FindingRead:
    proposal = (
        ProposalRead(
            proposal_id=row["proposal_id"],
            remedy_kind=row["remedy_kind"],
            remedy_family=row["remedy_family"],
            gate_delta=row["gate_delta"],
            expires_at=row["expires_at"],
        )
        if row.get("proposal_id")
        else None
    )
    return FindingRead(
        finding_id=row["id"],
        prompt_id=row["prompt_id"],
        detector_id=DetectorId(row["detector_id"]),
        severity=Severity(row["severity"]),
        params=row["params"] or {},
        evidence_line=row["evidence_line"],
        first_seen=row["first_seen"],
        last_seen=row["last_seen"],
        occurrence_count=row["occurrence_count"],
        status=row["status"],
        proposal=proposal,
    )


def _inbox(rows: list[FindingRead]) -> InboxRead:
    """Counts computed here so two clients cannot disagree about them."""
    return InboxRead(
        findings=rows,
        total=len(rows),
        warning_count=sum(1 for row in rows if row.severity is Severity.WARNING),
        advice_count=sum(1 for row in rows if row.severity is Severity.ADVICE),
    )


@router.get(
    "/improvement/findings",
    response_model=InboxRead,
    dependencies=[Depends(declares_action(ManagementAction.IMPROVEMENT_INBOX_READ))],
)
async def read_inbox(
    session: Annotated[Session, Depends(require_session)],
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> InboxRead:
    """INT-045. Every open finding on a prompt this reader may see, and nothing else.

    **Two steps, and the split is SR-7.** The first asks which prompts have an
    open finding — ids only, no detector, no evidence, no count. The second reads
    findings for the ids that survived ``may()``. A prompt the reader cannot see
    never reaches the second query, so it contributes no row, no count, and no
    total that differs from a workspace where nothing is wrong.

    **Authorised prompt by prompt rather than by one SQL predicate**, because
    ADR-0020 makes a permission decision take the subject's ``owner_id`` and
    ``access_level`` from the row the caller read — and the alternative here is a
    join onto ``registry.prompt_property``, which is the cross-schema read
    ADR-0055 refuses and this module's lock forbids by name.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        candidates = await repository.prompts_with_open_findings(
            db, workspace_id=session.workspace_id, limit=INBOX_PROMPT_LIMIT
        )

        visible: list[str] = []
        for prompt_id in candidates:
            row = await registry.load_prompt(db, prompt_id)
            if row is None or row.workspace_id != session.workspace_id:
                continue
            if await may(db, _actor(session), Action.PROMPT_READ, _subject(row)):
                visible.append(prompt_id)

        rows = await repository.list_inbox(
            db,
            workspace_id=session.workspace_id,
            prompt_ids=visible,
            limit=INBOX_FINDING_LIMIT,
        )

    return _inbox([_finding_read(dict(row)) for row in rows])


@router.get(
    "/prompts/{prompt_id}/findings",
    response_model=list[FindingRead],
    dependencies=[Depends(declares_action(ManagementAction.IMPROVEMENT_PROMPT_FINDINGS_READ))],
)
async def read_prompt_findings(
    prompt_id: PROMPT_ID,
    session: Annotated[Session, Depends(require_session)],
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> list[FindingRead]:
    """INT-046. The per-prompt tab, beside ADR-0055's call-records tab.

    Returns dismissed and resolved findings as well as open ones. This is the
    prompt's own history of degradation and a reader looking at it has asked for
    it — unlike the inbox, which is a queue and shows only what is outstanding.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        await _visible_prompt(db, session, prompt_id)
        rows = await repository.findings_for_prompt(
            db, workspace_id=session.workspace_id, prompt_id=prompt_id
        )

    return [_finding_read(dict(row)) for row in rows]


@router.post(
    "/improvement/findings/{finding_id}/dismiss",
    response_model=FindingRead,
    dependencies=[Depends(declares_action(ManagementAction.IMPROVEMENT_FINDING_DISMISS))],
)
async def dismiss_finding(
    finding_id: FINDING_ID,
    payload: DismissalCreate,
    session: Annotated[Session, Depends(require_session)],
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> FindingRead:
    """INT-047. Not for me. **Writes no history event, and that is A-102.**

    Dismissing a finding that carries no proposal is noise-suppression during
    reading, which is exactly the act A-102 says is not a state change on a prompt
    property. It is recorded on the row itself with its reason and its actor, and
    the reason is what makes the per-detector dismissal rate readable (OQ-157).

    A **proposal** disposition is a different object and does write an event —
    see :func:`accept_proposal`.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        row = await repository.read_finding(
            db, workspace_id=session.workspace_id, finding_id=finding_id
        )
        if row is None:
            raise _not_found()

        prompt = await _visible_prompt(db, session, row["prompt_id"])
        if not await may(db, _actor(session), Action.PROMPT_EDIT, _subject(prompt)):
            raise _forbidden(Action.PROMPT_EDIT)

        dismissed = await repository.dismiss_finding(
            db,
            workspace_id=session.workspace_id,
            finding_id=finding_id,
            reason=payload.reason,
            actor_id=session.user_id,
        )
        if dismissed is None:
            raise _refused("finding_already_closed")

        rows = await repository.findings_for_prompt(
            db, workspace_id=session.workspace_id, prompt_id=row["prompt_id"]
        )

    log.info("improvement.finding.dismissed", detector_id=row["detector_id"])
    match = next((entry for entry in rows if entry["id"] == finding_id), None)
    return _finding_read(dict(match)) if match else _finding_read(row)


@router.get(
    "/improvement/proposals/{proposal_id}",
    response_model=ProposalDetailRead,
    dependencies=[Depends(declares_action(ManagementAction.IMPROVEMENT_PROPOSAL_READ))],
)
async def read_proposal_detail(
    proposal_id: PROPOSAL_ID,
    session: Annotated[Session, Depends(require_session)],
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ProposalDetailRead:
    """The detail screen, opened deliberately — the one pre-decision body read.

    **This is ADR-0070 §5's load-bearing read.** An ``llm_edit`` proposal's
    accept button does not render until the candidate body and its diff do, so
    the reviewer's evidence IS the literal payload: the body, the gate delta,
    and the rationale as a clearly machine-attributed side note — never a
    paraphrase of the payload standing in for it.

    ``prompt.read`` governs, for the findings list's own reason: a grant confers
    visibility of the prompt and everything hanging off it. This route adds a
    `ManagementAction` and no `Action` — the vocabulary stays untouched, the
    same trade the schedule's read route made.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        proposal = await repository.read_proposal(
            db, workspace_id=session.workspace_id, proposal_id=proposal_id
        )
        if proposal is None:
            raise _not_found()

        prompt = await _visible_prompt(db, session, proposal["prompt_id"])
        if not await may(db, _actor(session), Action.PROMPT_READ, _subject(prompt)):
            raise _not_found()

    return ProposalDetailRead(
        proposal_id=str(proposal["id"]),
        prompt_id=str(proposal["prompt_id"]),
        finding_id=str(proposal["finding_id"]),
        remedy_kind=RemedyKind(proposal["remedy_kind"]),
        remedy_family=(
            RemedyFamily(proposal["remedy_family"]) if proposal["remedy_family"] else None
        ),
        candidate_body=proposal["candidate_body"],
        gate_delta=proposal["gate_delta"],
        draft_rationale=proposal["draft_rationale"],
        rails_report=proposal["rails_report"],
        status=str(proposal["status"]),
        expires_at=proposal["expires_at"],
        created_at=proposal["created_at"],
    )


@router.post(
    "/improvement/proposals/{proposal_id}/accept",
    response_model=ProposalAccepted,
    dependencies=[Depends(declares_action(ManagementAction.IMPROVEMENT_PROPOSAL_ACCEPT))],
)
async def accept_proposal(
    proposal_id: PROPOSAL_ID,
    session: Annotated[Session, Depends(require_session)],
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ProposalAccepted:
    """INT-048. Records the decision, hands back the body, **writes no revision** (SR-6).

    Declared under ``revision.create`` rather than a read permission. The response
    carries a body destined for ``POST /prompts/{id}/revisions``, and gating this
    lower than the act it prefills would be a permission gap wearing a read's
    clothes — somebody who cannot create a revision has no use for a prefill and
    should not be handed one.

    The history event is written in the SAME transaction as the disposition, for
    release-control's reason: *there is no release without a trail* applied one
    step earlier. A decision recorded without its event would be a decision the
    accountability record cannot see.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        proposal = await repository.read_proposal(
            db, workspace_id=session.workspace_id, proposal_id=proposal_id
        )
        if proposal is None:
            raise _not_found()

        prompt = await _visible_prompt(db, session, proposal["prompt_id"])
        if not await may(db, _actor(session), Action.REVISION_CREATE, _subject(prompt)):
            raise _forbidden(Action.REVISION_CREATE)

        decided = await repository.decide_proposal(
            db,
            workspace_id=session.workspace_id,
            proposal_id=proposal_id,
            status=ProposalStatus.ACCEPTED,
            actor_id=session.user_id,
        )
        if decided is None:
            raise _refused("proposal_already_decided")

        await _record_disposition(
            db,
            session=session,
            action="improvement_proposal_accepted",
            proposal=proposal,
            reason=None,
        )

    proposals_total.labels(
        remedy_family=proposal["remedy_family"] or "note",
        disposition=str(ProposalStatus.ACCEPTED),
    ).inc()
    proposals_open.dec()

    return ProposalAccepted(
        proposal_id=proposal_id,
        prompt_id=proposal["prompt_id"],
        remedy_family=proposal["remedy_family"],
        candidate_body=proposal["candidate_body"],
        gate_delta=proposal["gate_delta"],
        draft_rationale=proposal.get("draft_rationale"),
        rails_report=proposal.get("rails_report"),
    )


@router.post(
    "/improvement/proposals/{proposal_id}/dismiss",
    response_model=ProposalAccepted,
    dependencies=[Depends(declares_action(ManagementAction.IMPROVEMENT_PROPOSAL_DISMISS))],
)
async def dismiss_proposal(
    proposal_id: PROPOSAL_ID,
    payload: DismissalCreate,
    session: Annotated[Session, Depends(require_session)],
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ProposalAccepted:
    """INT-049. No thank you, with a reason. **The reason is required** and recorded.

    ``requires_reason`` is TRUE on this history action alone among the three. The
    dismissal rate per detector is what would retire a detector or a family, and a
    rate without reasons cannot tell *the detector is wrong* from *the remedy is
    wrong* — opposite fixes (OQ-157).

    Declared under ``prompt.edit`` rather than ``revision.create``: refusing a
    change is an editorial act on the prompt's record, and nothing is handed back
    that a person could apply.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        proposal = await repository.read_proposal(
            db, workspace_id=session.workspace_id, proposal_id=proposal_id
        )
        if proposal is None:
            raise _not_found()

        prompt = await _visible_prompt(db, session, proposal["prompt_id"])
        if not await may(db, _actor(session), Action.PROMPT_EDIT, _subject(prompt)):
            raise _forbidden(Action.PROMPT_EDIT)

        decided = await repository.decide_proposal(
            db,
            workspace_id=session.workspace_id,
            proposal_id=proposal_id,
            status=ProposalStatus.DISMISSED,
            actor_id=session.user_id,
        )
        if decided is None:
            raise _refused("proposal_already_decided")

        await _record_disposition(
            db,
            session=session,
            action="improvement_proposal_dismissed",
            proposal=proposal,
            reason=payload.reason,
        )

    proposals_total.labels(
        remedy_family=proposal["remedy_family"] or "note",
        disposition=str(ProposalStatus.DISMISSED),
    ).inc()
    proposals_open.dec()

    # No candidate body on a dismissal. Nothing was accepted, so there is nothing
    # to prefill, and returning one would put an unwanted edit on a clipboard.
    return ProposalAccepted(
        proposal_id=proposal_id,
        prompt_id=proposal["prompt_id"],
        remedy_family=proposal["remedy_family"],
    )


@router.get(
    "/workspaces/{workspace_id}/improvement-schedule",
    response_model=ScheduleRead,
    dependencies=[Depends(declares_action(ManagementAction.IMPROVEMENT_SCHEDULE_READ))],
)
async def read_schedule(
    workspace_id: WORKSPACE_ID,
    session: Annotated[Session, Depends(require_session)],
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ScheduleRead:
    """The current cadence. ``spend_ceiling.manage``, the same as the write.

    **The setting was write-only until this route existed**, which made the
    screen the lock asks for unbuildable: a toggle cannot render its own state
    from a PUT, and a client that guessed would show *off* to a workspace that
    had already turned it on — then charge it a second time when somebody
    "enabled" what was already enabled.

    A workspace with no row has never made the decision, and that is reported as
    the default rather than as a 404: *off, weekly, nothing selected* is a true
    description of a workspace that has not opted in, and a not-found here would
    make the screen distinguish *absent* from *disabled* for no reader's benefit.

    The path's ``workspace_id`` must match the session's, for ``write_schedule``'s
    reason and with the same refusal.
    """
    if workspace_id != session.workspace_id:
        raise _not_found()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        if not await may(
            db,
            _actor(session),
            Action.SPEND_CEILING_MANAGE,
            Subject(
                type=SubjectType.WORKSPACE,
                id=session.workspace_id,
                workspace_id=session.workspace_id,
            ),
        ):
            raise _forbidden(Action.SPEND_CEILING_MANAGE)

        row = await repository.read_schedule(db, workspace_id=session.workspace_id)

    if row is None:
        return ScheduleRead(
            enabled=False,
            cadence_days=DEFAULT_CADENCE_DAYS,
            namespaces=[],
            prompt_ids=[],
            last_run_at=None,
            updated_at=None,
        )

    return ScheduleRead(
        enabled=row["enabled"],
        cadence_days=row["cadence_days"],
        namespaces=list(row["namespaces"]),
        prompt_ids=list(row["prompt_ids"]),
        last_run_at=row["last_run_at"],
        updated_at=row["updated_at"],
    )


@router.put(
    "/workspaces/{workspace_id}/improvement-schedule",
    response_model=ScheduleRead,
    dependencies=[Depends(declares_action(ManagementAction.IMPROVEMENT_SCHEDULE_WRITE))],
)
async def write_schedule(
    workspace_id: WORKSPACE_ID,
    payload: ScheduleWrite,
    session: Annotated[Session, Depends(require_session)],
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> ScheduleRead:
    """INT-050. The re-probe cadence. ``spend_ceiling.manage``, because it is a charge.

    Enabling this commits the workspace to a recurring provider bill on its own
    credential. That is a spending decision before it is an authoring one, which
    is why it takes the permission that already governs the spend ceiling rather
    than ``prompt.edit`` — an author who can change a prompt should not thereby be
    able to start a weekly charge.

    The path's ``workspace_id`` must match the session's. It is in the path for
    the route table's sake and is not a way to reach another workspace: the
    tenant policy would answer zero rows anyway, and refusing here means the
    caller gets a refusal rather than a silently empty write.
    """
    if workspace_id != session.workspace_id:
        raise _not_found()

    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        if not await may(
            db,
            _actor(session),
            Action.SPEND_CEILING_MANAGE,
            Subject(
                type=SubjectType.WORKSPACE,
                id=session.workspace_id,
                workspace_id=session.workspace_id,
            ),
        ):
            raise _forbidden(Action.SPEND_CEILING_MANAGE)

        row = await repository.upsert_schedule(
            db,
            workspace_id=session.workspace_id,
            enabled=payload.enabled,
            cadence_days=payload.cadence_days,
            namespaces=payload.namespaces,
            prompt_ids=payload.prompt_ids,
            actor_id=session.user_id,
        )

    log.info(
        "improvement.schedule.written",
        enabled=payload.enabled,
        cadence_days=payload.cadence_days,
    )
    return ScheduleRead(
        enabled=row["enabled"],
        cadence_days=row["cadence_days"],
        namespaces=list(row["namespaces"]),
        prompt_ids=list(row["prompt_ids"]),
        last_run_at=row["last_run_at"],
        updated_at=row["updated_at"],
    )


async def _record_disposition(
    db: AsyncSession,
    *,
    session: Session,
    action: str,
    proposal: dict[str, Any],
    reason: str | None,
) -> None:
    """The trail. ``target_type='property'`` because the subject is the prompt.

    ``details`` carries the proposal id, the detector that raised it and the
    remedy family — and **not the candidate body**. A-124's allow-list is what
    enforces that: the three keys are registered in revision 0034 and anything
    else is refused by ``append`` rather than stored and regretted. History is
    append-only at the privilege level (ADR-0025), so a body written here could
    not be taken back out.
    """
    await append(
        db,
        HistoryEventDraft(
            workspace_id=session.workspace_id,
            actor_type=HistoryActorType.USER,
            actor_id=session.user_id,
            action=action,
            target_type="property",
            target_id=proposal["prompt_id"],
            scope_prompt_id=proposal["prompt_id"],
            reason=reason,
            occurred_at=datetime.now(UTC),
            details={
                "proposal_id": proposal["id"],
                "remedy_family": proposal["remedy_family"] or "",
            },
        ),
    )
