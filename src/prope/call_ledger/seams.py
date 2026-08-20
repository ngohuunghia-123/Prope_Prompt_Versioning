"""The three internal contracts evaluation will be written against. No caller yet.

``price_usage`` (INT-019), ``check_spend_ceiling`` (INT-020) and
``get_run_totals`` (INT-021) are registered seams whose one consumer — the
evaluation module — arrives in Phase 16/17. Nothing in this repository calls
them today. They are therefore proved from call-ledger's own tests, against the
real engine, rather than from a caller that could be shaped to agree with them.

**Two functions rather than one, because the two failure contracts are
opposite.** This is the load-bearing reason this file exists in this shape.

    enqueue      (INT-018)  NEVER raises into the caller. Ever. It is on the
                            gateway's response path and A-139 makes the p95
                            budget a property of the seam: a raise there is a
                            failed user request. It counts and drops.
    price_usage  (INT-019)  RAISES. Evaluation must be able to record a RUN
                            ERROR, because a run whose usage could not be priced
                            must not report a cost delta, and INT-021's counts
                            are how the review screen says so.

A single ``write_call_records(source=...)`` function would have to pick one of
those two and quietly break the other caller — and the breakage would be
invisible in both directions, because "returned normally" and "raised" are both
plausible-looking behaviour from the outside.

**``apis.exposes`` omits ``price_usage``, and it ships anyway.**
``docs/modules/call-ledger.lock.yml`` lists three internal seams and does not
name this one, while ``docs/architecture/interfaces.md`` registers it as INT-019
and the lock file's own ``inputs`` block cites INT-019 as evaluation's contract
with this module. The lock's list is treated as an **omission** rather than as
the authority (D-18), for the reason above: one function cannot hold both
failure contracts. The conflict is **raised as ``OQ-019``, not resolved by
patching the spec and not resolved by declining to ship the function** —
``.planning/BSP-LINK.md`` requires a spec that disagrees with the code to be
recorded as information rather than edited into agreement.

**Each seam opens its own transaction and never takes the caller's** (D-19).
property-history writes inside its caller's transaction (ADR-0023) and that
pattern is deliberately *not* copied here. Two reasons, and both are specific to
this module:

1. INT-019 requires that a raise leaves evaluation able to record a run error.
   Inside evaluation's transaction, the raise would have just rolled that
   transaction back, so the run error would have nowhere to be written.
2. call-ledger is a **sink**. Its whole design forbids reaching into a module
   that is doing work; holding a session belonging to the module that is
   mid-run is exactly that reach, in the one direction the module graph says
   must not exist.

**The same treatment for the second deviation.** ``get_run_totals`` ships as
``(workspace_id, run_id)`` where INT-021 registers ``run_id`` alone (D-20). The
reasoning is at the function; the conflict is raised as ``OQ-020`` against
``docs/architecture/interfaces.md``. Three deviations, three files, because each
blocks a different upstream field and a resolver can accept one without
accepting the others — ``OQ-018`` (``data.owns``) landed in plan 02-02.

**``get_run_totals`` is ROADMAP Phase 2's third success criterion and CL-11's
second clause, and this module does not tick CL-11.** That requirement's
``REQUIREMENTS.md`` row still reads Phase 1 / Pending, and the traceability
question — split the ID, remap the row across two phases, or accept a
permanently-pending Phase 1 row — is Phase 1 human-verification item 2 and is the
developer's to settle. Built here, claimed nowhere.

**The accepted cost, recorded rather than hidden.** An eval run's state change
and its usage write are now two transactions, and a crash between them is
possible: the usage rows can be committed while the run is still marked running,
or the run can advance with its usage unwritten. The retry is what fixes it, and
the retry is only safe once ``write_records`` upserts on ``call_id`` — that is
CL-02, in Phase 3. Until then a redelivered or retried batch meets a unique
violation, which is loud rather than silent, which is the correct failure mode
for a window this short.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.call_ledger.domain import CallRecordDraft, Outcome, Source
from prope.call_ledger.writer import period_month, write_records
from prope.db.session import workspace_transaction
from prope.observability import ceiling_check_total

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class EvalUsageRow:
    """One eval case's usage, as evaluation knows it, before it is priced.

    ``domain.CallRecordDraft``'s posture, narrowed to the one source this seam
    accepts. It carries no ``cost``, ``currency``, ``price_row_id`` or
    ``cost_status`` for the same reason that draft does not: those four are the
    writer's answer, and a caller able to supply them is a caller able to supply
    a zero. ``usage_status`` is likewise derived from whether the token counts
    are present.

    **There is no body field, and that is the point.** A-055 says no
    ``ledger.call_body`` row may ever exist for a ``source = 'eval'`` record.
    Plan 02-02 established — and asserted — that **no database constraint stands
    behind that rule**: a ``CHECK`` cannot reach another table, and the
    ``BEFORE INSERT`` trigger that could was refused on the cost of a per-row
    lookup on the highest-volume insert path in the system. So the guarantee
    holds exactly as far as ``write_records``' refusal reaches. The strongest
    thing this seam can add in front of it is to make an eval body
    **unrepresentable in its input type**, which is what the absence of a field
    here does. Eval outputs live on ``case_result``, which is evaluation's table.

    **``case_id`` is required, not optional.** The engine's
    ``ck_call_record_eval_calls_carry_run`` requires ``run_id`` AND ``case_id``
    AND a NULL ``consumer_key_id`` for an eval record. A caller that omits the
    case should meet a sentence naming the field it left out, at the moment it
    builds the value, rather than a constraint name it cannot act on arriving
    from the driver after a transaction has already opened. There is no
    ``consumer_key_id`` field at all, so the third clause of that constraint is
    satisfied by construction.

    **``version_id`` is required here and NOT by the engine, and the asymmetry
    is deliberate.** ``ck_call_record_gateway_calls_carry_version_id`` requires
    it only for ``source = 'gateway'``; eval records may carry a NULL version.
    Phase 2's own success criterion names ``version_id`` for an eval usage row —
    an eval result that cannot say which revision produced it is not evidence
    anybody can act on — so this model requires what the criterion requires and
    says out loud that the database does not.
    """

    call_id: str
    workspace_id: str
    run_id: str
    case_id: str
    version_id: str
    provider_config_id: str
    upstream_model: str
    outcome: Outcome
    created_at: datetime

    #: Both NULL together when the provider returned no usage object. Never a
    #: zero standing in for an absent count (BR-07, A-101, ADR-0019).
    input_tokens: int | None = None
    output_tokens: int | None = None

    def __post_init__(self) -> None:
        for name, reason in (
            (
                "case_id",
                "ck_call_record_eval_calls_carry_run requires run_id AND case_id AND a null "
                "consumer_key_id for an eval record, and a usage row that cannot say which case "
                "produced it is not evidence a reviewer can act on",
            ),
            (
                "run_id",
                "the same constraint requires it, and get_run_totals is keyed on it — a row "
                "without one would be written and then be unreachable from the only read path "
                "that exists for it",
            ),
            (
                "version_id",
                "Phase 2's success criterion names it for an eval usage row. The engine requires "
                "it only for source=gateway, so this is the model requiring what the criterion "
                "requires and not what the database enforces",
            ),
        ):
            if not getattr(self, name):
                raise ValueError(f"{self.call_id} has no {name}: {reason}")

        if self.created_at.tzinfo is None:
            raise ValueError(
                f"created_at for {self.call_id} is naive; a naive datetime is read against the "
                "server's time zone, which makes an effective-dated price depend on geography"
            )

        reported = (self.input_tokens is None, self.output_tokens is None)
        if reported[0] != reported[1]:
            raise ValueError(
                f"{self.call_id} reports one token count and not the other; usage is present or "
                "absent as a whole, and half of it is neither"
            )

    def to_draft(self) -> CallRecordDraft:
        """The one conversion, so ``price_usage`` builds no record inline.

        ``source`` is fixed to ``EVAL`` and ``body`` is left at its ``None``
        default — neither is a caller's choice, which is why neither is a field
        above.
        """
        return CallRecordDraft(
            call_id=self.call_id,
            workspace_id=self.workspace_id,
            source=Source.EVAL,
            outcome=self.outcome,
            created_at=self.created_at,
            version_id=self.version_id,
            run_id=self.run_id,
            case_id=self.case_id,
            provider_config_id=self.provider_config_id,
            upstream_model=self.upstream_model,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
        )


@dataclass(frozen=True, slots=True)
class ProbeUsageRow:
    """One probe case's usage, before it is priced. ADR-0067, revision 0032.

    ``EvalUsageRow``'s posture with the run replaced by the revision, and the
    differences are all forced by ``ck_call_record_probe_calls_name_no_run``.

    **There is no ``run_id`` field and no ``case_id`` field, and their absence is
    the type doing the work the constraint does.** A probe is not an eval run
    (ADR-0067 §3), so it may not name one — and ``run_id`` is what
    release-control's cost delta reads, which means a probe that carried one
    would put a convenience feature's bill inside the number comparing what two
    revisions cost to *serve*. A caller cannot make that mistake here because
    there is nowhere to make it.

    **There is no body field**, for ``EvalUsageRow``'s reason: a probe's inputs
    are the shipped catalogue and its outputs live on
    ``readiness.probe_case_result``, bounded and expiring. Nothing about a probe
    belongs in ``ledger.call_body``.

    **There is no ``consumer_key_id``** — a probe is started by a person holding
    ``probe.start`` over a session, not by a key — so the constraint's third
    clause is satisfied by construction.

    ``prompt_id`` and ``version_id`` are both required. The constraint requires
    them, and the reason it does is the whole justification for recording a probe
    at all: the spend has to be attributable to the revision that provoked it,
    or it is an unexplained line on a bill.
    """

    call_id: str
    workspace_id: str
    prompt_id: str
    version_id: str
    provider_config_id: str
    upstream_model: str
    outcome: Outcome
    created_at: datetime

    #: Both NULL together when the provider returned no usage object. Never a
    #: zero standing in for an absent count (BR-07, A-101, ADR-0019).
    input_tokens: int | None = None
    output_tokens: int | None = None

    def __post_init__(self) -> None:
        for name, reason in (
            (
                "prompt_id",
                "ck_call_record_probe_calls_name_no_run requires it, and a probe whose spend "
                "cannot be attributed to a prompt is an unexplained line on a bill",
            ),
            (
                "version_id",
                "the same constraint requires it. A probe measures ONE candidate revision, and "
                "a result that cannot say which one is not evidence a reviewer can act on",
            ),
        ):
            if not getattr(self, name):
                raise ValueError(f"{self.call_id} has no {name}: {reason}")

        if self.created_at.tzinfo is None:
            raise ValueError(
                f"created_at for {self.call_id} is naive; a naive datetime is read against the "
                "server's time zone, which makes an effective-dated price depend on geography"
            )

        reported = (self.input_tokens is None, self.output_tokens is None)
        if reported[0] != reported[1]:
            raise ValueError(
                f"{self.call_id} reports one token count and not the other; usage is present or "
                "absent as a whole, and half of it is neither"
            )

    def to_draft(self) -> CallRecordDraft:
        """The one conversion. ``source`` is fixed and is not a caller's choice."""
        return CallRecordDraft(
            call_id=self.call_id,
            workspace_id=self.workspace_id,
            source=Source.PROBE,
            outcome=self.outcome,
            created_at=self.created_at,
            prompt_id=self.prompt_id,
            version_id=self.version_id,
            provider_config_id=self.provider_config_id,
            upstream_model=self.upstream_model,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
        )


