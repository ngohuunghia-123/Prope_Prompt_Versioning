"""The call-ledger vocabulary, as Python values.

Four vocabularies and four value objects. The vocabularies are ``StrEnum`` and
their members' values are **byte-identical to the database CHECK sets** in
``alembic/versions/0002_call_record.py`` — ``priced`` / ``unpriced`` /
``not_applicable``, ``reported`` / ``unknown``, ``gateway`` / ``eval``, ``ok`` /
``fallback`` / ``truncated`` / ``caller_error`` / ``upstream_error``. A native
PostgreSQL ``ENUM`` was rejected (Pitfall 4); the vocabulary lives in a ``CHECK``
and is mirrored here so Python can type-check against it.

These values stay literal ASCII at rest. ADR-0053 puts Vietnamese behind an i18n
layer that translates a machine ``code`` at the API edge — a status is never
translated in the database, because a stored status is a fact and not a label.

**No field on any object here is a binary floating-point number.** Money is
``decimal.Decimal`` end to end (Pitfall 5) and every timestamp is a
timezone-aware ``datetime`` (Pitfall 7): a naive value compared against a
``timestamptz`` column is interpreted against the server's time zone, so
CL-03's day-5/day-12 arithmetic would depend on where the database is running.

``CallRecordDraft`` carries what a *caller* knows. It deliberately does not
carry ``cost``, ``currency``, ``price_row_id`` or ``cost_status``: those four
are the writer's answer, derived from the price row in force at this draft's own
``created_at``, and a caller able to supply them is a caller able to supply a
zero. ``usage_status`` is likewise derived rather than declared — it is a
restatement of whether the provider returned a usage object, which the token
fields already say.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class CostStatus(StrEnum):
    """``ck_call_record_cost_status_values``. There is no fourth state."""

    PRICED = "priced"
    UNPRICED = "unpriced"
    NOT_APPLICABLE = "not_applicable"


class UsageStatus(StrEnum):
    """``ck_call_record_usage_status_values``.

    ``UNKNOWN`` means the provider returned no usage object. It does not mean
    zero tokens: ``ck_call_record_unknown_usage_is_null`` requires both token
    columns to be NULL in that case, because an absent figure asks a question
    and a zero answers it (ADR-0019).
    """

    REPORTED = "reported"
    UNKNOWN = "unknown"


class Source(StrEnum):
    """``ck_call_record_source_values``.

    One table, so there is one price path, one spend total and one answer to
    "what did this workspace spend" (A-098). A ``EVAL`` record never has a
    ``call_body`` row (A-055).
    """

    GATEWAY = "gateway"
    EVAL = "eval"


class Outcome(StrEnum):
    """``ck_call_record_outcome_values`` (ADR-0013).

    ``TRUNCATED`` carries a real cost: the provider generated tokens and charged
    for them.
    """

    OK = "ok"
    FALLBACK = "fallback"
    TRUNCATED = "truncated"
    CALLER_ERROR = "caller_error"
    UPSTREAM_ERROR = "upstream_error"


@dataclass(frozen=True, slots=True)
class PriceRow:
    """One row of ``ledger.price_table``, as resolved for a given instant.

    Frozen because the table it mirrors is append-only by privilege (T-006). A
    price is superseded by a new row with a later ``effective_from``; nothing —
    in the database or here — edits one.
    """

    price_row_id: str
    input_price_per_1k: Decimal
    output_price_per_1k: Decimal
    currency: str
    effective_from: datetime


@dataclass(frozen=True, slots=True)
class CallBodyDraft:
    """The raw provider payloads, when they survive.

    ``text`` rather than JSON at rest, because a malformed body is exactly the
    one worth keeping. Nothing reads this table in the MVP (ADR-0018); its only
    scheduled reader is the retention delete.
    """

    request_body: str | None = None
    response_body: str | None = None
    byte_size: int | None = None


@dataclass(frozen=True, slots=True)
class CallRecordDraft:
    """One call, as the caller knows it, before it is priced.

    ``call_id`` is supplied by the CALLER at request time and not generated here
    (A-099) — that is what makes a broker redelivery safe, because the writer
    can upsert on it rather than counting a record into a workspace's spend
    twice.

    ``created_at`` is the call's OWN time and is required. ``ledger.call_record``
    has no column default for it, deliberately: a default would price a
    backlogged record at drain time, and a call made on day 5 and written on day
    12 would be priced at day 12 (ADR-0019). This is the single easiest way to
    get CL-03 subtly wrong.
    """

    call_id: str
    workspace_id: str
    source: Source
    outcome: Outcome
    created_at: datetime

    prompt_id: str | None = None
    version_id: str | None = None
    revision_number: int | None = None
    run_id: str | None = None
    case_id: str | None = None
    consumer_key_id: str | None = None
    actor_id: str | None = None
    provider_config_id: str | None = None
    upstream_model: str | None = None

    pinned: bool = False
    fallback: bool = False
    streaming: bool = False

    #: Both NULL together when the provider returned no usage object. Never a
    #: zero standing in for an absent count.
    input_tokens: int | None = None
    output_tokens: int | None = None

    added_latency_ms: int | None = None
    upstream_duration_ms: int | None = None
    error_class: str | None = None

    #: Absent for ``source=eval``, which never has a body row (A-055), and for a
    #: gateway call whose body was dropped under pressure (A-037).
    body: CallBodyDraft | None = field(default=None)

    def __post_init__(self) -> None:
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

    @property
    def usage_status(self) -> UsageStatus:
        """Derived, never declared. Mirrors ``ck_call_record_unknown_usage_is_null``."""
        if self.input_tokens is None:
            return UsageStatus.UNKNOWN
        return UsageStatus.REPORTED


@dataclass(frozen=True, slots=True)
class WriteResult:
    """What landed, counted from the stored encoding rather than from intent.

    ``unknown`` counts records whose provider returned no usage object — the
    count CL-11 requires to be reportable alongside the total. It is derived
    from ``usage_status``, never by asking whether a token column is NULL,
    so Phase 2's ``get_run_totals`` can compute the same number with a
    ``count(*) FILTER (WHERE usage_status = 'unknown')`` and get the same
    answer.
    """

    priced: int = 0
    unpriced: int = 0
    unknown: int = 0
    bodies_written: int = 0

    @property
    def total(self) -> int:
        return self.priced + self.unpriced + self.unknown
