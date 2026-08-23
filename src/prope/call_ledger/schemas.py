"""INT-028's wire types, and the A-045 conventions this project did not have yet.

Three things arrive with this file and every later module inherits all three:
**one error envelope**, **one pagination convention**, and **one rule about
money on the wire**. There was no route anywhere in this repository before it, so
none of them had a precedent to copy — A-045 and ADR-0003 supply the conventions
and INT-024's failure line supplies the semantics INT-028 inherits by reference.

**The vocabularies are imported, never re-declared.** ``Source``, ``Outcome``,
``CostStatus`` and ``UsageStatus`` live in ``prope.call_ledger.domain``, whose
members are byte-identical to the database ``CHECK`` sets. A second copy here
would be a second thing to keep in step with a constraint, and the first drift
would be invisible in both directions.

**Money is ``Decimal`` and it crosses the wire as a JSON *string*.** Every money
column in ``ledger`` is ``numeric(20,10)`` and ``pricing.COST_SCALE`` names the
ten places; a representative call costs about ``0.00007``, which is why
``pricing.py`` refuses to quantise to a currency's minor unit. A JSON *number*
would hand that figure to a client's double and give it back changed, and
``str(Decimal("1E-10"))`` would hand it over in scientific notation. So the
serializer below is fixed-point and explicit, and
``tests/integration/test_management_routes.py`` asserts a ten-place round trip
rather than trusting a default.

**Every timestamp is timezone-aware, in and out.** ``AwareDatetime`` refuses a
naive value at the edge for ``domain.py``'s reason: a naive value compared
against a ``timestamptz`` is read against the server's time zone, which would
make an effective-dated price depend on where the database is running. An
``effective_from`` is the single most damaging place for that to happen.

**No model here carries a stored request body, a stored response body or a byte
size, and none ever may.** ADR-0018 and A-105: the body store has **no read path
in the MVP** — no viewer, no export, no endpoint — and INT-028 says so again in
its own words. The strongest available place to make that true is the type a
route is able to return, which is why ``CallBodyDraft``'s three fields have no
counterpart in this file. The absence is asserted over the *assembled OpenAPI
schema* by ``tests/architecture/test_route_table.py``, not by inspection, because
a rule that is only written down is a rule somebody adds a field beside.

**Where a refusal is decided, and why not here.** These models describe
**shape**: types, formats, bounds that are true of the representation. Every
refusal that has a *reason* — a free-tier price row, a limit with no currency,
a figure with more scale than the column can hold — is raised in
``prope.call_ledger.api`` as a :class:`~prope.session_auth.ManagementRefusal`
carrying its own :class:`~prope.errors.ErrorCode`. A ``model_validator`` would
collapse all of them into one ``validation_failed``, and ADR-0053 makes the
``code`` the thing the client actually renders, so a merged code is a message the
SPA cannot write.

**The envelope itself left this file in Phase 7, and this module's docstring is
where that was predicted.** ``ErrorCode``, ``ApiError``, ``ErrorEnvelope``,
``REQUEST_ID_PREFIX`` and ``install_error_envelope`` now live in
``prope.errors``, because access-control mounts the second router in the product
and may not import call-ledger — ADR-0018 makes this module a sink. They are
re-exported below so that no call site in this package changed, which is the
whole point of doing the move as a move rather than as a rewrite.
"""

from decimal import Decimal
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, PlainSerializer

from prope.errors import (
    REQUEST_ID_PREFIX,
    ApiError,
    ErrorCode,
    ErrorEnvelope,
    install_error_envelope,
)

#: Re-exported from ``prope.errors``, not defined here. Listing them keeps
#: ``from prope.call_ledger.schemas import ErrorCode`` working for the importers
#: that predate the move — ``api.py``, ``tests/integration/test_management_routes``
#: and ``tests/unit/test_retention_days_bound`` — and keeps ruff from reading the
#: import block above as unused.
__all__ = [
    "DEFAULT_PAGE_LIMIT",
    "MAX_PAGE_LIMIT",
    "MAX_RETENTION_DAYS",
    "MONEY_SCALE_PLACES",
    "REQUEST_ID_PREFIX",
    "ApiError",
    "ErrorCode",
    "ErrorEnvelope",
    "PageRequest",
    "install_error_envelope",
    "PriceRowCreate",
    "PriceRowPage",
    "PriceRowRead",
    "RetentionSet",
    "RetentionState",
    "SpendCeilingSet",
    "SpendCeilingState",
    "UnpricedRow",
]