async def price_probe_usage(
    sessionmaker: async_sessionmaker[AsyncSession],
    usage_rows: Sequence[ProbeUsageRow],
) -> None:
    """Price and count one probe run's usage. Raises, or commits.

    ``price_usage``'s twin, minus the run. Takes a ``sessionmaker`` for the same
    reason (D-19): a seam that raised inside prompt-readiness's own transaction
    would take with it the ``probe_run`` row that records what happened, and a
    probe whose spend was recorded but whose result was lost is the worst of the
    available failures.

    **It writes no SQL of its own.** Every row goes through ``write_records``,
    where pricing at the record's own ``created_at``, the three cost states and
    the monthly aggregate live. One implementation, on purpose (ADR-0019).

    **prompt-readiness gains no read path into the ledger by calling this.**
    call-ledger is a sink and stays one; this is the write side, and the module's
    lock forbids the other one by name.
    """
    if not usage_rows:
        return

    workspaces = {row.workspace_id for row in usage_rows}
    if len(workspaces) > 1:
        raise ValueError(
            f"batch spans {len(workspaces)} workspaces {sorted(workspaces)}; ADR-0040 gives one "
            "transaction exactly one workspace, and a probe run belongs to one workspace, so "
            "this batch is refused whole rather than split behind the caller's back"
        )

    drafts = [row.to_draft() for row in usage_rows]
    workspace_id = usage_rows[0].workspace_id

    async with workspace_transaction(sessionmaker, workspace_id) as session:
        await write_records(session, drafts)


async def price_usage(
    sessionmaker: async_sessionmaker[AsyncSession],
    run_id: str,
    usage_rows: Sequence[EvalUsageRow],
) -> None:
    """INT-019. Price and count one eval run's usage. Raises, or commits.

    **The signature takes a ``sessionmaker``, never a session** (D-19). See this
    module's docstring for why: a seam that raises inside evaluation's own
    transaction would take with it the run-error row evaluation is required to
    write in response.

    **It writes no SQL of its own.** Every row is converted to a
    ``CallRecordDraft`` and handed to ``write_records``, which is where pricing
    at the record's own ``created_at``, the three cost states, the ``expires_at``
    stamp and the monthly aggregate live. There is one implementation of those on
    purpose (ADR-0019): a second statement here would be a second place for the
    eval path and the gateway path to drift, and the whole argument for one
    ``call_record`` table (A-098) is that they do not.

    Raises ``ValueError`` for a batch this seam cannot represent — a row
    belonging to another run, a batch spanning two workspaces — and re-raises
    whatever ``write_records`` and the engine raise. Every one of those leaves
    nothing written: the refusals below happen before a transaction opens, and
    the later ones roll back the transaction this function itself opened.
    """
    if not usage_rows:
        # A run with no cases is a run, not an error. Returning here also means
        # no transaction is opened for a batch that has nothing to write.
        return

    stray = sorted({row.run_id for row in usage_rows} - {run_id})
    if stray:
        raise ValueError(
            f"batch for run {run_id} carries rows belonging to {stray}; run_id is both this "
            "function's argument and a column, and the two disagreeing is invisible once "
            "written — get_run_totals would simply report one fewer case for the run the "
            "caller believes it wrote"
        )

    workspaces = {row.workspace_id for row in usage_rows}
    if len(workspaces) > 1:
        raise ValueError(
            f"batch spans {len(workspaces)} workspaces {sorted(workspaces)}; ADR-0040 gives one "
            "transaction exactly one workspace, and an eval run belongs to one workspace, so "
            "this batch is refused whole rather than split behind the caller's back"
        )

    # Built before the transaction opens, so a malformed row is refused without
    # a session, a tenant context or a round trip.
    drafts = [row.to_draft() for row in usage_rows]
    workspace_id = usage_rows[0].workspace_id

    async with workspace_transaction(sessionmaker, workspace_id) as session:
        await write_records(session, drafts)


