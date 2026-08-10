"""INT-028's five management routes. One router, no outbound call, no body read path.

**Five ``/api/v1`` paths, and the count is a path count.** ``interfaces.md``
INT-028 states *"5 routes"* while showing four bullet lines, because
``POST|GET /api/v1/prices`` is one line and two paths. They are:

    POST /api/v1/prices                            append one price row
    GET  /api/v1/prices                            the table, superseded rows included
    GET  /api/v1/prices/unpriced                   the worklist Phase 1 owed this route
    PUT  /api/v1/workspaces/{id}/spend-ceiling     set or clear the ceilings
    PUT  /api/v1/workspaces/{id}/retention         set the body retention window

``prope.app`` adds INT-030's ``/healthz`` and ``/readyz`` for seven in the
assembled table, and ``tests/architecture/test_route_table.py`` compares that
table against a literal list so an extra path fails as loudly as a missing one.

**Read the method column, not only the path column.** Both ``/workspaces/{id}``
paths are registered ``PUT``-**only**. INT-028 gives neither the ceiling nor the
retention window a read route, so a client observes what its write produced from
the ``PUT`` response body and from nowhere else — which is why
:class:`~prope.call_ledger.schemas.SpendCeilingState` returns the resulting state
in full rather than echoing the request. Adding a ``GET`` would be a sixth
``/api/v1`` path, exceeding ``apis.exposes`` and the registered interface; that
is a deviation to raise as an OQ against INT-028, not a line in this file.

**This module calls no other module, and its ``dependencies`` list is empty.**
call-ledger is a sink (ADR-0018). INT-028 says it in its own words: *"this module
exposes nothing that needs a permission check, which is exactly why it can have
no dependency on access-control — its only edge would be the one that turns a
ledger into a caller"*. So every route declares
:func:`~prope.session_auth.require_session` and one
:class:`~prope.session_auth.ManagementAction`, and neither of those is a
permission check; the action is a declaration Phase 7's wiring and Phase 23's
route-table assertion both read.

**No route, response model, query parameter or path parameter exposes a stored
request body, response body or byte size.** ADR-0018 and A-105 give the body
store no read path in the MVP, and CL-10's full claim is Phase 3's while its
cross-module form is Phase 23's. This phase's obligation is not to build the
route that would fail either, and the assembled OpenAPI schema is asserted free
of one.

**The price table is append-only through this router exactly as it is in the
database.** There is no ``UPDATE`` and no ``DELETE`` against
``ledger.price_table`` anywhere below; superseding a price is a new row with a
later ``effective_from`` (A-102), so a cost figure recorded under the old one
stays explicable. ``prope_app`` holds ``SELECT`` and ``INSERT`` on that table and
nothing else (T-006, proven live in Phase 1), so the engine refuses even a
mistake — but the absence here is what makes the mistake un-writable.

**Every handler that touches tenant data goes through ``workspace_transaction``,
and the workspace comes from the session.** Under ADR-0045 a ``prope_app`` query
issued with no ``app.workspace_id`` set returns **zero rows** from every
``ledger`` table — not an error, an empty result — so a handler that forgot the
seam would answer ``200`` with nothing in it. The ``{id}`` path parameter is
checked against the session's workspace and answered **not-found** when it
differs (A-045: not-found, never forbidden), so the parameter is not a way to
discover which workspaces exist (T-02-30).

**A-046.** Nothing here logs a request body, a response body, a price figure or
a session cookie. The one log line is written by ``prope.app``'s envelope
handler and carries an event name, the machine ``code`` and a ``request_id``.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from ulid import ULID

from prope.call_ledger.retention_settings import set_retention_window
from prope.call_ledger.schemas import (
    MONEY_SCALE_PLACES,
    ErrorCode,
    PageRequest,
    PriceRowCreate,
    PriceRowPage,
    PriceRowRead,
    RetentionSet,
    RetentionState,
    SpendCeilingSet,
    SpendCeilingState,
    UnpricedRow,
)
from prope.call_ledger.writer import UNPRICED_WORKLIST
from prope.db.session import workspace_transaction
from prope.session_auth import (
    ManagementAction,
    ManagementRefusal,
    Session,
    declares_action,
    require_session,
)

#: A-045 / ADR-0003: typed-prefix ULIDs. ``prc_`` is the price row's, and this is
#: the first place in Prope that generates one — ``call_id`` is caller-supplied
#: (A-099) because a broker redelivery has to be idempotent against it, and a
#: price row has no redelivery to be idempotent against.
PRICE_ROW_ID_PREFIX = "prc_"

#: INSERT only. Never an UPDATE, never a DELETE — see the module docstring.
INSERT_PRICE_ROW = text(
    """
    INSERT INTO ledger.price_table (
        price_row_id, workspace_id, provider_config_id, upstream_model,
        input_price_per_1k, output_price_per_1k, currency,
        effective_from, created_by
    ) VALUES (
        :price_row_id, :workspace_id, :provider_config_id, :upstream_model,
        :input_price_per_1k, :output_price_per_1k, :currency,
        :effective_from, :created_by
    )
    """
)

#: **One statement, serving both reads**, because the two differ only in a
#: predicate and a duplicated projection is two places for the derived range to
#: drift. ``GET /prices`` passes a ``cursor`` and a ``limit`` with
#: ``price_row_id`` NULL; ``POST /prices`` passes the id it just inserted with
#: the other two at NULL and 1. Each ``CAST(... AS text) IS NULL`` disjunct is a
#: filter that switches itself off, which is what makes one statement answer both
#: questions without a fragment being pasted into either.
#:
#: It is also written as a **plain string constant** rather than composed from a
#: shared fragment, because ``tests/architecture/test_no_sql_interpolation.py``
#: requires every ``text()`` argument to be one. That gate is deliberately
#: strict — from Phase 2 onward a ``workspace_id`` arrives inside a broker
#: payload — and the right response to it is a statement that needs no
#: composition, not an entry on its allow-list.
#:
#: **The effective range is DERIVED, never stored.** ``lead(effective_from)`` over
#: exactly the key ``uq_price_table_workspace_id`` is unique on is the half-open
#: interval ``pricing.PRICE_IN_FORCE`` already implements with
#: ``effective_from <= :at ORDER BY effective_from DESC LIMIT 1``. A stored
#: ``effective_to`` would be a second encoding of one fact, and the two would
#: disagree the first time a row was inserted *between* two others — which is
#: CL-05's whole scenario, a price row added after calls have accrued. Superseded
#: rows are returned with their ranges (INT-028, A-102); the row in force has a
#: NULL ``effective_to``.
#:
#: ``workspace_id`` is in the ``PARTITION BY`` alongside the tenant policy rather
#: than instead of it, the posture ``PRICE_IN_FORCE`` takes with its explicit
#: predicate: the policy is the enforcement, the explicit column is what makes
#: the window a property of the statement.
#:
#: Keyset pagination, not offset. A page computed from an offset shifts under an
#: append-only table the moment somebody adds a row mid-scroll; a page taken from
#: "the last id I saw" does not. ``price_row_id`` is a ULID, so ordering by it is
#: ordering by creation, and it is a total order — which
#: ``(provider, model, effective_from)`` is not without a tiebreak. The casts are
#: not decoration: with none, asyncpg has no type to infer for a NULL parameter.
PRICE_ROWS = text(
    """
    SELECT * FROM (
        SELECT price_row_id,
               provider_config_id,
               upstream_model,
               input_price_per_1k,
               output_price_per_1k,
               currency,
               effective_from,
               lead(effective_from) OVER (
                   PARTITION BY workspace_id, provider_config_id, upstream_model
                   ORDER BY effective_from
               ) AS effective_to,
               created_by,
               created_at
        FROM   ledger.price_table
    ) AS ranged
    WHERE  (CAST(:price_row_id AS text) IS NULL
            OR ranged.price_row_id = CAST(:price_row_id AS text))
      AND  (CAST(:cursor AS text) IS NULL
            OR ranged.price_row_id > CAST(:cursor AS text))
    ORDER  BY ranged.price_row_id
    LIMIT  :limit
    """
)

#: Writes exactly the columns ``seams.check_spend_ceiling`` reads — ``enabled``,
#: ``monthly_limit`` and ``currency`` — plus ``per_run_limit``, which is declared
#: and defaults off and becomes a check in whichever phase adds its
#: ``CeilingReason`` member. The agreement between what this statement writes and
#: what that function reads is the whole point of the route, so it is asserted by
#: driving the real function through this route rather than by reading the row
#: back (``tests/integration/test_management_routes.py``).
#:
#: An upsert, not a read-then-branch: *"set this workspace's ceiling"* has one
#: outcome whichever way it happens, and a caller that had to know which one
#: would be a caller that could get it wrong under a concurrent first write. It
#: is the shape ``retention_settings.UPSERT_RETENTION_WINDOW`` already uses.
#:
#: **Clearing a limit writes the cleared state; it never deletes the row.** A
#: workspace with no row and a workspace whose row has ``enabled`` false both
#: allow, and collapsing them is how a workspace silently loses the ceiling
#: somebody set — so ``DELETE`` is absent here on purpose, and ``prope_app``
#: holds no ``DELETE`` on this table anyway.
#:
#: ``RETURNING`` is what makes the ``PUT`` response a real read-back rather than
#: an echo of the request. INT-028 registers no ``GET`` on this path.
UPSERT_SPEND_CEILING = text(
    """
    INSERT INTO ledger.spend_ceiling (
        workspace_id, monthly_limit, per_run_limit, currency, enabled, updated_by, updated_at
    ) VALUES (
        :workspace_id, :monthly_limit, :per_run_limit, :currency, :enabled, :updated_by, :updated_at
    )
    ON CONFLICT (workspace_id) DO UPDATE SET
        monthly_limit = EXCLUDED.monthly_limit,
        per_run_limit = EXCLUDED.per_run_limit,
        currency      = EXCLUDED.currency,
        enabled       = EXCLUDED.enabled,
        updated_by    = EXCLUDED.updated_by,
        updated_at    = EXCLUDED.updated_at
    RETURNING workspace_id, monthly_limit, per_run_limit, currency, enabled, updated_at
    """
)

router = APIRouter(prefix="/api/v1")


def _utc_now() -> datetime:
    """The one clock read in this module, in the one place that may read it.

    ``prope.worker`` states the same rule for the same reason: everything
    downstream — ``set_retention_window``, the ceiling's ``updated_at`` — takes
    the instant as an argument, so what a request wrote is arithmetic on one
    value rather than on however many clock reads the call graph made.
    """
    return datetime.now(UTC)


def get_sessionmaker(request: Request) -> async_sessionmaker[AsyncSession]:
    """The application's sessionmaker, put on ``app.state`` by ``prope.app``'s lifespan.

    A dependency rather than a module-level global for two reasons: a global
    would be built at import time, before any settings are read, and a test
    would have no seam to point at a container. It is what
    ``tests/integration/test_management_routes.py`` sets.

    A missing sessionmaker is a ``503`` and not a ``500``: the process is up and
    the request is well-formed, and the only state in which this can happen is
    one where the lifespan has not run.
    """
    sessionmaker = getattr(request.app.state, "sessionmaker", None)
    if sessionmaker is None:
        raise ManagementRefusal(
            status_code=503,
            code=ErrorCode.INTERNAL_ERROR,
            message="the application has no database sessionmaker; its lifespan has not run",
        )
    return sessionmaker


def path_workspace(
    workspace_id: Annotated[str, Path(alias="id")],
    session: Annotated[Session, Depends(require_session)],
) -> str:
    """The ``{id}`` path parameter, refused as **not-found** when it is not the session's.

    A-045: *"a subject the actor may not see returns not-found, never
    forbidden"*. The distinction carries security weight here rather than
    politeness — ``403`` would confirm that the named workspace exists, turning
    the path parameter into an enumeration oracle (T-02-30). The refusal is
    byte-identical to the one a workspace that does not exist at all would get,
    because both are this same branch.

    Underneath it, the tenant policy would return zero rows for another
    workspace anyway (ADR-0045). This check is what turns that silence into an
    answer, and what stops a ``PUT`` writing into the session's workspace while
    the caller believes it addressed another.
    """
    if workspace_id != session.workspace_id:
        raise ManagementRefusal(
            status_code=404,
            code=ErrorCode.NOT_FOUND,
            message="no such workspace",
        )
    return workspace_id


def _constraint_name(error: IntegrityError) -> str | None:
    """The engine's constraint name, for **branching on** and never for returning.

    asyncpg raises ``UniqueViolationError`` / ``CheckViolationError`` carrying
    ``constraint_name``. **It is two levels down, not one**: SQLAlchemy's asyncpg
    dialect re-raises its own ``AsyncAdapt_asyncpg_dbapi.IntegrityError`` as
    ``error.orig`` and chains the real asyncpg exception onto it as
    ``__cause__``. Reading only ``error.orig`` finds nothing, silently, and every
    mapped refusal below degrades into a ``500`` — which is exactly what
    happened when this function was written the obvious way. Both are checked so
    a future dialect change that stops chaining is not a second outage.

    The name is used to choose a machine ``code`` and is never put into a
    ``message`` or into ``details`` — a constraint name reaching a client is
    T-02-34, and it is also a string no translation catalogue has an entry for
    (ADR-0053).
    """
    for candidate in (error.orig, getattr(error.orig, "__cause__", None)):
        name = getattr(candidate, "constraint_name", None)
        if name:
            return str(name)
    return None


def _refuse_unrepresentable_money(figures: dict[str, Decimal | None]) -> None:
    """Refuse a figure the money columns cannot hold **exactly**, before any write.

    Two shapes, and each is a silent corruption rather than an error if it is
    allowed through:

    **More scale than the column.** Every money column in ``ledger`` is
    ``numeric(20,10)``. Postgres would round an eleventh decimal place away
    without complaint, leaving a stored price that differs from the one somebody
    submitted — which is precisely what T-006's append-only privilege set and
    ADR-0019's effective dating exist to keep explicable. Refusing is the only
    answer that does not quietly change a number.

    **A non-finite value.** ``numeric`` accepts ``NaN``, and in Postgres
    ``NaN >= 0`` is **true**, so ``ck_price_table_prices_are_non_negative``
    would let one through; ``compute_cost`` would then produce a ``NaN`` cost
    that ``cost <= 0`` does not catch, and the row would be stored as ``priced``
    with a cost nobody can compare. Refused here because there is nowhere
    downstream that catches it.
    """
    unrepresentable: dict[str, Any] = {}
    for name, figure in figures.items():
        if figure is None:
            continue
        if not figure.is_finite():
            unrepresentable[name] = str(figure)
        elif -figure.as_tuple().exponent > MONEY_SCALE_PLACES:
            unrepresentable[name] = str(figure)

    if unrepresentable:
        raise ManagementRefusal(
            status_code=422,
            code=ErrorCode.MONEY_SCALE_EXCEEDED,
            message=(
                f"every money column in ledger is numeric({MONEY_SCALE_PLACES + 10},"
                f"{MONEY_SCALE_PLACES}); a figure with more scale than that, or one that is not "
                "finite, would be stored as a number different from the one submitted"
            ),
            details={"figures": unrepresentable, "scale": MONEY_SCALE_PLACES},
        )


def _price_row(row: Any) -> PriceRowRead:
    """One mapping from ``RANGED_PRICE_ROWS`` as its response model."""
    return PriceRowRead(
        price_row_id=row["price_row_id"],
        provider_config_id=row["provider_config_id"],
        upstream_model=row["upstream_model"],
        input_price_per_1k=row["input_price_per_1k"],
        output_price_per_1k=row["output_price_per_1k"],
        currency=row["currency"],
        effective_from=row["effective_from"],
        effective_to=row["effective_to"],
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


@router.post(
    "/prices",
    status_code=201,
    response_model=PriceRowRead,
    dependencies=[Depends(declares_action(ManagementAction.PRICE_CREATE))],
)
async def create_price_row(
    payload: PriceRowCreate,
    session: Annotated[Session, Depends(require_session)],
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> PriceRowRead:
    """Append one price row. **Insert only** — superseding a price is a new row.

    Two refusals carry their own machine ``code``, and both are ``422`` in the
    one envelope (INT-028's failure line).

    **CR-01, the free-tier row.** A row whose ``input_price_per_1k`` and
    ``output_price_per_1k`` are both zero is refused here, at the only place a
    human can create one. Phase 1's verifier established the chain and
    recommended exactly this disposition, option (a) — *a blocking pre-condition
    on the Phase 2 plan that builds ``POST /api/v1/prices``*:
    ``ck_price_table_prices_are_non_negative`` **permits** ``(0, 0)`` because it
    is non-negative, ``compute_cost`` then returns exactly zero for every call
    that row prices, and ``write_records`` **raises** on a zero cost and discards
    the whole batch (``ck_call_record_cost_is_never_zero``: neither storing a
    zero nor downgrading to unpriced would be true). So a single free-tier price
    row poisons every batch containing a call it prices (T-02-32). The other half
    of CR-01 — one unpriceable record not discarding its batch-mates — is plan
    02-01's drain classification, and both halves land in this phase because
    that is where the exposure arrives.

    **The ambiguous effective range.** A row colliding on
    ``(workspace_id, provider_config_id, upstream_model, effective_from)`` meets
    ``uq_price_table_workspace_id``, which exists because two rows sharing that
    key would make ``ORDER BY effective_from DESC LIMIT 1`` non-deterministic —
    a non-deterministic figure on an approval record is what ADR-0019 exists to
    prevent. The unique violation is caught and answered as a ``code`` with
    ``details`` naming the four values the caller sent; the constraint name does
    not reach the client.
    """
    if payload.input_price_per_1k == 0 and payload.output_price_per_1k == 0:
        # CR-01. See the docstring: the CHECK permits it, compute_cost returns
        # zero, and write_records then refuses the whole batch. The message says
        # the consequence rather than "invalid", because a bare validation error
        # would read as a quirk of this route instead of a decision.
        raise ManagementRefusal(
            status_code=422,
            code=ErrorCode.PRICE_BOTH_PRICES_ARE_ZERO,
            message=(
                "a price row with both per-1k prices at zero would price every call it applies "
                "to at exactly zero, and a priced call may not record a cost of zero — so every "
                "batch containing such a call would be refused at write time and discarded"
            ),
            details={
                "input_price_per_1k": str(payload.input_price_per_1k),
                "output_price_per_1k": str(payload.output_price_per_1k),
            },
        )

    _refuse_unrepresentable_money(
        {
            "input_price_per_1k": payload.input_price_per_1k,
            "output_price_per_1k": payload.output_price_per_1k,
        }
    )

    price_row_id = f"{PRICE_ROW_ID_PREFIX}{ULID()}"
    values = {
        "price_row_id": price_row_id,
        "workspace_id": session.workspace_id,
        "provider_config_id": payload.provider_config_id,
        "upstream_model": payload.upstream_model,
        "input_price_per_1k": payload.input_price_per_1k,
        "output_price_per_1k": payload.output_price_per_1k,
        "currency": payload.currency,
        "effective_from": payload.effective_from,
        "created_by": session.user_id,
    }

    try:
        async with workspace_transaction(sessionmaker, session.workspace_id) as db:
            await db.execute(INSERT_PRICE_ROW, values)
            row = (
                (
                    await db.execute(
                        PRICE_ROWS,
                        {"price_row_id": price_row_id, "cursor": None, "limit": 1},
                    )
                )
                .mappings()
                .one()
            )
    except IntegrityError as error:
        constraint = _constraint_name(error)
        if constraint == "uq_price_table_workspace_id":
            raise ManagementRefusal(
                status_code=422,
                code=ErrorCode.PRICE_EFFECTIVE_RANGE_AMBIGUOUS,
                message=(
                    "a price row already exists for this provider config, model and effective "
                    "instant; two rows sharing them would make the price in force at that instant "
                    "ambiguous, so supersede it with a later effective_from instead"
                ),
                details={
                    "workspace_id": session.workspace_id,
                    "provider_config_id": payload.provider_config_id,
                    "upstream_model": payload.upstream_model,
                    "effective_from": payload.effective_from.isoformat(),
                },
            ) from error
        if constraint == "ck_price_table_prices_are_non_negative":
            raise ManagementRefusal(
                status_code=422,
                code=ErrorCode.PRICE_IS_NEGATIVE,
                message="a per-1k price may not be negative",
                details={
                    "input_price_per_1k": str(payload.input_price_per_1k),
                    "output_price_per_1k": str(payload.output_price_per_1k),
                },
            ) from error
        raise

    return _price_row(row)


@router.get(
    "/prices",
    response_model=PriceRowPage,
    dependencies=[Depends(declares_action(ManagementAction.PRICE_READ))],
)
async def list_price_rows(
    page: Annotated[PageRequest, Query()],
    session: Annotated[Session, Depends(require_session)],
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> PriceRowPage:
    """The price table, **superseded rows included**, with derived effective ranges.

    A-102: superseding a price is a new row, and a superseded row keeps being
    returned because a cost figure recorded under it has to stay explicable
    years later. The range is derived by ``lead(effective_from)`` rather than
    stored — see :data:`RANGED_PRICE_ROWS`.

    Cursor-paginated at A-045's 50 by default and 200 at most (T-02-33). Each
    row carries its own currency and there is no conversion anywhere (A-107).
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        rows = (
            (
                await db.execute(
                    PRICE_ROWS,
                    {"price_row_id": None, "cursor": page.cursor, "limit": page.limit},
                )
            )
            .mappings()
            .all()
        )

    items = [_price_row(row) for row in rows]
    # Present rather than inferred from ``len(items) < limit``: a full final page
    # is indistinguishable from a full non-final one, and a client that guessed
    # would either stop early or ask one time too many forever.
    next_cursor = items[-1].price_row_id if len(items) == page.limit else None
    return PriceRowPage(items=items, next_cursor=next_cursor)


@router.get(
    "/prices/unpriced",
    response_model=list[UnpricedRow],
    dependencies=[Depends(declares_action(ManagementAction.UNPRICED_WORKLIST_READ))],
)
async def list_unpriced(
    session: Annotated[Session, Depends(require_session)],
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> list[UnpricedRow]:
    """The ``(provider, model)`` pairs that have produced calls with no price row.

    **Serves ``writer.UNPRICED_WORKLIST`` unchanged.** Phase 1 wrote the query
    and the partial index ``ix_call_record_unpriced_worklist`` behind it, with a
    comment saying Phase 1 owed the encoding, the index and the query and Phase 2
    owed the route. This is that route, and there is deliberately no second
    aggregate here: a projection written twice is two answers to *"what has not
    been priced"*, and the whole point of the encoding is that there is one.

    INT-028 calls this *"the only spend-shaped screen in the MVP"*. It is a
    worklist, not a total — an unpriced call has a NULL cost by construction, so
    there is no figure here to sum or to leak.

    Not paginated, because the projection is grouped by ``(provider_config_id,
    upstream_model)`` and its cardinality is the number of models a workspace
    uses, not the number of calls it has made.
    """
    async with workspace_transaction(sessionmaker, session.workspace_id) as db:
        rows = (await db.execute(UNPRICED_WORKLIST)).mappings().all()

    return [
        UnpricedRow(
            provider_config_id=row["provider_config_id"],
            upstream_model=row["upstream_model"],
            unpriced_calls=row["unpriced_calls"],
            since=row["since"],
        )
        for row in rows
    ]


@router.put(
    "/workspaces/{id}/spend-ceiling",
    response_model=SpendCeilingState,
    dependencies=[Depends(declares_action(ManagementAction.SPEND_CEILING_SET))],
)
async def set_spend_ceiling(
    payload: SpendCeilingSet,
    workspace_id: Annotated[str, Depends(path_workspace)],
    session: Annotated[Session, Depends(require_session)],
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> SpendCeilingState:
    """Set or clear this workspace's ceilings. Both default off (A-029).

    **The response body is the read-back, and that is INT-028's doing rather
    than a preference.** This path is registered ``PUT``-only: there is no
    ``GET /spend-ceiling``, this phase adds none, and the route-table test fails
    on a sixth ``/api/v1`` path. So the response returns the resulting state in
    full — the monthly limit, the per-run limit, ``enabled`` and the currency —
    because it is the only route-shaped place a client can learn which of the
    three states its write produced. A later reader should not add the ``GET``
    believing it was an oversight; it is a deviation to raise as an OQ.

    **The three states, and why the middle one has to exist.** No row at all
    (never configured), a row with ``enabled`` false (configured then turned
    off), and a row with ``enabled`` true and a limit. The first two both allow,
    but only one leaves a row behind, and collapsing them is how a workspace
    silently loses the ceiling somebody set. Clearing writes the cleared state:
    it does not delete the row and it does not touch recorded spend, which lives
    in ``ledger.workspace_spend`` and is maintained only by ``write_records``.

    **A limit with no currency is refused**, and this is the refusal most worth
    reading twice. ``check_spend_ceiling`` treats a limit whose currency is NULL
    — or one denominated differently from the workspace's recorded spend — as an
    **unevaluable** check: it fails **open**, allows the run, and increments
    ``prope_call_ledger_ceiling_check_total{result="failed_open"}``. A-107 forbids
    conversion, so that is the right answer for the seam. But it means a ceiling
    written here without a currency would be a ceiling that never refuses anything
    and says so only through a counter with no scraper until plan 03-04 mounts
    ``/metrics`` — an off switch with a light nobody is watching (A-104). Refused
    at the one place a human creates it.
    """
    if (payload.monthly_limit is not None and payload.monthly_limit < 0) or (
        payload.per_run_limit is not None and payload.per_run_limit < 0
    ):
        # ledger.spend_ceiling carries no positivity CHECK, so this is the only
        # guard there is. A negative limit refuses every run forever — spend is
        # never below it — with nothing anywhere saying why.
        raise ManagementRefusal(
            status_code=422,
            code=ErrorCode.SPEND_CEILING_LIMIT_IS_NEGATIVE,
            message=(
                "a spend limit may not be negative; recorded spend is never below zero, so a "
                "negative limit would refuse every eval run with no way to see why"
            ),
            details={
                "monthly_limit": None
                if payload.monthly_limit is None
                else str(payload.monthly_limit),
                "per_run_limit": None
                if payload.per_run_limit is None
                else str(payload.per_run_limit),
            },
        )

    has_limit = payload.monthly_limit is not None or payload.per_run_limit is not None
    if has_limit and payload.currency is None:
        raise ManagementRefusal(
            status_code=422,
            code=ErrorCode.SPEND_CEILING_LIMIT_NEEDS_CURRENCY,
            message=(
                "a spend limit must name its currency; there is no conversion anywhere in Prope, "
                "so a limit with no currency cannot be compared against a recorded spend total "
                "and the ceiling check would allow every run while counting itself unevaluable"
            ),
        )

    _refuse_unrepresentable_money(
        {"monthly_limit": payload.monthly_limit, "per_run_limit": payload.per_run_limit}
    )

    now = _utc_now()
    async with workspace_transaction(sessionmaker, workspace_id) as db:
        row = (
            (
                await db.execute(
                    UPSERT_SPEND_CEILING,
                    {
                        "workspace_id": workspace_id,
                        "monthly_limit": payload.monthly_limit,
                        "per_run_limit": payload.per_run_limit,
                        "currency": payload.currency,
                        "enabled": payload.enabled,
                        "updated_by": session.user_id,
                        "updated_at": now,
                    },
                )
            )
            .mappings()
            .one()
        )

    return SpendCeilingState(
        workspace_id=row["workspace_id"],
        enabled=row["enabled"],
        monthly_limit=row["monthly_limit"],
        per_run_limit=row["per_run_limit"],
        currency=row["currency"],
        updated_at=row["updated_at"],
    )


@router.put(
    "/workspaces/{id}/retention",
    response_model=RetentionState,
    dependencies=[Depends(declares_action(ManagementAction.RETENTION_SET))],
)
async def set_retention(
    payload: RetentionSet,
    workspace_id: Annotated[str, Depends(path_workspace)],
    session: Annotated[Session, Depends(require_session)],
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> RetentionState:
    """Set the body retention window. The write half of what the drain reads.

    Calls ``retention_settings.set_retention_window`` — the upsert plan 02-02
    built with this route named at the statement — passing ``updated_by`` from
    the session's subject and ``now`` from this handler, because that module
    reads no clock.

    **A window at or below zero is refused by the engine and surfaced, never
    clamped.** ``ck_workspace_retention_window_is_positive`` is the guarantee and
    nothing re-checks it here: a retention policy quietly corrected into a legal
    one is a policy nobody set, and this repository's rule is that the database
    owns the constraint. The ``422`` below is the translation of that refusal
    into the one envelope, not a second check.

    **It takes effect for bodies written after it and for no others** (D-10).
    ``expires_at`` is stamped once by ``write_records`` and never rewritten, so
    shortening a window leaves existing rows on the expiry they were given.
    There is no backfill and there cannot be one: ``prope_app`` holds ``SELECT``,
    ``INSERT`` and ``DELETE`` on ``ledger.call_body`` and deliberately no
    ``UPDATE``.
    """
    now = _utc_now()
    try:
        await set_retention_window(
            sessionmaker,
            workspace_id,
            timedelta(days=payload.retention_days),
            updated_by=session.user_id,
            now=now,
        )
    except IntegrityError as error:
        if _constraint_name(error) == "ck_workspace_retention_window_is_positive":
            raise ManagementRefusal(
                status_code=422,
                code=ErrorCode.RETENTION_WINDOW_NOT_POSITIVE,
                message=(
                    "a retention window must be strictly positive; a window of zero or less would "
                    "expire every body at the instant it was written, and it is refused rather "
                    "than corrected into one that was not asked for"
                ),
                details={"retention_days": payload.retention_days},
            ) from error
        raise

    return RetentionState(
        workspace_id=workspace_id,
        retention_days=payload.retention_days,
        updated_at=now,
    )
