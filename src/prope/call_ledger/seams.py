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

**The accepted cost, recorded rather than hidden.** An eval run's state change
and its usage write are now two transactions, and a crash between them is
possible: the usage rows can be committed while the run is still marked running,
or the run can advance with its usage unwritten. The retry is what fixes it, and
the retry is only safe once ``write_records`` upserts on ``call_id`` — that is
CL-02, in Phase 3. Until then a redelivered or retried batch meets a unique
violation, which is loud rather than silent, which is the correct failure mode
for a window this short.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.call_ledger.domain import CallRecordDraft, Outcome, Source
from prope.call_ledger.writer import period_month, write_records
from prope.db.session import workspace_transaction
from prope.observability import ceiling_failed_open_total

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
    that cannot be evaluated returns ``allowed`` and increments
    ``prope_call_ledger_ceiling_failed_open_total``; it does not raise into
    evaluation. The trade is stated rather than assumed: the ceiling guards an
    optional, off-by-default feature, and blocking a reviewer's evidence over a
    billing lookup is the worse outcome. **The counter is the control**, because
    an open-failing check nobody watches is an off switch.

    **The branch ships here; the claim does not.** CL-07 is the requirement that
    states the fail-open behaviour and its counter, and CL-07 belongs to Phase 3.
    This plan builds the branch because INT-020 and A-142 §2 make it part of the
    seam's contract, and it does not tick the requirement.
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
            return CeilingDecision(allowed=True)

        if row["total_cost"] is None:
            # A ceiling exists and nothing priced has landed this month. Not a
            # zero total — a total that does not exist yet — and either way the
            # workspace is under any positive limit.
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
            return CeilingDecision(
                allowed=False, reason=CeilingReason.MONTHLY_CEILING_EXCEEDED
            )

        return CeilingDecision(allowed=True)

    except Exception as error:
        # Deliberately broad, and deliberately not re-raising. ``Exception``
        # rather than ``BaseException`` leaves ``asyncio.CancelledError`` alone,
        # so a shutdown still cancels this task instead of being counted as a
        # billing-lookup failure.
        #
        # A-046: the exception's CLASS, never its message, which at this depth
        # can quote a row, a connection string or a figure.
        ceiling_failed_open_total.inc()
        log.warning(
            "call_ledger.ceiling_failed_open",
            workspace_id=workspace_id,
            reason=type(error).__name__,
        )
        return CeilingDecision(allowed=True)