class CeilingReason(StrEnum):
    """Why a run was refused. A machine ``code``, never a human sentence.

    ``domain.py``'s convention, for ``domain.py``'s reason: a status that is
    stored or transmitted is a **fact**, not a label, and it stays literal ASCII
    wherever it travels. ADR-0053 puts Vietnamese behind an i18n layer that
    translates a machine ``code`` at the API edge — the client renders the
    ``code``, not a ``message`` the server wrote — so a reason invented as an
    English sentence here would be a string the SPA could only display or
    discard.

    **The honest caveat, because this is a discretionary call.** ADR-0053 governs
    user-facing strings in the SPA and in the API envelope, and an in-process
    seam has no UI at all. This reason only becomes user-facing when evaluation
    surfaces it in Phase 17. Choosing a code *now*, before there is a screen to
    argue about, is what stops that phase inheriting an untranslatable English
    sentence from a function that had no locale to be wrong in.

    One member today. The per-run ceiling (``spend_ceiling.per_run_limit``) is
    also declared and also defaults off; whichever phase makes it a check adds
    its member here rather than reusing this one.
    """

    MONTHLY_CEILING_EXCEEDED = "monthly_ceiling_exceeded"


class CeilingCheckResult(StrEnum):
    """``ceiling_check_total``'s ``result`` label. Three values, and the set is closed.

    **It lives beside ``CeilingReason`` rather than in ``domain.py``** because
    ``domain.py`` holds the vocabularies the database has ``CHECK`` sets for, and
    no column carries this one. It is a metric label vocabulary: it leaves the
    process on a Prometheus series and nowhere else.

    ``enqueue._classify_publish_failure``'s discipline, one module over: **one
    place a value is chosen, so a fourth cannot appear by accident.** The
    alternative — four bare string literals repeated at four ``return`` sites — is
    how a typo becomes a fourth series that no alert reads and no test notices.

    **The three are mutually exclusive and jointly exhaustive over every path
    through** :func:`check_spend_ceiling`, and that is asserted rather than
    intended: ``tests/integration/test_ceiling_refuses_evals_only.py`` adds the
    three deltas across a single call and requires the sum to be exactly one.

    **``ALLOWED`` and ``FAILED_OPEN`` both return ``allowed=True``, which is why
    this is not a boolean.** A counter keyed off ``decision.allowed`` would fold
    the branch this whole control exists to watch into the ordinary one, and the
    fold would be invisible: the number would still rise, on the wrong label.
    """

    #: The ceiling was evaluated and the workspace may start the run — no row, a
    #: disabled row, a row with no monthly figure, no priced spend this month, or
    #: spend genuinely under the limit. All five are one answer.
    ALLOWED = "allowed"

    #: The ceiling was evaluated and the workspace may not. The only value that
    #: pairs with a ``CeilingReason``.
    REFUSED = "refused"

    #: The check could not be evaluated at all and allowed the run anyway
    #: (A-104, INT-020). ROADMAP SC3's *"failed-open counter"* is this label
    #: value, not a metric of its own — **a labelled counter is a counter**.
    FAILED_OPEN = "failed_open"


@dataclass(frozen=True, slots=True)
class CeilingDecision:
    """INT-020's whole return: ``allowed``, and why not. **Never a figure.**

    **This type has two fields and must never grow a third that carries a
    number** — not a spend, not a limit, not a remaining budget, not a
    percentage of the limit, not a currency code. A-056 makes the ceiling a
    boolean surface, and the reasoning is specific rather than general: there is
    no billing dashboard in the MVP, so the *only* place a workspace's billing
    position could surface is here — in front of somebody who is entitled to
    start eval runs and not necessarily entitled to see what the workspace
    spends. The refusal branch is where the leak would be added, because
    "you are $12.40 over your $200 limit" is a more helpful message and every
    part of it is the thing this type exists to withhold.

    ``docs/modules/call-ledger.lock.yml``'s ``test_plan.security`` requires the
    absence to be asserted under **every** branch including refused, which is why
    ``tests/integration/test_ceiling_refuses_evals_only.py`` searches the
    *serialized* decision and every captured log record for the workspace's
    actual figures rather than reading these two fields and believing them.
    """

    allowed: bool
    reason: CeilingReason | None = None


class _UnevaluableCeilingError(Exception):
    """The check has an answer-shaped input it cannot compare. Fails open, counted.

    Raised for the cases that are not database failures but are equally not
    decisions: a limit with no currency beside it, or a limit and a total
    denominated differently. A-107 forbids conversion, so comparing them would
    be comparing two numbers with different units — and a refusal computed from
    a figure that does not exist is worse than no refusal. It is an ``Exception``
    so that it takes exactly the same path as a database that would not answer,
    including the counter.
    """


#: One row, keyed on the two primary keys, joined rather than read twice so the
#: ceiling and the total come from a single consistent snapshot.
#:
#: **The aggregate is read; ``ledger.call_record`` is not touched.**
#: ``ledger.workspace_spend`` is maintained inside ``write_records``' own
#: transaction (A-103) for exactly this: a check that runs before every eval run
#: reads one row keyed ``(workspace_id, period_month)`` instead of aggregating
#: the largest and fastest-growing table in the system (T-02-25).
#:
#: The ``LEFT JOIN`` is load-bearing. A workspace with a ceiling row and no
#: traffic this month has no ``workspace_spend`` row at all, and an inner join
#: would return nothing — which this function would then have to read as "no
#: ceiling configured". The two are opposite states and they must not collapse.
#:
#: The tenant policy supplies the workspace restriction on both tables, exactly
#: as everywhere else in this module. The explicit predicate is bound and is
#: written alongside the policy rather than instead of it.
CEILING_READ = text(
    """
    SELECT ceiling.enabled,
           ceiling.monthly_limit,
           ceiling.currency  AS ceiling_currency,
           spend.total_cost,
           spend.currency    AS spend_currency
    FROM   ledger.spend_ceiling AS ceiling
    LEFT JOIN ledger.workspace_spend AS spend
           ON spend.workspace_id = ceiling.workspace_id
          AND spend.period_month = :period_month
    WHERE  ceiling.workspace_id = :workspace_id
    """
)


