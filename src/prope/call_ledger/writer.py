"""The Phase 1 write-path seam. One writer, three cost states, no fourth.

``write_records`` is what Phase 2's broker drain calls once per workspace group
and what Phase 3's direct-write fallback calls with a single record. There is
one implementation of it on purpose: the lock file requires that pricing and
``expires_at`` stamping cannot drift between those two callers, and two
functions that both "write a call record" is exactly how they would.

**The session is handed in and carries exactly one workspace.** It comes from
``workspace_transaction()``, which opened the transaction and set the tenant for
its duration (D-08, ADR-0040). This function therefore opens no transaction,
switches no workspace, and refuses a batch containing a second ``workspace_id``
before writing any of it. The policy's ``WITH CHECK`` would refuse a mis-stamped
row at the engine, but a half-written batch is not an acceptable way to discover
the mistake.

**Every record is priced at its OWN ``created_at``.** Not at wall-clock write
time, which differs after a backlog or a redelivery (ADR-0019). Nothing in this
module reads a clock: ``expires_at`` is the record's own ``created_at`` plus the
``retention_window`` argument, and ``period_month`` is the record's own
``created_at`` in UTC. ``written_at`` and ``updated_at`` are left to their column
defaults, which is the one place a server clock is the correct answer, because
those two columns mean "when the database saw this".

**Three states, and nothing may invent a fourth.**

    reported usage + a resolved price   -> priced,         cost > 0, currency, price_row_id
    reported usage + no resolved price  -> unpriced,       cost/currency/price_row_id NULL
    no usage object                     -> not_applicable, tokens NULL as well

There is no default branch. A missing price is never a zero price, a missing
usage object is never zero tokens, and no path here substitutes an average, the
nearest price row, or a figure inferred from prompt length. ``ck_call_record_
cost_state_is_coherent`` and ``ck_call_record_cost_is_never_zero`` say the same
thing in the schema; this module is what makes sure they are never asked to.

**No body reaches a log line or a metric label** (A-046). This module writes a
body to exactly one place — ``ledger.call_body`` — and it emits **four counters
and no log**. Phase 1's sentence here said *"no log and no metric at all"*, and
D-33/D-35/D-40 make that false in the same change that makes it false, so it is
replaced rather than left standing. The four are
``prope_call_ledger_duplicate_call_id_total``,
``prope_call_ledger_missing_version_id_total``,
``prope_call_ledger_unpriced_total`` and ``prope_call_ledger_unknown_usage_total``,
and every one of them describes **the statement's own outcome or the record's own
encoding** rather than the record's contents: no body reaches a label, because
none of the four carries a body-shaped label at all. **They live here rather than
at the three call sites** — the drain, the direct-write fallback and
``price_usage`` — because a counter each caller has to remember is a counter one
caller forgets, which is INT-019's *"the same upsert INT-018's drain uses"* read
as an instruction about metrics too. The alternative shape was to raise a typed
error and increment at each call site; it is refused for consistency, because
D-35 already put one counter here and two metric conventions inside one function
is worse than one rewritten sentence.

**This module is the first consumer of the Core layer anywhere in ``src/``**, and
three consequences follow that are worth stating rather than discovering:

1. ``tests/architecture/test_no_sql_interpolation.py`` inspects ``text(...)``
   arguments only, so the two Core constructs below pass that gate **by not being
   seen** rather than by being safe. That is not a hole — a Core construct binds
   its own parameters and there is nothing to interpolate — but it is written down
   rather than relied on.
2. That file's guard test asserts ``found >= 5`` ``text()`` calls, so moving two
   statements off ``text()`` moves the count. It does not move it below the floor.
   **If it ever does, the repair is not to raise the threshold**: the guard exists
   so the walk cannot pass by inspecting nothing, and the honest fix is to confirm
   the remaining statements are genuinely fewer and adjust the floor with a comment
   naming which ones left — never by touching ``ALLOWED``, which stays empty.
3. ``tests/architecture/test_schema_invariants.py`` asserts every table declared in
   ``models.py`` has a live counterpart whose columns are a superset. Until this
   change that was insurance on a declaration nothing consumed; from here it guards
   the statement that writes **every call record in the system**.
"""

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from prope.call_ledger import models
from prope.call_ledger.domain import (
    CallRecordDraft,
    CostStatus,
    Source,
    UsageStatus,
    WriteResult,
)
from prope.call_ledger.pricing import compute_cost, resolve_price
from prope.observability import (
    duplicate_call_id_total,
    missing_version_id_total,
    unknown_usage_total,
    unpriced_total,
)