def _fixed_point(value: Decimal) -> str:
    """A ``Decimal`` as the digits it actually holds. Never ``1E-10``.

    ``format(value, "f")`` keeps trailing zeros, so a ``numeric(20,10)`` value
    read back from the engine crosses the wire with all ten places intact and a
    client comparing two prices is comparing two strings of the same shape.
    """
    return format(value, "f")


#: Money on the wire. A ``Decimal`` in Python, a string in JSON.
#:
#: ``when_used="json"`` rather than ``"always"``: a caller doing ``model_dump()``
#: in Python is holding a ``Decimal`` and should keep it, because turning it into
#: a string in-process is how a figure gets parsed back as a float by something
#: downstream. The string is a **transport** decision and applies where transport
#: happens.
Money = Annotated[Decimal, PlainSerializer(_fixed_point, return_type=str, when_used="json")]

#: The scale of every money column in ``ledger`` — ``numeric(20,10)``, the same
#: ten places ``pricing.COST_SCALE`` quantises to. A value arriving with more
#: than this is refused at the route rather than rounded into the column, because
#: a stored price that differs from the one somebody submitted is the exact thing
#: T-006's append-only privilege set exists to keep explicable.
MONEY_SCALE_PLACES = 10

#: A-045: ``limit`` defaults to 50 and is capped at 200. Written as constants
#: because the route-table and pagination tests assert the numbers, and a
#: literal in a ``Field`` is a number a test would have to restate.
DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 200

#: Ten years, the upper bound on ``RetentionSet.retention_days``. A constant for
#: ``MAX_PAGE_LIMIT``'s reason: the test asserts the number, and a literal in a
#: ``Field`` is a number a test would have to restate.
#:
#: **Argued rather than rounded.** The bound's job is to stop an input becoming an
#: unclassifiable exception — see ``RetentionSet`` for why that exception is
#: unreachable from the engine — and among the values that do that job, ten years
#: is the largest that is still recognisably a retention *policy*. It is longer
#: than the pilot, longer than anything OQ-013 could plausibly answer, and short
#: enough that "never delete" cannot be spelled in this field: ADR-0018 and A-040
#: refuse that answer, and a bound of a million days would have quietly offered it.
#:
#: **What it does not do.** It does not bound the stored column. A workspace whose
#: window is already longer than ten years would be unaffected — there are none,
#: and no path exists that could have created one — because this bounds what a
#: caller may *set*, not what ``ledger.workspace_retention`` may *hold*.
#:
#: A tunable judgement and a product-visible limit, recorded so that changing it is
#: a visible act.
MAX_RETENTION_DAYS = 3650


class PageRequest(BaseModel):
    """A-045's cursor pagination: ``limit`` 50 by default, 200 at most.

    **A cap and not a suggestion.** ``le=MAX_PAGE_LIMIT`` makes ``limit=201`` a
    ``422`` rather than a silently clamped page, for ``set_retention_window``'s
    reason one table over: a request quietly corrected into one the caller did
    not make leaves them believing it took effect. It is also T-02-33's
    mitigation, and the number is asserted rather than documented.

    **The cursor is opaque and the client must not construct one.** Today it is
    the ``price_row_id`` of the last row of the previous page — a ULID, so
    ordering by it is ordering by creation — but that is an implementation of
    "opaque", not a promise. Offset pagination was not considered: a page
    computed from a count is a page that shifts under an append-only table
    whenever somebody adds a price row mid-scroll.
    """

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    cursor: str | None = None


class PriceRowCreate(BaseModel):
    """The body of ``POST /api/v1/prices``. One new row, never an edit.

    ``workspace_id`` is **not** a field. It comes from the session, because a
    caller able to name the workspace is a caller able to name another one, and
    the tenant seam takes exactly one workspace per transaction (ADR-0040).

    ``price_row_id`` is **not** a field either. It is server-generated with the
    ``prc_`` prefix (A-045, ADR-0003) — the one identifier class in this module
    that is not caller-supplied, because unlike ``call_id`` there is no
    redelivery to be idempotent against.

    ``effective_from`` may be in the past, and that is required rather than
    tolerated: CL-05 is precisely *"a price row is added after calls have
    accrued"*, and repricing them needs the new row to predate them. The
    migration says the same thing by having no ``CHECK (effective_from >=
    now())``.
    """

    model_config = ConfigDict(extra="forbid")

    provider_config_id: str = Field(min_length=1)
    upstream_model: str = Field(min_length=1)
    input_price_per_1k: Decimal
    output_price_per_1k: Decimal
    #: The floor under one request's cost, in ``currency``. Optional because zero
    #: is what the column defaults to and what every row written before migration
    #: 0017 means: a caller that has never heard of a per-request minimum keeps
    #: sending the body it always sent and keeps getting the arithmetic it always
    #: got. Per *request*, not per 1k — it is not scaled by tokens anywhere.
    minimum_charge_per_request: Decimal = Decimal(0)
    #: ``ck_price_table_currency_format``, mirrored so a malformed code is
    #: refused before a transaction opens rather than as a driver error.
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    effective_from: AwareDatetime


