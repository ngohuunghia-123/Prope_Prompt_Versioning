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
carrying its own :class:`ErrorCode`. A ``model_validator`` would collapse all of
them into one ``validation_failed``, and ADR-0053 makes the ``code`` the thing
the client actually renders, so a merged code is a message the SPA cannot write.
"""

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, PlainSerializer

from prope.session_auth import SESSION_REQUIRED as SESSION_REQUIRED_CODE

__all__ = [
    "DEFAULT_PAGE_LIMIT",
    "MAX_PAGE_LIMIT",
    "MONEY_SCALE_PLACES",
    "ApiError",
    "ErrorCode",
    "ErrorEnvelope",
    "PageRequest",
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


class ErrorCode(StrEnum):
    """The closed set of machine codes the envelope's ``code`` may carry.

    **A ``StrEnum`` and not a free string, because of ADR-0053.** The interface
    language is Vietnamese only, behind an i18n layer with a keyed catalogue and
    **no literal display strings** — the API returns a machine ``code`` and the
    client translates it. A route that invented a code would therefore render as
    nothing at all in the SPA, and it would do so silently. Closing the set here
    makes an unknown code impossible to produce rather than merely unlikely.

    ``domain.py`` states the same rule for statuses at rest: a status that is
    stored or transmitted is a **fact**, not a label, and it stays literal ASCII
    wherever it travels.

    ``SESSION_REQUIRED`` takes its value from ``prope.session_auth`` rather than
    repeating the literal, so the refusal and the vocabulary cannot drift.
    """

    SESSION_REQUIRED = SESSION_REQUIRED_CODE
    NOT_FOUND = "not_found"
    VALIDATION_FAILED = "validation_failed"
    PRICE_EFFECTIVE_RANGE_AMBIGUOUS = "price_effective_range_ambiguous"
    PRICE_BOTH_PRICES_ARE_ZERO = "price_both_prices_are_zero"
    PRICE_IS_NEGATIVE = "price_is_negative"
    MONEY_SCALE_EXCEEDED = "money_scale_exceeded"
    SPEND_CEILING_LIMIT_IS_NEGATIVE = "spend_ceiling_limit_is_negative"
    SPEND_CEILING_LIMIT_NEEDS_CURRENCY = "spend_ceiling_limit_needs_currency"
    RETENTION_WINDOW_NOT_POSITIVE = "retention_window_not_positive"
    INTERNAL_ERROR = "internal_error"


class ApiError(BaseModel):
    """A-045's error object: ``{code, message, details?, request_id}``.

    ``code`` is what the client renders (ADR-0053). ``message`` is for the
    person reading a log or a test failure and is **English on purpose** — it is
    never displayed, so translating it would be translating something nobody
    sees. ``details`` carries structured values the caller already sent, so a
    client can point at the field that was wrong; it never carries a constraint
    name, a SQL fragment or a driver's words (T-02-34). ``request_id``
    is INT-024's requirement for a ``5xx``, and is filled for every refusal
    rather than only those, because a client reporting a ``422`` it did not
    expect is worth being able to find.
    """

    model_config = ConfigDict(extra="forbid")

    code: ErrorCode
    message: str
    details: dict[str, Any] | None = None
    request_id: str | None = None


class ErrorEnvelope(BaseModel):
    """The whole of A-045's error shape: ``{error: {...}}``. There is one.

    Every refusal from every management route in every module renders as this,
    including the ones FastAPI would otherwise answer with its own
    ``{"detail": ...}``. ``prope.app`` registers the handlers that make that
    true. The gateway is exempt and returns OpenAI-shaped errors (A-026,
    INT-022) — that exemption is the gateway's, in Phase 19, and nothing here.
    """

    model_config = ConfigDict(extra="forbid")

    error: ApiError


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
    """

    model_config = ConfigDict(extra="forbid")

    retention_days: int


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