#: A-040: 30 days, the default retention window. It is a PARAMETER for this
#: phase and deliberately not a column read (OQ-B) — no table outside
#: call-ledger's ``data.owns`` is touched to satisfy it. Phase 2 owns the
#: storage decision when ``PUT /workspaces/{id}/retention`` arrives.
DEFAULT_RETENTION_WINDOW = timedelta(days=30)

#: **D-33: the statement CL-02 actually turns on.**
#:
#: ``ledger.call_record``'s primary key is ``call_id`` alone
#: (``0002_call_record.py:90``), so a second row was already impossible and
#: ``ON CONFLICT`` alone buys nothing CL-02 asks for. What a redelivery corrupts
#: is ``ledger.workspace_spend`` — the monthly aggregate maintained inside this
#: transaction (A-103) so that ``check_spend_ceiling`` reads one row instead of
#: aggregating the largest table in the system — because that aggregate used to be
#: built from the rows OFFERED. **``RETURNING`` over ``DO NOTHING`` is the only
#: statement shape that says which rows were NEW**, and the returned set is what
#: the buckets below are built from. A change that stopped at
#: ``ON CONFLICT DO NOTHING`` would pass a "the record appears once" test and still
#: fail CL-02.
#:
#: **Why this is a Core construct and not ``text()``:** a ``text()`` executemany
#: returns no per-row results, so there is no returned set to read. ``models.py``
#: already declares the table, so this is a change of construct rather than a new
#: modelling layer.
#:
#: **``DO NOTHING``, never ``DO UPDATE``, and there are four independent reasons.**
#: (1) ADR-0019 prices once at write time and never revises; ``DO UPDATE`` would
#: re-price an existing record from a redelivered envelope, which is the one thing
#: effective dating exists to prevent. (2) ``prope_app`` holds no ``UPDATE`` on
#: ``ledger.call_body`` (``0003_ledger_tables.py:246-252``, *"No UPDATE: bodies are
#: written once and deleted"*) and PostgreSQL requires ``UPDATE`` privilege for
#: ``ON CONFLICT DO UPDATE`` — so ``DO UPDATE`` on one table and ``DO NOTHING`` on
#: the other would put two idempotency semantics inside one function. (3) Only
#: ``RETURNING`` over ``DO NOTHING`` reports which rows were new, and CL-02's claim
#: is about ``workspace_spend``. (4) The pleasant corollary, recorded because a
#: future tightening would break two things rather than one: the ``SELECT`` grant
#: on ``call_body`` that ``0003`` justifies solely as *"required alongside
#: DELETE"* is **also** what makes ``ON CONFLICT DO NOTHING`` legal on that table,
#: because all forms of ``ON CONFLICT`` require ``SELECT`` on any column read.
#:
#: **``sort_by_parameter_order`` is DELIBERATELY ABSENT, and this paragraph is the
#: reason**, because the absence of an argument is invisible and somebody adding
#: ordering "for determinism" would be making a reasonable-looking change that
#: fails only under load. With it, SQLAlchemy selects ``call_id`` as a
#: **client-side sentinel**, and the driver then compares the sentinel-keyed result
#: length against the batch length — which ``ON CONFLICT DO NOTHING`` guarantees
#: will differ the first time a duplicate arrives. That raises
#: ``InvalidRequestError: Sentinel-keyed result set did not produce correct number
#: of rows``, which is **CL-02's own scenario turned into an exception**, on the
#: path whose whole job is to survive it. No ordering is needed, because the
#: returned ids are used as a **set**: the month buckets are built from membership,
#: never from positional correspondence. That is why D-33 says ``RETURNING
#: call_id`` and not ``RETURNING`` an index.
#:
#: **A zero ``rowcount`` here means the OPPOSITE of what it means at
#: ``UPSERT_WORKSPACE_SPEND`` below.** There, an ``ON CONFLICT ... WHERE`` makes a
#: conflicting row not match, so "nothing updated" is a genuine refusal (WARN-2 /
#: T-02-13). Here, "nothing inserted" means *already there*, which is the ordinary
#: redelivery case and is not an error at all. This statement's outcome is read
#: from the returned set and never from ``rowcount`` — said out loud because the
#: neighbouring statement in this same file says the opposite about its own, and a
#: reader will otherwise carry the reading across.
UPSERT_CALL_RECORD = (
    pg_insert(models.call_record)
    .on_conflict_do_nothing(index_elements=["call_id"])
    .returning(models.call_record.c.call_id)
)