class PriceRowRead(BaseModel):
    """One price row with its **derived** effective range.

    ``effective_to`` is not stored and must never be: it is the next row's
    ``effective_from`` for the same ``(provider_config_id, upstream_model)``,
    which is exactly the half-open interval ``pricing.PRICE_IN_FORCE`` already
    implements with ``effective_from <= :at ORDER BY effective_from DESC LIMIT
    1``. Storing it would be a second encoding of the same fact, and the two
    would disagree the first time a row was inserted between two others — which
    is CL-05's whole scenario.

    ``effective_to`` is ``None`` for the row currently in force. A superseded row
    keeps its range and keeps being returned (INT-028, A-102), because a cost
    figure recorded under it has to stay explicable.

    ``currency`` travels with every figure and there is no conversion anywhere
    (A-107).
    """

    model_config = ConfigDict(extra="forbid")

    price_row_id: str
    provider_config_id: str
    upstream_model: str
    input_price_per_1k: Money
    output_price_per_1k: Money
    minimum_charge_per_request: Money
    currency: str
    effective_from: AwareDatetime
    effective_to: AwareDatetime | None = None
    created_by: str
    created_at: AwareDatetime


class PriceRowPage(BaseModel):
    """One page of ``GET /api/v1/prices``, plus the cursor for the next.

    ``next_cursor`` is ``None`` on the last page. It is present rather than
    inferred from ``len(items) < limit``, because a full final page is
    indistinguishable from a full non-final one and a client that guessed would
    either stop early or make one request too many forever.
    """

    model_config = ConfigDict(extra="forbid")

    items: list[PriceRowRead]
    next_cursor: str | None = None


class UnpricedRow(BaseModel):
    """One row of ``GET /api/v1/prices/unpriced``: a key that has produced cost-less calls.

    The projection ``writer.UNPRICED_WORKLIST`` has served since Phase 1, with a
    comment saying Phase 1 owed the query and the index and Phase 2 owed the
    route. INT-028 calls this *"the only spend-shaped screen in the MVP"* —
    there is no billing dashboard and the ceiling answers a boolean — which is
    why it returns a worklist and not a total.

    ``unpriced_calls`` is a count of calls, not of money: an unpriced call has a
    NULL cost by construction, so there is no figure here to leak or to sum.
    """

    model_config = ConfigDict(extra="forbid")

    provider_config_id: str | None = None
    upstream_model: str | None = None
    unpriced_calls: int
    since: AwareDatetime