async def check_spend_ceiling(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspace_id: str,
    *,
    now: datetime,
) -> CeilingDecision:
    """INT-020. May this workspace start an eval run? Yes, or no and why.

    **Checked once, before a run's first dispatch** — never per case, and never
    by call-ledger during a call. A run that starts under the ceiling and crosses
    it mid-run finishes.

    **Ceilings refuse eval runs and never gateway traffic** (A-029). Nothing in
    this function is on the gateway path, and nothing on the gateway path calls
    it. Both ceilings default off, and "off" here has three shapes that all mean
    the same thing: no row, ``enabled`` false, or a NULL ``monthly_limit``.

    **The clock is passed in, never read**, matching ``retention.py``'s rule —
    and the month is derived with ``writer.period_month``, the shared helper,
    rather than re-derived here. That sharing is the whole of Pitfall 8:
    ``write_records`` files a record under the record's own ``created_at`` in
    UTC; this function has no record and must pick a month itself. If one read a
    local-time month while the other filed by UTC, the two would disagree for up
    to a day at every month boundary, and the disagreement would be invisible
    because both sides would be internally consistent and simply looking at
    different rows. AC-6's phrasing — "a workspace whose gateway traffic alone
    has already exceeded its monthly ceiling" — is only testable if both sides
    file into the same month.

    **This is the one seam in Prope that fails OPEN** (A-104, INT-020). A check
    that cannot be evaluated returns ``allowed`` and counts itself on
    ``prope_call_ledger_ceiling_check_total{result="failed_open"}``; it does not
    raise into evaluation. The trade is stated rather than assumed: the ceiling
    guards an optional, off-by-default feature, and blocking a reviewer's
    evidence over a billing lookup is the worse outcome. **The counter is the
    control**, because an open-failing check nobody watches is an off switch.

    **CL-07 is claimed here, and it is claimed by counting all three branches
    rather than by renaming a constant.** Phase 2 shipped the branch and recorded
    at this very paragraph that the claim was not its own. The requirement's own
    words are *a spend-ceiling check that cannot be evaluated returns allowed,
    counts the failure, and never raises into evaluation* — three clauses, and all
    three are asserted in
    ``tests/integration/test_ceiling_refuses_evals_only.py``. What made the claim
    unavailable in Phase 2 was not the branch but the metric: the declared counter
    is ``ceiling_check_total`` labelled ``result = allowed | refused |
    failed_open``, which counts **every** check, and only the open one had an
    increment site. ``allowed`` and ``refused`` gained theirs here, which is the
    actual work; Phase 2's separate fail-open counter is retired rather than kept
    beside it, for the reason written in ``observability.py`` where it used to be
    defined.

    **Say the corollary out loud.** ROADMAP SC3 reads *"increments the failed-open
    counter"*, and a reader may go looking for the retired constant. **A labelled
    counter is a counter** — ``ceiling_check_total{result="failed_open"}`` is the
    failed-open counter, under the name the spec declares.

    **The increment sits beside each ``return``, never once at the end.**
    ``allowed`` is ``True`` on two different branches — the workspace was under
    its ceiling, and the check blew up — so a single site keyed off
    ``decision.allowed`` could not tell them apart, and ``failed_open`` is the
    value the whole control exists for. Exactly one of the three fires per call,
    and the test adds the three deltas to prove it.
    """
    month = period_month(now)

    try:
        async with workspace_transaction(sessionmaker, workspace_id) as session:
            row = (
                (
                    await session.execute(
                        CEILING_READ, {"workspace_id": workspace_id, "period_month": month}
                    )
                )
                .mappings()
                .first()
            )

        if row is None or not row["enabled"] or row["monthly_limit"] is None:
            # No ceiling configured for this workspace, or one that is switched
            # off, or one with no monthly figure. All three are "off" (A-029).
            ceiling_check_total.labels(result=CeilingCheckResult.ALLOWED).inc()
            return CeilingDecision(allowed=True)

        if row["total_cost"] is None:
            # A ceiling exists and nothing priced has landed this month. Not a
            # zero total — a total that does not exist yet — and either way the
            # workspace is under any positive limit.
            ceiling_check_total.labels(result=CeilingCheckResult.ALLOWED).inc()
            return CeilingDecision(allowed=True)

        if row["ceiling_currency"] is None or row["ceiling_currency"] != row["spend_currency"]:
            raise _UnevaluableCeilingError

        # ``>=`` rather than ``>``. INT-020's own words are "a run that starts
        # UNDER the ceiling ... finishes", and at exactly the limit a workspace
        # is not under it. Allowing there would guarantee crossing, because every
        # run costs money and ``ck_call_record_cost_is_never_zero`` says no
        # priced call costs nothing.
        if row["total_cost"] >= row["monthly_limit"]:
            log.info(
                "call_ledger.ceiling_refused",
                workspace_id=workspace_id,
                reason=str(CeilingReason.MONTHLY_CEILING_EXCEEDED),
            )
            # The counter counts the BRANCH and carries no figure — no spend, no
            # limit, no remainder, no currency code. That is what makes the
            # ceiling observable while ``CeilingDecision`` keeps exactly two
            # fields (A-056), and it matters most on this branch: "you are $12.40
            # over your $200 limit" is the helpful message the type exists to
            # withhold, and a label is the next place it would be written.
            #
            # After the log rather than before it, so that a logging call which
            # somehow raised takes the fail-open path alone and this branch cannot
            # contribute a second increment to the same call.
            ceiling_check_total.labels(result=CeilingCheckResult.REFUSED).inc()
            return CeilingDecision(
                allowed=False, reason=CeilingReason.MONTHLY_CEILING_EXCEEDED
            )

        ceiling_check_total.labels(result=CeilingCheckResult.ALLOWED).inc()
        return CeilingDecision(allowed=True)

    except Exception as error:
        # Deliberately broad, and deliberately not re-raising. ``Exception``
        # rather than ``BaseException`` leaves ``asyncio.CancelledError`` alone,
        # so a shutdown still cancels this task instead of being counted as a
        # billing-lookup failure.
        #
        # A-046: the exception's CLASS, never its message, which at this depth
        # can quote a row, a connection string or a figure.
        #
        # This is the branch CL-07 is about, and the counter is the whole of the
        # mitigation — the branch itself is contractual and is not the thing being
        # controlled. Each of the four returns above increments immediately before
        # returning, so a call that reached one of them cannot also reach this.
        ceiling_check_total.labels(result=CeilingCheckResult.FAILED_OPEN).inc()
        log.warning(
            "call_ledger.ceiling_failed_open",
            workspace_id=workspace_id,
            reason=type(error).__name__,
        )
        return CeilingDecision(allowed=True)


@dataclass(frozen=True, slots=True)
class RunTotals:
    """INT-021's six fields. ``domain.WriteResult``'s posture, one table further on.

    The docstring says what each field is derived **from**, not what it means,
    because what it means is evaluation's to decide and what it is derived from
    is what makes two implementations agree.

    ``input_tokens`` / ``output_tokens``  ``sum`` over the token columns of every
    record carrying this ``run_id``. Records whose provider returned no usage
    object contribute nothing, because both their token columns are NULL — never
    a zero (``ck_call_record_unknown_usage_is_null``).

    ``cost`` / ``currency``  ``sum`` over ``cost``, which is non-NULL only for
    ``cost_status = 'priced'``. ``currency`` is the one currency the priced rows
    carry; a run carrying two is refused rather than summed. **``cost`` is
    ``None``, not zero, for a run with nothing priced.** A zero beside a NULL
    currency is a number with no unit — the exact shape
    ``ck_workspace_spend_total_cost_carries_currency`` refuses one table over —
    and it would make "this run cost nothing" indistinguishable from "nothing in
    this run was priced", which is the distinction the two counts exist to keep.

    ``unpriced_count``  ``count(*) FILTER (WHERE cost_status = 'unpriced')``.

    ``unknown_usage_count``  ``count(*) FILTER (WHERE usage_status = 'unknown')``
    — the same number ``WriteResult.unknown`` reports for the same rows, derived
    the same way, which is what that field's docstring promised Phase 2 would do.

    **The two counts are part of the answer, not diagnostics** (INT-021). A delta
    computed over a partly unpriced run is not a delta, and evaluation withholds
    it rather than publishing a smaller number that looks like a cheaper
    revision. They do not overlap: an unknown-usage record carries
    ``cost_status = 'not_applicable'``, so it is counted by the second filter and
    never by the first, and neither count is derivable from the other.
    """

    input_tokens: int
    output_tokens: int
    cost: Decimal | None
    currency: str | None
    unpriced_count: int
    unknown_usage_count: int


#: One projection over the stored encoding, in ``writer.UNPRICED_WORKLIST``'s
#: shape. Served by ``ix_call_record_workspace_id_run_id``, the partial index
#: Phase 1 added with a comment naming this phase — **and whose leading column is
#: ``workspace_id``**, which is the mechanical half of D-20's argument.
#:
#: The two counts filter two DIFFERENT columns and the asymmetry is not smoothed
#: over: ``unpriced_count`` filters ``cost_status`` and ``unknown_usage_count``
#: filters ``usage_status``. A record whose provider returned no usage object
#: carries ``cost_status = 'not_applicable'``, so it appears in the second count
#: and never in the first — the two are disjoint, and neither can be computed
#: from the other or from the token columns.
#:
#: ``array_agg(DISTINCT currency)`` rather than ``min``/``max``: a run carrying
#: three currencies should be refused with three names in the message, not two.
#: The ``FILTER`` drops the NULLs that unpriced and not-applicable rows carry, so
#: an ordinary partly-unpriced run does not look like a currency conflict.
#:
#: The tenant policy supplies the workspace restriction, so there is no
#: ``workspace_id`` predicate to forget — and a ``run_id`` belonging to another
#: workspace returns zero rows rather than that workspace's figures.
RUN_TOTALS = text(
    """
    SELECT coalesce(sum(input_tokens), 0)   AS input_tokens,
           coalesce(sum(output_tokens), 0)  AS output_tokens,
           sum(cost)                        AS cost,
           array_agg(DISTINCT currency) FILTER (WHERE currency IS NOT NULL) AS currencies,
           count(*) FILTER (WHERE cost_status = 'unpriced')  AS unpriced_count,
           count(*) FILTER (WHERE usage_status = 'unknown')  AS unknown_usage_count
    FROM   ledger.call_record
    WHERE  run_id = :run_id
    """
)