#: **D-34: a body follows its record.** Its rows are filtered by the same returned
#: ``call_id`` set before this executes, so a ``call_body`` row is written only for
#: a record THIS transaction inserted.
#:
#: The case that decides is the one ADR-0041 creates on purpose: a confirm that
#: **timed out** rather than being refused means the broker did get the message,
#: the direct-write fallback wrote the record without its body, and the broker
#: later delivers the same record *with* its body. Letting that body land would
#: recover real data — and would break AC-1's stated equality, *"body_dropped_total
#: equals the number missing from call_body"*, because the drop was already
#: counted. **A counter that cannot be reconciled against the table is worse than a
#: body that was already declared best-effort (A-037).** The cost, stated plainly
#: rather than left to be discovered: **a body lost to a timed-out confirm is lost
#: permanently, by decision.**
#:
#: It carries its own ``ON CONFLICT DO NOTHING`` as well as the filter — belt and
#: braces, because ``DO UPDATE`` is not available to it at all (see above) and a
#: ``call_body`` row whose ``call_record`` row is missing is a state nothing in this
#: module can produce but nothing in this module checks for either.
UPSERT_CALL_BODY = pg_insert(models.call_body).on_conflict_do_nothing(
    index_elements=["call_id"]
)

#: A-103: the monthly aggregate is maintained inside the writer's own
#: transaction, so ``check_spend_ceiling`` reads one row instead of aggregating
#: the largest and fastest-growing table in the system. The composite primary
#: key is what makes this a single conflict-target upsert.
#:
#: ``call_count`` adds every record written for the month, including unpriced
#: and not-applicable ones. ``total_cost`` adds only priced costs, and stays
#: NULL until a priced record arrives — ``ck_workspace_spend_total_cost_carries_
#: currency`` requires a currency beside any total, and a total of zero standing
#: in for "nothing priced yet" would be the same lie this whole module refuses.
#:
#: **The ``WHERE`` on the ``DO UPDATE`` branch closes WARN-2** (T-02-13). Phase 1
#: enforced one currency per ``(workspace, month)`` by reading
#: ``workspace_spend.currency`` and then upserting, which two concurrent drains
#: can interleave into a USD-labelled total containing VND —
#: ``ck_workspace_spend_currency_format`` checks the format of the label and can
#: see nothing about what the total is made of. Carrying the invariant into the
#: statement makes a conflicting currency simply not match the row: the update is
#: skipped, ``rowcount`` is 0, and a zero rowcount here is a real refusal rather
#: than a no-op. Same technique as ``repricing.UPDATE_TO_PRICED``, which repeats
#: its status predicate in the update's own ``WHERE`` so a row another writer
#: changed in between is not overwritten with a second opinion.
#:
#: The three disjuncts are the three cases that are NOT a conflict: the row has
#: no currency yet, this batch prices nothing, or the two agree. The pre-read
#: below is kept alongside and is not redundant — it produces the clearer message
#: on the ordinary sequential path, and it does so without spending a doomed
#: transaction. The belt-and-braces half of WARN-2 — that exactly one drain
#: consumer runs — is asserted in plan 02-03.
UPSERT_WORKSPACE_SPEND = text(
    """
    INSERT INTO ledger.workspace_spend (
        workspace_id, period_month, currency, total_cost, call_count
    ) VALUES (
        :workspace_id, :period_month, :currency, :total_cost, :call_count
    )
    ON CONFLICT (workspace_id, period_month) DO UPDATE SET
        call_count = ledger.workspace_spend.call_count + EXCLUDED.call_count,
        total_cost = CASE
            WHEN EXCLUDED.total_cost IS NULL THEN ledger.workspace_spend.total_cost
            ELSE COALESCE(ledger.workspace_spend.total_cost, 0) + EXCLUDED.total_cost
        END,
        currency   = COALESCE(ledger.workspace_spend.currency, EXCLUDED.currency),
        -- The one clock reading in this module, and the correct one: updated_at
        -- means "when the database saw this", the same thing its column default
        -- means. No pricing or retention value is derived from it.
        updated_at = clock_timestamp()
    WHERE  ledger.workspace_spend.currency IS NULL
       OR  EXCLUDED.currency IS NULL
       OR  ledger.workspace_spend.currency = EXCLUDED.currency
    """
)