class SpendCeilingSet(BaseModel):
    """The body of ``PUT /api/v1/workspaces/{id}/spend-ceiling``. The whole state.

    **A ``PUT`` of the resulting state, not a patch of one field.** The three
    reachable states — no row, a row with ``enabled`` false, a row with
    ``enabled`` true and a limit — are told apart by ``enabled``, and a partial
    update would make "I did not mention ``enabled``" indistinguishable from "I
    want it off".

    **``enabled`` has no default, deliberately.** Defaulting it to ``False``
    would let ``{"monthly_limit": "100", "currency": "USD"}`` succeed, return
    ``200``, and enforce nothing — the exact shape of a workspace silently
    losing the ceiling somebody set. Defaulting it to ``True`` would arm a
    ceiling somebody was only recording. So the caller says.

    The two limits are independent: either may be ``None`` while the other is
    set, and both ``None`` with ``enabled`` true is a row that allows
    everything and leaves a row behind, which is a different state from no row
    at all.

    ``currency`` is validated for **format** here and for **presence** at the
    route, because a limit with no currency is not a malformed request — it is a
    ceiling ``check_spend_ceiling`` cannot evaluate, and that has its own code.
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    monthly_limit: Decimal | None = None
    per_run_limit: Decimal | None = None
    #: ``ck_spend_ceiling_currency_format`` permits NULL, so this does too.
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")


class SpendCeilingState(BaseModel):
    """The resulting ceiling, in full. **The only read-back INT-028 permits.**

    INT-028 registers ``PUT`` on ``/api/v1/workspaces/{id}/spend-ceiling`` and
    **no other method**: there is no ``GET /spend-ceiling`` and this phase does
    not add one, because a sixth ``/api/v1`` path would exceed ``apis.exposes``
    and the registered interface — the kind of deviation OQ-018 through OQ-021
    exist to raise rather than absorb.

    That makes this response the load-bearing artifact it looks decorative as.
    It is where a client learns which of the three states its write produced, and
    a response that echoed the request or returned nothing would leave "never
    configured" and "configured then turned off" indistinguishable through the
    API — which is how a workspace quietly loses a ceiling.

    It carries figures the caller has just sent and which are that caller's own
    workspace's configuration, so A-056's no-figure rule is not in play: that
    rule governs ``seams.CeilingDecision``, which answers *"may this run start"*
    to somebody entitled to start runs and not necessarily to see what the
    workspace spends. **No spend total appears here**, only limits.
    """

    model_config = ConfigDict(extra="forbid")

    workspace_id: str
    enabled: bool
    monthly_limit: Money | None = None
    per_run_limit: Money | None = None
    currency: str | None = None
    updated_at: AwareDatetime


class RetentionSet(BaseModel):
    """The body of ``PUT /api/v1/workspaces/{id}/retention``. Days, not an interval.

    Days because A-040 states the default as *30 days* and INT-028 repeats it;
    the column is an ``interval`` so the positivity ``CHECK`` can be a plain
    comparison, and the route does the one conversion.

    **There is no lower bound on this field and that is deliberate.**
    ``ck_workspace_retention_window_is_positive`` is what refuses a zero or
    negative window, at the engine, and ``set_retention_window`` surfaces the
    refusal rather than clamping. Re-checking it here would put the guarantee in
    two places, and this repository's rule is that the database owns it — see
    ``retention_settings.UPSERT_RETENTION_WINDOW``, whose comment says the same.

    **There IS an upper bound, and it is different in kind from the lower one.**
    ``api.set_retention`` evaluates ``timedelta(days=payload.retention_days)``
    **before any statement exists**, so there is no engine there to refuse
    anything: above ``timedelta.max.days`` — 999,999,999 — that expression raises
    ``OverflowError``, which subclasses ``ArithmeticError`` and therefore matches
    **none** of ``drain.classify_write_failure``'s branches — it would take the
    ``PERMANENT`` default and dead-letter, two modules away from where the value
    was accepted. A ``CHECK`` cannot help with an exception raised in the client,
    which is why ``le=MAX_RETENTION_DAYS`` sits here and not in a migration.
    **This is the documented exception to "build database-first", and naming the
    exception is what keeps the rule intact.**

    **A cap and not a clamp**, inheriting :class:`PageRequest`'s consequence
    verbatim: a request quietly corrected into one the caller did not make leaves
    them believing it took effect, and a retention policy is exactly the setting
    where that belief is expensive. A ``le=`` violation renders as the existing
    ``ErrorCode.VALIDATION_FAILED`` through ``install_error_envelope``'s
    ``RequestValidationError`` handler; ``ErrorCode`` gains no member, because a
    code the SPA's catalogue has never seen renders as nothing at all and does so
    silently (ADR-0053).

    **So this one field carries two bounds that live in two different places for
    two different reasons, and a later reader must not tidy either into the
    other's home.** The lower one belongs to the engine because the engine can
    hold it; the upper one cannot be held there at all.
    """

    model_config = ConfigDict(extra="forbid")

    retention_days: int = Field(le=MAX_RETENTION_DAYS)


class RetentionState(BaseModel):
    """The resulting window. ``PUT``-only path, so this is the read-back.

    Same reasoning as :class:`SpendCeilingState`: INT-028 registers no ``GET``
    for this path either. The value the drain will actually read is asserted
    through ``read_retention_window`` in
    ``tests/integration/test_management_routes.py`` rather than through a route
    this phase would have to invent.
    """

    model_config = ConfigDict(extra="forbid")

    workspace_id: str
    retention_days: int
    updated_at: AwareDatetime


class ObservabilityContentAccessSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


class ObservabilityContentAccessState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str
    enabled: bool
    updated_at: AwareDatetime | None = None