async def get_run_totals(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspace_id: str,
    run_id: str,
) -> RunTotals:
    """INT-021. One run's tokens, cost, and the two counts that qualify them.

    **The signature takes the workspace, and INT-021 registers a one-argument
    form** (D-20). The reason is RLS, and it is structural rather than stylistic:
    with D-19's own-transaction shape this function must set a tenant before any
    read, and a ``run_id`` alone cannot supply one — the lookup that would
    resolve the workspace *from* the run is itself a read, and under ADR-0045 a
    read with no tenant set returns **zero rows**, so it would resolve nothing,
    forever, silently. The caller passes the workspace it already holds, which is
    ``check_spend_ceiling``'s posture and the rule access-control lives by:
    callers supply the subject.

    **A fifth ``SECURITY DEFINER`` resolver is refused.** Exactly four are
    sanctioned and a test asserts the set is those four. That refusal is the
    whole of why this argument exists.

    The corroboration is in the schema: Phase 1's
    ``ix_call_record_workspace_id_run_id`` leads with ``workspace_id``, and the
    one-argument form could not have used it.

    **This function is ROADMAP Phase 2's third success criterion and CL-11's
    second clause, and it does not tick CL-11.** That requirement's
    ``REQUIREMENTS.md`` row still reads Phase 1 / Pending, and the traceability
    question — split the ID, remap the row to both phases, or accept a
    permanently-pending Phase 1 row — is Phase 1 human-verification item 2 and is
    the developer's to settle. Built here; not claimed here.

    Raises ``ValueError`` for a run whose rows carry two currencies. INT-021's
    declared failure semantics are raises -> a run error at evaluation, and no
    delta.
    """
    async with workspace_transaction(sessionmaker, workspace_id) as session:
        row = (
            (await session.execute(RUN_TOTALS, {"run_id": run_id})).mappings().one()
        )

    currencies = sorted(row["currencies"] or ())
    if len(currencies) > 1:
        # Neither alternative answer is true, and that is why this raises.
        #
        # A SUM across two currencies is a number with no unit — A-107 forbids
        # conversion, and an exchange rate would be a second effective-dated
        # table nobody has agreed to maintain.
        #
        # A NULL cost would be worse than useless here: it would make "two
        # currencies" indistinguishable from "nothing priced" to the review
        # screen, and telling those two apart is precisely what INT-021 says the
        # counts exist for.
        raise ValueError(
            f"run {run_id} has costs recorded in {', '.join(currencies)}; A-107 forbids "
            "conversion, so a sum across them would be a number with no unit — and a null "
            "cost would make this indistinguishable from a run with nothing priced. "
            "write_records refuses a mixed-currency batch, so this run was written in two "
            "batches with a price row's currency changing in between"
        )

    return RunTotals(
        input_tokens=int(row["input_tokens"]),
        output_tokens=int(row["output_tokens"]),
        cost=row["cost"],
        currency=currencies[0] if currencies else None,
        unpriced_count=int(row["unpriced_count"]),
        unknown_usage_count=int(row["unknown_usage_count"]),
    )


# ---------------------------------------------------------------------------
# INT-031 — one prompt's call metadata, read
# ---------------------------------------------------------------------------

#: A-045's page size, and the ceiling a caller may ask for. Restated rather than
#: imported from `prompt_registry.repository`: the numbers are A-045's, and this
#: module may not import the one that will call it.
CALL_RECORD_PAGE_LIMIT = 50
CALL_RECORD_MAX_LIMIT = 200

#: **Metadata only. Not one column of `ledger.call_body` appears here, and none
#: ever may** (ADR-0018). That ADR forbids a read path for *bodies* and says of
#: the rest, in as many words: *"Metadata is unaffected. It is kept indefinitely,
#: it has readers, and it is the audit trail NFR-02 requires."* This is one of
#: those readers. `tests/security/test_no_body_read_path.py` asserts the
#: distinction structurally rather than trusting this comment.
#:
#: **`actor_id` is deliberately absent.** It names the *person* who made a call,
#: which is a fact about somebody's working day rather than about the prompt, and
#: nothing on the screen this feeds needs it. `consumer_key_id` is what a reader
#: is actually asking about — *which integration is calling this* — and it names a
#: key rather than a person.
#:
#: The keyset compares `(created_at, call_id)` as a **row value** against the
#: cursor row's own pair. Ordering by `created_at` alone would page unstably the
#: moment two records shared a millisecond: one would appear on both pages and the
#: other on neither. The subquery resolves the cursor under the same tenant
#: policy as the outer read, so a `call_id` from another workspace resolves to
#: nothing and the page simply starts at the beginning rather than leaking that
#: the id exists.
#:
#: **The four filters are here rather than in the caller, because a filter
#: applied after paging is a lie.** The keyset returns one page; a client that
#: dropped rows from that page would show "3 results" for a prompt with three
#: thousand, and the next page would drop a different number. Each is written as
#: `param IS NULL OR column = param` so one prepared statement serves every
#: combination, and `since` stays a range predicate on `created_at` — the third
#: column of `ix_call_record_workspace_id_prompt_id_created_at`, so the window
#: narrows the scan instead of forcing a sort.
LIST_PROMPT_CALL_RECORDS = text(
    """
    SELECT call_id, source, version_id, revision_number, consumer_key_id,
           provider_config_id, upstream_model, outcome, pinned, fallback, streaming,
           input_tokens, output_tokens, usage_status, cost, currency, cost_status,
           added_latency_ms, upstream_duration_ms, error_class, created_at
    FROM   ledger.call_record
    WHERE  prompt_id = :prompt_id
      AND  (CAST(:source AS text) IS NULL OR source = CAST(:source AS text))
      AND  (CAST(:outcome AS text) IS NULL OR outcome = CAST(:outcome AS text))
      AND  (CAST(:version_id AS text) IS NULL OR version_id = CAST(:version_id AS text))
      AND  (CAST(:since AS timestamptz) IS NULL OR created_at >= CAST(:since AS timestamptz))
      AND  (CAST(:cursor AS text) IS NULL
            OR (created_at, call_id) < (
                   SELECT created_at, call_id
                   FROM   ledger.call_record
                   WHERE  call_id = CAST(:cursor AS text)
               ))
    ORDER  BY created_at DESC, call_id DESC
    LIMIT  :limit
    """
)


@dataclass(frozen=True, slots=True)
class CallRecordListing:
    """One call's metadata, as a reader with `prompt.read` may see it.

    **No body, and no field that could carry one.** The type is the boundary: a
    caller cannot ask this seam for a request or a response because there is
    nowhere in the return value to put one.
    """

    call_id: str
    source: str
    version_id: str | None
    revision_number: int | None
    consumer_key_id: str | None
    provider_config_id: str | None
    upstream_model: str | None
    outcome: str
    pinned: bool
    fallback: bool
    streaming: bool
    input_tokens: int | None
    output_tokens: int | None
    usage_status: str
    cost: Decimal | None
    currency: str | None
    cost_status: str
    added_latency_ms: int | None
    upstream_duration_ms: int | None
    error_class: str | None
    created_at: datetime