READ_SPEND_CURRENCY = text(
    """
    SELECT currency FROM ledger.workspace_spend
    WHERE  workspace_id = :workspace_id AND period_month = :period_month
    """
)

#: CL-04's operational surface, as a projection over the stored encoding rather
#: than a second table. Served by ``ix_call_record_unpriced_worklist``, the
#: partial index over ``cost_status = 'unpriced'``.
#:
#: Phase 1 owes the encoding, the index and this query. Phase 2 owes the route
#: (``GET /api/v1/prices/unpriced``); none is built here. The tenant policy
#: supplies the workspace restriction, so there is no ``workspace_id`` predicate
#: to forget.
UNPRICED_WORKLIST = text(
    """
    SELECT provider_config_id,
           upstream_model,
           count(*)       AS unpriced_calls,
           min(created_at) AS since
    FROM   ledger.call_record
    WHERE  cost_status = 'unpriced'
    GROUP  BY provider_config_id, upstream_model
    ORDER  BY unpriced_calls DESC, upstream_model
    """
)


def period_month(at: datetime) -> date:
    """The first day of ``at``'s month, in UTC.

    From the record's own ``created_at``, never from wall clock — same reasoning
    as pricing. A drain catching up across a month boundary must not file
    September's calls under August.

    **Public, and taking an instant rather than a draft, because there are two
    callers and they must agree** (RESEARCH Pitfall 8). ``write_records`` has a
    record and passes its ``created_at``; ``check_spend_ceiling`` has no record at
    all and must pick a month itself. If the ceiling read derived its month in
    local time while the writer filed by UTC, the two would disagree for up to a
    day at every month boundary — and the disagreement is invisible, because both
    sides would be internally consistent and simply looking at different rows.
    One function is what makes that impossible; two agreeing implementations
    would only make it unlikely.

    The conversion is ``astimezone(UTC)`` rather than ``replace(tzinfo=UTC)``:
    the first moves the instant into UTC, the second relabels it and would file a
    call made at 23:00 on 31 August in a +07:00 offset under August when it
    happened in September.
    """
    at_utc = at.astimezone(UTC)
    return date(at_utc.year, at_utc.month, 1)


