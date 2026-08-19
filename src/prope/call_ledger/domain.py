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

    ``PLAYGROUND`` is the internal caller added in revision 0020: a person
    talking to a *draft* revision from the SPA over a session cookie, before
    anything is approved. It carries a ``version_id`` like a gateway call and
    **never a ``consumer_key_id``**, because no key authenticated it — see
    ``ck_call_record_playground_calls_are_internal``, which is where that is
    enforced rather than remembered. Unlike ``EVAL`` it may carry a body: a
    trial's turns exist nowhere else, whereas a suite's inputs are already in
    the suite.
    """

    GATEWAY = "gateway"
    EVAL = "eval"
    PLAYGROUND = "playground"

    #: ``observed`` is the fourth caller, added in revision 0026 (ADR-0060). The
    #: gateway forwarded a call it could not resolve (ADR-0059): no prompt, no
    #: revision, no approval — somebody else's prompt, running through Prope,
    #: recorded so it can be discovered.
    #:
    #: It exists for ``PLAYGROUND``'s reason at the other end of the same metric.
    #: The playground got its own value because filing it as ``gateway`` would
    #: corrupt the DENOMINATOR of "100% of gateway calls record a version ID" with
    #: traffic no consumer made; this gets one because filing it as ``gateway``
    #: would corrupt the NUMERATOR with traffic no revision served. Between them,
    #: ``ck_call_record_gateway_calls_carry_version_id`` goes on meaning exactly
    #: what it says.
    #:
    #: ``ck_call_record_observed_calls_name_no_revision`` is the mirror of the
    #: playground's constraint: prompt, version, revision, run and case are all
    #: NULL, ``consumer_key_id`` is NOT NULL because a real key authenticated
    #: this, and ``pinned``/``fallback`` are both false because both are
    #: properties of a revision that does not exist.
    #:
    #: **The observed BODY is not in ``call_body``.** It has a reader, and
    #: ADR-0018 gives that table none; it lives in ``observation.observation``.
    OBSERVED = "observed"


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
    #: The floor under one request's cost, in ``currency``. Zero means no floor,
    #: which is what every row written before migration 0017 means and what the
    #: column defaults to — so the default here is the schema's default, not a
    #: convenience. ``compute_cost`` takes ``max(computed, this)``.
    minimum_charge_per_request: Decimal = Decimal(0)


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

    #: The CALLER's correlation, and the only two fields on this record whose
    #: meaning is defined outside Prope. `conversation_id` groups the calls one
    #: end-user conversation made; `parent_call_id` names the call this one
    #: followed from, so a chain that fans out to sub-agents reads as a tree
    #: rather than as whatever order the clock happened to record.
    #:
    #: Both are NULL for every caller that has not adopted them, which is every
    #: caller until they change one line — and for every non-gateway source,
    #: since an eval dispatch and a playground trial are not conversations.
    #:
    #: `parent_call_id` is a **value, not a foreign key**, for the reason
    #: `property_history.target_id` is: the parent may have been retained away
    #: while the child survives, and a constraint would then force a delete that
    #: ADR-0018 keeps the ledger from performing. An unmatched parent renders as
    #: a root, which is the honest picture of a chain whose head has expired.
    conversation_id: str | None = None
    parent_call_id: str | None = None
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
        if self.parent_call_id is not None and self.conversation_id is None:
            raise ValueError(
                f"{self.call_id} names a parent but no conversation; the chain is assembled by "
                "conversation, so a parent with nothing to hang it in would be stored and never "
                "read"
            )
        if self.parent_call_id == self.call_id:
            raise ValueError(f"{self.call_id} is its own parent, which is not a chain but a loop")
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

    ``duplicates`` is derived from **rows offered minus ``call_id``s returned by
    the idempotent insert** (D-33, D-35) — the database's own answer to "how many
    of these were already here", not the writer's opinion about which envelope
    looked like a redelivery. It is the same number
    ``prope_call_ledger_duplicate_call_id_total`` moves by, so a caller that needs
    it per batch does not have to read a process-global counter to get it.
    ``priced``, ``unpriced`` and ``unknown`` continue to describe the whole batch
    OFFERED, which is why ``total`` can exceed the rows this call created.
    """

    priced: int = 0
    unpriced: int = 0
    unknown: int = 0
    bodies_written: int = 0
    duplicates: int = 0

    @property
    def total(self) -> int:
        return self.priced + self.unpriced + self.unknown