async def list_prompt_call_records(
    db: AsyncSession,
    prompt_id: str,
    *,
    cursor: str | None = None,
    limit: int = CALL_RECORD_PAGE_LIMIT,
    source: str | None = None,
    outcome: str | None = None,
    version_id: str | None = None,
    since: datetime | None = None,
) -> tuple[CallRecordListing, ...]:
    """INT-031. One prompt's call metadata, newest first, on the caller's transaction.

    **This seam performs no permission check and must never grow one.** ADR-0018
    makes call-ledger a sink: it has no edge to access-control and therefore no
    way to ask `may()` anything, and giving it a second copy of "who may see this"
    is the failure that ADR rejected outright. So the check happens in the module
    that calls this — prompt-registry, which has already loaded the prompt row and
    authorised `prompt.read` against it before reaching here.

    **That placement is what keeps BR-01 intact.** A workspace-wide call-record
    list would name `prompt_id`s, which tells a reader that a private prompt
    exists — the disclosure prompts-are-private-by-default closes as not-found,
    arriving through a door nobody thought of as a read. Scoping the read to one
    prompt whose visibility has already been decided means there is no such door.

    **It takes the caller's `db` rather than a sessionmaker**, unlike the three
    seams above it. Those three write, or are called from `worker` where there is
    no ambient transaction, so each owns its boundary. This one is called from a
    route that has already opened a `workspace_transaction` to authorise — and
    reading the authorisation and the rows under one snapshot is strictly better
    than reading them under two. It is `property_history.read`'s shape, which
    prompt-registry's Activity route already uses for the same reason.

    The tenant policy supplies the workspace restriction, so there is no
    `workspace_id` predicate to forget — and a `prompt_id` belonging to another
    workspace returns zero rows rather than that workspace's traffic.
    """
    if not 1 <= limit <= CALL_RECORD_MAX_LIMIT:
        raise ValueError(f"limit={limit} is outside A-045's bound of 1..{CALL_RECORD_MAX_LIMIT}")

    rows = (
        (
            await db.execute(
                LIST_PROMPT_CALL_RECORDS,
                {
                    "prompt_id": prompt_id,
                    "cursor": cursor,
                    "limit": limit,
                    "source": source,
                    "outcome": outcome,
                    "version_id": version_id,
                    "since": since,
                },
            )
        )
        .mappings()
        .all()
    )
    return tuple(CallRecordListing(**dict(row)) for row in rows)


# ---------------------------------------------------------------------------
# One prompt's traffic, rolled up per calling integration
# ---------------------------------------------------------------------------

#: Grouped by `(consumer_key_id, currency)` and **not** by key alone, because a
#: prompt served by a USD provider and a VND provider has two costs and no total.
#:
#: `get_run_totals` raises on a mixed-currency run, and that is right for a *run*:
#: one run is one dispatch of one suite, so two currencies there mean something
#: went wrong and a review screen must not paper over it. A *prompt* is different
#: — thirty days of traffic legitimately spans a provider change, and refusing to
#: render the tab because of it would be the tool breaking over a fact about the
#: workspace. So the grouping keeps them apart and the caller reports both, which
#: is the only honest answer A-107 leaves available.
#:
#: The unpriced rows carry `currency IS NULL` and therefore land in their own
#: group. That is why the caller folds groups back together per key rather than
#: rendering one row each: `requests` must count the call whether or not anybody
#: could price it, and `unpriced_count` is what says how much of the cost column
#: to believe.
#:
#: `error_count` is `caller_error` + `upstream_error`. `truncated` is deliberately
#: not in it: the provider generated tokens and charged for them, so it is a
#: **cost** event rather than a failure, and folding it into an error rate would
#: make the two indistinguishable on the one screen where the difference decides
#: whether you change the prompt or change `max_tokens`.
AGGREGATE_PROMPT_USAGE = text(
    """
    SELECT consumer_key_id,
           currency,
           count(*)                         AS requests,
           coalesce(sum(input_tokens), 0)   AS input_tokens,
           coalesce(sum(output_tokens), 0)  AS output_tokens,
           sum(cost)                        AS cost,
           count(*) FILTER (WHERE cost_status = 'unpriced')                  AS unpriced_count,
           count(*) FILTER (WHERE outcome IN ('caller_error','upstream_error')) AS error_count,
           count(*) FILTER (WHERE outcome = 'fallback')                      AS fallback_count,
           max(created_at)                  AS last_called_at
    FROM   ledger.call_record
    WHERE  prompt_id = :prompt_id
      AND  (CAST(:source AS text) IS NULL OR source = CAST(:source AS text))
      AND  (CAST(:since AS timestamptz) IS NULL OR created_at >= CAST(:since AS timestamptz))
    GROUP  BY consumer_key_id, currency
    """
)


@dataclass(frozen=True, slots=True)
class UsageBucket:
    """What one calling integration did to one prompt, over one window.

    **`consumer_key_id` and never `actor_id`.** The question this answers is
    *which product is calling us*, and the answer is a key. A `None` here is the
    internal caller, which today means a **playground trial**: it authenticates
    with a session and `ck_call_record_playground_calls_are_internal` refuses it
    a key outright. The caller labels the bucket rather than dropping it, because
    a cost total that omitted a person's own turns would not reconcile with what
    the workspace spent on the prompt.

    **Eval dispatches are not in it, and the reason is upstream of this query.**
    `EvalUsageRow.to_draft` writes `version_id`, `run_id` and `case_id` and
    leaves `prompt_id` null, so an eval record never matches a per-prompt
    predicate — here or in `list_prompt_call_records`. That is a gap in the write
    path rather than a decision taken here; until it is closed, eval spend is
    reported from `evaluation.eval_run`'s own priced totals, which is the more
    precise source for it anyway because it is per run rather than per call.

    `cost` is a tuple of `(currency, amount)` pairs, empty when nothing in the
    bucket could be priced. Never a single number with a nullable currency beside
    it: that shape has no way to say "USD 0.41 and VND 12,000" and would force
    either a conversion A-107 forbids or a silent drop.
    """

    consumer_key_id: str | None
    requests: int
    input_tokens: int
    output_tokens: int
    cost: tuple[tuple[str, Decimal], ...]
    unpriced_count: int
    error_count: int
    fallback_count: int
    last_called_at: datetime | None


@dataclass(slots=True)
class _UsageAccumulator:
    """The mutable half of the fold, so `UsageBucket` can stay frozen.

    One instance per `consumer_key_id`, absorbing that key's per-currency rows.
    """

    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    unpriced_count: int = 0
    error_count: int = 0
    fallback_count: int = 0
    last_called_at: datetime | None = None
    cost: dict[str, Decimal] = field(default_factory=dict)

    def absorb(self, row: Mapping[str, Any]) -> None:
        self.requests += int(row["requests"])
        self.input_tokens += int(row["input_tokens"])
        self.output_tokens += int(row["output_tokens"])
        self.unpriced_count += int(row["unpriced_count"])
        self.error_count += int(row["error_count"])
        self.fallback_count += int(row["fallback_count"])

        # Both guards are load-bearing rather than defensive: an unpriced row
        # carries a NULL in each, and adding it under a NULL currency key would
        # invent a currency named "None".
        if row["currency"] is not None and row["cost"] is not None:
            currency = str(row["currency"])
            self.cost[currency] = self.cost.get(currency, Decimal(0)) + row["cost"]

        seen = row["last_called_at"]
        if seen is not None and (self.last_called_at is None or seen > self.last_called_at):
            self.last_called_at = seen

    def freeze(self, consumer_key_id: str | None) -> UsageBucket:
        return UsageBucket(
            consumer_key_id=consumer_key_id,
            requests=self.requests,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cost=tuple(sorted(self.cost.items())),
            unpriced_count=self.unpriced_count,
            error_count=self.error_count,
            fallback_count=self.fallback_count,
            last_called_at=self.last_called_at,
        )


async def aggregate_prompt_usage(
    db: AsyncSession,
    prompt_id: str,
    *,
    since: datetime | None = None,
    source: str | None = None,
) -> tuple[UsageBucket, ...]:
    """One prompt's traffic, one bucket per calling integration, newest-busiest first.

    **This seam performs no permission check and must never grow one**, for the
    same reason `list_prompt_call_records` above does not: ADR-0018 leaves
    call-ledger without an edge to access-control, so it cannot ask `may()`
    anything, and a second copy of "who may see this" is the failure that ADR
    rejected. The caller — prompt-registry — has already loaded the prompt row and
    authorised `prompt.read` against it.

    **It resolves no key names either, and that is the same rule seen from the
    other side.** `access.api_key` belongs to access-control; a join to it from
    here would be call-ledger reaching out, which is the one direction the module
    graph forbids. The bucket carries the id; the caller, which may import
    access-control, turns it into a label.

    Takes the caller's `db` rather than a sessionmaker, so the authorisation and
    the rollup are read under one snapshot.

    The tenant policy supplies the workspace restriction, so there is no
    `workspace_id` predicate to forget.
    """
    rows = (
        (
            await db.execute(
                AGGREGATE_PROMPT_USAGE,
                {"prompt_id": prompt_id, "since": since, "source": source},
            )
        )
        .mappings()
        .all()
    )

    folded: dict[str | None, _UsageAccumulator] = {}
    for row in rows:
        folded.setdefault(row["consumer_key_id"], _UsageAccumulator()).absorb(row)

    return tuple(
        sorted(
            (accumulator.freeze(key_id) for key_id, accumulator in folded.items()),
            key=lambda bucket: (-bucket.requests, bucket.consumer_key_id or ""),
        )
    )