async def write_records(
    session: AsyncSession,
    records: Sequence[CallRecordDraft],
    *,
    retention_window: timedelta = DEFAULT_RETENTION_WINDOW,
) -> WriteResult:
    """Price, stamp, upsert and aggregate one workspace's batch. All or nothing.

    ``session`` must come from ``workspace_transaction()``. This function does
    not commit; the caller's context manager owns the transaction boundary, so a
    raise anywhere below leaves nothing written.

    Raises ``ValueError`` for a batch this encoding cannot represent: more than
    one workspace, more than one currency in one month, an ``eval`` record
    carrying a body, a priced record whose cost works out to zero, or a
    ``source=gateway`` record with no ``version_id``.

    **Two passes, and the split is load-bearing** (D-33). Pass 1 validates and
    prices the WHOLE batch — every refusal above is decided over every offered
    record, before anything is written. Pass 2 runs after the upsert and touches
    only the ``call_id``s the statement RETURNED, because that is the set that
    actually became rows and therefore the only set a spend total may be built
    from. A redelivered record is priced, counted in ``WriteResult`` and counted
    on ``duplicate_call_id_total`` — and moves ``ledger.workspace_spend`` by
    nothing at all.
    """
    if not records:
        return WriteResult()

    workspaces = {record.workspace_id for record in records}
    if len(workspaces) > 1:
        raise ValueError(
            f"batch spans {len(workspaces)} workspaces {sorted(workspaces)}; ADR-0040 groups by "
            "workspace and the session carries exactly one, so this batch is refused whole "
            "rather than written in part"
        )

    record_rows: list[dict] = []
    body_rows: list[dict] = []
    #: One entry per OFFERED draft, in order: what pass 2 needs to bucket a row
    #: it now knows actually inserted. Carried rather than recomputed, because
    #: re-deriving the cost would mean resolving every price a second time.
    aggregated: list[tuple[str, date, Decimal | None, str | None]] = []
    #: period_month -> the one currency priced records in that month may use.
    #: **Validation only** — the spend buckets are built in pass 2 and this map
    #: is not one of them.
    offered_currency: dict[date, str] = {}
    counts = {CostStatus.PRICED: 0, CostStatus.UNPRICED: 0, CostStatus.NOT_APPLICABLE: 0}

    for draft in records:
        if draft.source == Source.EVAL and draft.body is not None:
            raise ValueError(
                f"{draft.call_id} is source=eval and carries a body; no call_body row will ever "
                "exist for an eval call (A-055)"
            )

        if draft.source == Source.GATEWAY and draft.version_id is None:
            # D-40. Refused BY NAME, before the insert, rather than left to
            # ck_call_record_gateway_calls_carry_version_id — which would refuse
            # it too, as an IntegrityError that dead-letters under a CONSTRAINT's
            # name rather than under this counter's. The counter's whole job is
            # to be zero, and a counter that can never move is not a control.
            #
            # Same posture as EvalUsageRow.__post_init__ and as the zero-cost
            # refusal below: name what is missing, never substitute. The two
            # alternative answers are both false — a synthesised version id would
            # claim a revision served this call when none did, and dropping the
            # record would delete the very evidence the "100% of gateway calls
            # record a version ID" metric is about.
            #
            # classify_write_failure maps a ValueError to PERMANENT, so this
            # record dead-letters: missing_version_id_total rising and dlq_depth
            # rising are THE SAME EVENT, and the alert annotation should say so
            # rather than inviting two incidents.
            missing_version_id_total.inc()
            raise ValueError(
                f"{draft.call_id} is source=gateway and has no version_id; "
                "ck_call_record_gateway_calls_carry_version_id requires one, and a gateway call "
                "that cannot say which revision served it is not evidence anybody can act on"
            )

        cost: Decimal | None = None
        currency: str | None = None
        price_row_id: str | None = None

        if draft.usage_status is UsageStatus.UNKNOWN:
            # No usage object. There is nothing to price — not "nothing to
            # charge". The tokens stay NULL and the cost is not_applicable.
            cost_status = CostStatus.NOT_APPLICABLE
            # Counted for the record OFFERED, not for the row inserted — and the
            # same is true of unpriced_total below. These two describe what the
            # caller sent, not what the table gained: a redelivered unpriced
            # record is still an unpriced record whose price row nobody has
            # fixed, and a redelivered usage-less record is still a provider that
            # returned no usage object. Only the SPEND aggregate is built from
            # the inserted set, because only the spend aggregate is money.
            unknown_usage_total.labels(source=str(draft.source)).inc()
        else:
            price = await resolve_price(
                session,
                workspace_id=draft.workspace_id,
                provider_config_id=draft.provider_config_id,
                upstream_model=draft.upstream_model,
                at=draft.created_at,
            )
            if price is None:
                # No price in force at this call's own timestamp — whether
                # because no row exists or because every row is later. The two
                # are the same absence and are stored the same way.
                cost_status = CostStatus.UNPRICED
                # LedgerPriceMissing reads this one. A draft that carries no
                # provider config renders as the string "None" here rather than
                # as an invented "unknown": the label says what the record says,
                # and a fourth value one line from the third is how a vocabulary
                # stops being one.
                unpriced_total.labels(
                    provider_config_id=draft.provider_config_id,
                    upstream_model=draft.upstream_model,
                ).inc()
            else:
                cost_status = CostStatus.PRICED
                cost = compute_cost(draft.input_tokens or 0, draft.output_tokens or 0, price)
                currency = price.currency
                price_row_id = price.price_row_id
                if cost <= 0:
                    # Unrepresentable, and deliberately loud. A priced record
                    # with a zero cost is refused by
                    # ck_call_record_cost_is_never_zero, and the two honest
                    # answers here — a zero, or a silent downgrade to unpriced
                    # — are both a figure the encoding does not have. Surfacing
                    # it is the only option that does not invent one.
                    raise ValueError(
                        f"{draft.call_id} prices to {cost} against price row {price_row_id}: "
                        f"{draft.input_tokens} input and {draft.output_tokens} output tokens at "
                        f"{price.input_price_per_1k}/{price.output_price_per_1k} per 1k. A priced "
                        "record cannot record a cost of zero, and neither a zero nor a downgrade "
                        "to unpriced would be true"
                    )

        counts[cost_status] += 1
        month = period_month(draft.created_at)

        # **The mixed-currency refusal stays in pass 1, over the WHOLE batch**
        # (D-33, RESEARCH Pitfall 2). If it moved into pass 2 with the buckets, a
        # batch mixing two currencies whose second-currency records happened to
        # be duplicates would be silently ACCEPTED where it is refused today — a
        # property that changed without a test going red. A batch mixing
        # currencies is a caller bug whether or not its rows are duplicates, and
        # refusing it whole is this module's established posture. The cost is one
        # extra iteration over a list already in memory.
        #
        # **The keying is reproduced exactly, and "exactly" is the whole point.**
        # Before this split the refusal was a side effect of the month-bucket
        # accumulation, so it was keyed on ``period_month(draft.created_at)`` and
        # consulted only records that carry a cost. A January-USD /
        # February-VND batch is therefore ACCEPTED, and so is one whose second
        # currency arrives only on an unpriced record. The natural wrong move is
        # a batch-wide ``{r.currency for r in records}`` set, which would tighten
        # write_records silently — nothing in the suite would fail, because the
        # existing mixed-currency test uses a single month.
        if cost is not None:
            established = offered_currency.setdefault(month, currency)
            if established != currency:
                raise ValueError(
                    f"batch mixes currencies {established} and {currency}; a workspace uses "
                    "one currency and there is no conversion (A-107), so a sum across two of them "
                    "would be a number with no unit"
                )

        record_rows.append(
            {
                "call_id": draft.call_id,
                "workspace_id": draft.workspace_id,
                "source": str(draft.source),
                "prompt_id": draft.prompt_id,
                "version_id": draft.version_id,
                "revision_number": draft.revision_number,
                "run_id": draft.run_id,
                "case_id": draft.case_id,
                "consumer_key_id": draft.consumer_key_id,
                "actor_id": draft.actor_id,
                "provider_config_id": draft.provider_config_id,
                "upstream_model": draft.upstream_model,
                "outcome": str(draft.outcome),
                "pinned": draft.pinned,
                "fallback": draft.fallback,
                "streaming": draft.streaming,
                "input_tokens": draft.input_tokens,
                "output_tokens": draft.output_tokens,
                "usage_status": str(draft.usage_status),
                "cost": cost,
                "currency": currency,
                "price_row_id": price_row_id,
                "cost_status": str(cost_status),
                "added_latency_ms": draft.added_latency_ms,
                "upstream_duration_ms": draft.upstream_duration_ms,
                "error_class": draft.error_class,
                "created_at": draft.created_at,
            }
        )

        if draft.body is not None:
            body_rows.append(
                {
                    "call_id": draft.call_id,
                    "workspace_id": draft.workspace_id,
                    "request_body": draft.body.request_body,
                    "response_body": draft.body.response_body,
                    "byte_size": draft.body.byte_size,
                    # From the record's OWN created_at. A backlogged record must
                    # not get a shorter life than a fresh one (A-106).
                    "expires_at": draft.created_at + retention_window,
                    "created_at": draft.created_at,
                }
            )

        aggregated.append((draft.call_id, month, cost, currency))

    workspace_id = records[0].workspace_id

    # ---- PASS 2 -----------------------------------------------------------
    # The upsert first, because everything below it depends on knowing which
    # rows were new. ``scalars()`` over ``RETURNING call_id`` gives exactly that
    # and nothing else; the ids are consumed as a SET and never positionally,
    # which is what makes ``sort_by_parameter_order``'s absence safe as well as
    # necessary (see UPSERT_CALL_RECORD).
    inserted = set((await session.execute(UPSERT_CALL_RECORD, record_rows)).scalars().all())

    # D-35: the DATABASE's own view of what was already there — rows offered
    # minus call_ids returned. It is incremented HERE rather than in the drain so
    # that all three callers (the drain, the direct-write fallback and
    # price_usage) get it for free, which is the answer to INT-019's "idempotent
    # on call_id — the same upsert INT-018's drain uses". Deliberately NOT the
    # same counter as redelivered_total, which is the BROKER's view: the
    # LedgerDuplicateCallIds alert reads the two together, and that comparison is
    # impossible if either side is derived from the other.
    duplicates = len(record_rows) - len(inserted)
    if duplicates:
        duplicate_call_id_total.inc(duplicates)

    #: period_month -> [count, priced total or None, currency or None]. Built
    #: from the INSERTED set alone: a record that was already there adds nothing
    #: to a workspace's spend, which is the whole of CL-02. Pass 1 has already
    #: established that a month carries one currency, so the conflict branch that
    #: used to live in this loop cannot fire here and is not repeated.
    months: dict[date, dict] = {}
    for call_id, month, cost, currency in aggregated:
        if call_id not in inserted:
            continue
        bucket = months.setdefault(
            month, {"call_count": 0, "total_cost": None, "currency": None}
        )
        bucket["call_count"] += 1
        if cost is not None:
            if bucket["currency"] is None:
                bucket["currency"] = currency
            bucket["total_cost"] = (bucket["total_cost"] or Decimal(0)) + cost

    # D-34: a body follows its record — see UPSERT_CALL_BODY for the trade this
    # makes and what it costs.
    surviving_bodies = [row for row in body_rows if row["call_id"] in inserted]
    if surviving_bodies:
        await session.execute(UPSERT_CALL_BODY, surviving_bodies)

    # ``month`` rather than ``period_month``: the latter is now a module-level
    # function, and a loop variable of the same name would shadow it here.
    for month, bucket in months.items():
        if bucket["currency"] is not None:
            stored = (
                await session.execute(
                    READ_SPEND_CURRENCY,
                    {"workspace_id": workspace_id, "period_month": month},
                )
            ).scalar_one_or_none()
            if stored is not None and stored != bucket["currency"]:
                raise ValueError(
                    f"{workspace_id} already has spend recorded in {stored} for {month} and "
                    f"this batch is priced in {bucket['currency']}; A-107 forbids conversion, so "
                    "the two cannot be summed"
                )
        result = await session.execute(
            UPSERT_WORKSPACE_SPEND,
            {"workspace_id": workspace_id, "period_month": month, **bucket},
        )
        if result.rowcount == 0:
            # WARN-2's race, caught where the read above cannot reach it: between
            # that read and this statement another transaction committed a
            # different currency for the same (workspace, month). The upsert's
            # WHERE made the row not match rather than relabelling the total, so
            # nothing is mislabelled and there is a refusal to report.
            #
            # The stored currency is re-read rather than guessed. This is READ
            # COMMITTED, so the new statement takes a fresh snapshot and sees the
            # row the other transaction committed — the same row that just
            # refused to match.
            stored = (
                await session.execute(
                    READ_SPEND_CURRENCY,
                    {"workspace_id": workspace_id, "period_month": month},
                )
            ).scalar_one_or_none()
            raise ValueError(
                f"{workspace_id} has spend recorded in {stored} for {month} and this batch is "
                f"priced in {bucket['currency']}; another writer committed the first between this "
                "batch's read and its write. A-107 forbids conversion, so the two cannot be "
                "summed, and the total is left labelled with the currency it actually contains"
            )

    return WriteResult(
        priced=counts[CostStatus.PRICED],
        unpriced=counts[CostStatus.UNPRICED],
        unknown=counts[CostStatus.NOT_APPLICABLE],
        # From the rows that SURVIVED the filter, never from the rows built: the
        # type's own rule is that a count says what it is derived from, and
        # "bodies offered" is a different number from "bodies written" the moment
        # a redelivery arrives carrying one.
        bodies_written=len(surviving_bodies),
        duplicates=duplicates,
    )