# ---------------------------------------------------------------------------
# One conversation, as a chain of calls
# ---------------------------------------------------------------------------

#: A-045 again, and the same numbers. A conversation is a handful of calls, so
#: the graph read is not paged at all — see `read_conversation_calls` for why a
#: cap is used instead of a cursor.
CONVERSATION_PAGE_LIMIT = 50
CONVERSATION_MAX_LIMIT = 200

#: The ceiling on nodes in one graph. A conversation with more calls than this is
#: not a conversation anybody can read as a picture; it is a load test, or an app
#: reusing one `conversation_id` for its whole lifetime. Both are real, and both
#: are answered by truncating and **saying so** — the caller reports truncation
#: explicitly, because a graph that silently showed the first two hundred of nine
#: thousand calls would be a lie of exactly the kind this feature exists to avoid.
CONVERSATION_NODE_CAP = 200

#: The conversations this prompt took part in, newest activity first.
#:
#: **Grouped, so one row is one conversation rather than one call.** The counts
#: come from the same rows `LIST_PROMPT_CALL_RECORDS` would return; what differs
#: is that a reader looking for *a chain that went wrong* wants to scan
#: conversations, not calls, and a per-call list buries a five-call conversation
#: under a thousand-call one.
#:
#: **No cost column, deliberately.** A conversation legitimately spans a provider
#: change, so its calls can carry two currencies, and A-107 leaves no conversion.
#: `aggregate_prompt_usage` answers that by grouping on currency and letting the
#: caller report both; a *list* row has no room for two totals, and one total
#: across two currencies is a number with no unit. Cost lives on the node detail,
#: where each call carries its own currency.
#:
#: **The inner `mine` CTE finds the conversations, the outer aggregate counts
#: them whole.** Rolling up only the rows that name `:prompt_id` would report
#: `call_count` as this prompt's share rather than the conversation's length,
#: which is the number a reader is actually scanning for.
#:
#: The keyset compares `(last_called_at, conversation_id)` as a row value against
#: the cursor conversation's own pair, resolved in a subquery under the same
#: tenant policy — so a `conversation_id` from another workspace resolves to
#: nothing and the page starts at the beginning rather than revealing that the id
#: exists somewhere.
LIST_PROMPT_CONVERSATIONS = text(
    """
    WITH mine AS (
        SELECT conversation_id
        FROM   ledger.call_record
        WHERE  prompt_id = :prompt_id
          AND  conversation_id IS NOT NULL
          AND  (CAST(:since AS timestamptz) IS NULL
                OR created_at >= CAST(:since AS timestamptz))
        GROUP  BY conversation_id
    ),
    rolled AS (
        SELECT r.conversation_id,
               min(r.created_at)                               AS started_at,
               max(r.created_at)                               AS last_called_at,
               count(*)                                        AS call_count,
               count(DISTINCT r.prompt_id)                     AS prompt_count,
               count(*) FILTER (
                   WHERE r.outcome IN ('caller_error','upstream_error')
               )                                               AS error_count,
               count(*) FILTER (WHERE r.outcome = 'fallback')  AS fallback_count
        FROM   ledger.call_record r
        JOIN   mine ON mine.conversation_id = r.conversation_id
        GROUP  BY r.conversation_id
    )
    SELECT conversation_id, started_at, last_called_at, call_count,
           prompt_count, error_count, fallback_count
    FROM   rolled
    WHERE  CAST(:cursor AS text) IS NULL
       OR (last_called_at, conversation_id) < (
              SELECT max(created_at), CAST(:cursor AS text)
              FROM   ledger.call_record
              WHERE  conversation_id = CAST(:cursor AS text)
          )
    ORDER  BY last_called_at DESC, conversation_id DESC
    LIMIT  :limit
    """
)

#: Every call in one conversation, oldest first — the graph's nodes.
#:
#: **The `EXISTS` clause is the authorisation, not a filter.** The route
#: authorises `prompt.read` on `:prompt_id` and nothing else; without this
#: predicate, naming any prompt you may read alongside any `conversation_id` you
#: could guess would return that conversation entire. So the conversation must
#: demonstrably involve the prompt whose visibility was checked. It is written as
#: `EXISTS` rather than as a join so that it gates the read without filtering the
#: rows — the whole chain is returned, including its other prompts, which the
#: caller then filters by visibility one prompt at a time.
#:
#: **`prompt_id` is in the projection here and absent from
#: `LIST_PROMPT_CALL_RECORDS`, and that is not an inconsistency.** There, every
#: row was the one prompt the caller named, so repeating it would have been
#: noise. Here the rows span prompts by construction, and the caller cannot apply
#: ADR-0020's visibility rule to a row whose subject it cannot identify.
#:
#: Ordered `(created_at, call_id)` ascending as a row value: a fan-out to
#: parallel sub-agents routinely lands two calls in one millisecond, and a
#: `created_at`-only sort would render those two in an order that changed between
#: reads.
READ_CONVERSATION_CALLS = text(
    """
    SELECT call_id, parent_call_id, prompt_id, source, version_id, revision_number,
           consumer_key_id, provider_config_id, upstream_model, outcome, pinned,
           fallback, streaming, input_tokens, output_tokens, usage_status, cost,
           currency, cost_status, added_latency_ms, upstream_duration_ms,
           error_class, created_at
    FROM   ledger.call_record
    WHERE  conversation_id = :conversation_id
      AND  EXISTS (
               SELECT 1
               FROM   ledger.call_record witness
               WHERE  witness.conversation_id = :conversation_id
                 AND  witness.prompt_id = :prompt_id
           )
    ORDER  BY created_at ASC, call_id ASC
    LIMIT  :limit
    """
)


@dataclass(frozen=True, slots=True)
class ConversationListing:
    """One conversation, rolled up — what a reader scans before opening a graph."""

    conversation_id: str
    started_at: datetime
    last_called_at: datetime
    call_count: int
    prompt_count: int
    error_count: int
    fallback_count: int


@dataclass(frozen=True, slots=True)
class ConversationCall:
    """One call in a conversation: a node, and the edge back to its parent.

    `CallRecordListing` plus `prompt_id` and `parent_call_id`, and **no body and
    no field that could carry one** — ADR-0018 applies here exactly as it applies
    there, and the type is again the boundary. The point of this feature is the
    *shape* of a chain; the shape is metadata, and the content stays where it has
    no reader.
    """

    call_id: str
    parent_call_id: str | None
    prompt_id: str | None
    source: str
    version_id: str | None
    revision_number: int | None
    consumer_key_id: str | None
    provider_config_id: str | None
    upstream_model: str | None
    outcome: str
    pinned: bool
    fallback: bool
    streaming: bool
    input_tokens: int | None
    output_tokens: int | None
    usage_status: str
    cost: Decimal | None
    currency: str | None
    cost_status: str
    added_latency_ms: int | None
    upstream_duration_ms: int | None
    error_class: str | None
    created_at: datetime


async def list_prompt_conversations(
    db: AsyncSession,
    prompt_id: str,
    *,
    cursor: str | None = None,
    limit: int = CONVERSATION_PAGE_LIMIT,
    since: datetime | None = None,
) -> tuple[ConversationListing, ...]:
    """The conversations this prompt took part in, most recently active first.

    **No permission check here, and there must never be one** — the same rule
    `list_prompt_call_records` states, for the same reason. ADR-0018 leaves this
    module without an edge to access-control, and a second copy of "who may see
    this" is precisely what that ADR refused. prompt-registry has already loaded
    the prompt row and authorised `prompt.read` against it before calling.

    Scoping to one prompt is what keeps BR-01 intact, and it is why there is no
    workspace-wide version of this function: a list of every conversation would
    name conversations that ran through private prompts, which tells a reader
    those prompts exist.

    Takes the caller's `db`, so the authorisation and the rows come from one
    snapshot — `list_prompt_call_records`'s argument, unchanged.
    """
    if not 1 <= limit <= CONVERSATION_MAX_LIMIT:
        raise ValueError(f"limit={limit} is outside A-045's bound of 1..{CONVERSATION_MAX_LIMIT}")

    rows = (
        (
            await db.execute(
                LIST_PROMPT_CONVERSATIONS,
                {"prompt_id": prompt_id, "cursor": cursor, "limit": limit, "since": since},
            )
        )
        .mappings()
        .all()
    )
    return tuple(ConversationListing(**dict(row)) for row in rows)


async def read_conversation_calls(
    db: AsyncSession,
    prompt_id: str,
    conversation_id: str,
    *,
    limit: int = CONVERSATION_NODE_CAP,
) -> tuple[ConversationCall, ...]:
    """One conversation's calls, oldest first, gated on the prompt the caller may read.

    **`prompt_id` is not a filter, and removing it would be a privilege
    escalation.** The caller authorised `prompt.read` on that prompt and on
    nothing else; the query returns the conversation only if the prompt actually
    took part in it. A conversation the caller has no connection to is not
    refused — it returns zero rows, which is not-found's shape and carries no
    information about whether the id exists.

    **Capped rather than paged.** A cursor over a graph is close to meaningless:
    page two of a tree is a set of nodes whose parents are on page one, and every
    layout decision the client makes needs the whole set. So the read takes all of
    it up to the cap and the caller reports truncation explicitly. The caller asks
    for `cap + 1` precisely so that "exactly at the cap" and "over it" are
    distinguishable.

    The rows returned span every prompt in the conversation, including ones the
    caller may not see. Filtering them is the caller's job and cannot be done
    here: ADR-0020 requires the subject's `owner_id` and `access_level` to be
    passed to `may()` by whoever read them, and this module may not read a
    registry row.
    """
    if not 1 <= limit <= CONVERSATION_MAX_LIMIT + 1:
        raise ValueError(f"limit={limit} is outside 1..{CONVERSATION_MAX_LIMIT + 1}")

    rows = (
        (
            await db.execute(
                READ_CONVERSATION_CALLS,
                {"prompt_id": prompt_id, "conversation_id": conversation_id, "limit": limit},
            )
        )
        .mappings()
        .all()
    )
    return tuple(ConversationCall(**dict(row)) for row in rows)


#: One prompt's traffic, folded to counts. ADR-0055's read path with a WINDOW on
#: it rather than a second read path beside it — the permission decision still
#: happens in prompt-registry, against a prompt row it already read, and there is
#: still no cross-prompt shape available to anybody.
#:
#: **Aggregated in the database rather than folded in Python from
#: `list_prompt_call_records`.** That seam is paginated at 200 rows for A-045's
#: reason, and a day of traffic on a busy prompt is not 200 rows; a caller that
#: paged through it would be building the flat reader ADR-0055 refused, one page
#: at a time. Aggregation also means the return value is arithmetic and cannot
#: carry a single call's identity, let alone a body.
SUMMARISE_PROMPT_CALLS = text(
    """
    SELECT count(*)                                                      AS requests,
           count(*) FILTER (WHERE outcome = 'truncated')                 AS truncated,
           count(*) FILTER (WHERE outcome = 'fallback')                  AS fallback,
           count(*) FILTER (WHERE outcome = 'caller_error')              AS caller_error,
           count(*) FILTER (WHERE outcome = 'upstream_error')            AS upstream_error,
           count(*) FILTER (WHERE pinned)                                AS pinned,
           count(*) FILTER (WHERE usage_status = 'unknown')              AS usage_unknown,
           count(*) FILTER (WHERE cost_status = 'unpriced')              AS cost_unpriced,
           count(*) FILTER (WHERE parent_call_id IS NOT NULL)            AS chained,
           coalesce(sum(input_tokens), 0)                                AS input_tokens,
           coalesce(sum(output_tokens), 0)                               AS output_tokens,
           percentile_disc(0.95) WITHIN GROUP (ORDER BY upstream_duration_ms)
                                                                         AS latency_p95_ms,
           percentile_disc(0.99) WITHIN GROUP (ORDER BY upstream_duration_ms)
                                                                         AS latency_p99_ms,
           max(created_at)                                               AS last_called_at
    FROM   ledger.call_record
    WHERE  prompt_id  = :prompt_id
      AND  created_at >= :window_start
      AND  created_at <  :window_end
      AND  source      = 'gateway'
    """
)


@dataclass(frozen=True, slots=True)
class PromptCallWindow:
    """One prompt's traffic over one window, as counts. INT-043.

    **No field here can carry a call's identity, and that is the type doing the
    work again.** `CallRecordListing` cannot hold a body; this cannot hold a
    call. A caller reading windows can compute that truncation rose and cannot
    reconstruct which request truncated, which is exactly the amount of
    information the improvement sweep needs and the most it should have.

    `source = 'gateway'` in the query above is deliberate and it is not a
    filter for tidiness. Eval runs, playground calls, observations and probes are
    all Prope's own traffic against the prompt; folding them into a window would
    make *"latency got worse"* move because somebody ran a suite. The question is
    about what production is experiencing, so only production traffic answers it.

    `chained` is the count of calls with a `parent_call_id`, NOT a maximum chain
    depth. Real depth needs a recursive walk of the conversation graph, and
    `read_conversation_calls` is per conversation for BR-01's reason — a
    cross-conversation walk here would be a shape ADR-0058 does not offer. A
    rising SHARE of chained calls is what retry and loop behaviour looks like
    from this side, and the proxy is named as a proxy rather than dressed up.
    """

    requests: int
    truncated: int
    fallback: int
    caller_error: int
    upstream_error: int
    pinned: int
    usage_unknown: int
    cost_unpriced: int
    chained: int
    input_tokens: int
    output_tokens: int
    latency_p95_ms: int | None
    latency_p99_ms: int | None
    last_called_at: datetime | None


async def summarise_prompt_calls(
    db: AsyncSession,
    prompt_id: str,
    *,
    window_start: datetime,
    window_end: datetime,
) -> PromptCallWindow:
    """INT-043. One prompt's production traffic over `[window_start, window_end)`.

    Takes the caller's `db`, exactly as `list_prompt_call_records` does and for
    its stated reason: the caller has already opened a `workspace_transaction`
    to authorise, and reading the authorisation and the data under one snapshot
    is strictly better than reading them under two.

    **This seam performs no permission check and must never grow one.** ADR-0018
    makes call-ledger a sink with no edge to access-control, so a second copy of
    *who may see this* cannot live here. The check happens in prompt-registry,
    which loaded the prompt row and authorised `prompt.read` against it before
    reaching this line.

    The tenant policy supplies the workspace restriction, so a `prompt_id`
    belonging to another workspace returns an empty window rather than that
    workspace's traffic — the aggregate over zero rows, which is what
    deny-by-default looks like when the query is a `count(*)`.
    """
    if window_end <= window_start:
        raise ValueError("window_end must be after window_start")

    row = (
        (
            await db.execute(
                SUMMARISE_PROMPT_CALLS,
                {
                    "prompt_id": prompt_id,
                    "window_start": window_start,
                    "window_end": window_end,
                },
            )
        )
        .mappings()
        .one()
    )
    return PromptCallWindow(**dict(row))
