"""INT-018's wire contract, and the source gate on ``workspace_id``.

This lives in its own module rather than in ``schemas.py`` because the two
contracts version INDEPENDENTLY. This one is versioned by ``schema_version`` on
the broker message; the HTTP one is versioned by ``/api/v1`` in the path. A
single module holding both would make one bump look like the other's problem.
Plan 02-05 owns ``schemas.py``; nothing here is imported by it.

**This model is the source gate ``prope.db.session``'s docstring already claims
exists.** That module says the tenant identifier is "a value which, from phase 2
onward, arrives inside a broker payload", and binds it as a parameter rather than
interpolating it. Binding stops SQL injection. It does not stop a
``workspace_id`` that is 4 MB of text, or one carrying a newline, or one that is
a different workspace's identifier with whitespace appended — and
``set_config('app.workspace_id', ...)`` is what decides which tenant's rows the
transaction may touch. So the V5 input-validation control is HERE, at the
process boundary, on the way in: an explicit minimum length, an explicit maximum
length, and an explicit character class. A value that fails any of the three
never reaches ``workspace_transaction`` at all, because the drain dead-letters
an envelope that fails validation before it opens a transaction (T-02-01).

**The vocabularies are imported, never redeclared.** ``Source`` and ``Outcome``
come from ``domain.py``, whose members are byte-identical to the database CHECK
sets. A second copy here would be a second thing to keep in step with a
migration.

**Time is timezone-aware, without exception.** ``AwareDatetime`` rather than
``datetime``: a naive value compared against a ``timestamptz`` column is read
against the server's time zone, which would make an effective-dated price depend
on where the database is running. ``CallRecordDraft.__post_init__`` refuses a
naive value too; this is the same refusal one layer earlier, where it can be
dead-lettered instead of raised.

**No money crosses this wire.** ``cost``, ``currency``, ``price_row_id`` and
``cost_status`` are the writer's answer, derived from the price row in force at
the record's own ``created_at``. A publisher able to supply them is a publisher
able to supply a zero, so the envelope has no field for any of them — the same
omission ``CallRecordDraft`` makes, for the same reason.

**A-046.** This module is where bodies enter the process, and it emits no log
line and no metric. A body reaches exactly two places: ``ledger.call_body``, via
``write_records``, and the broker message this model decodes.
"""

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from prope.call_ledger.domain import CallBodyDraft, CallRecordDraft, Outcome, Source

#: The character class a ``workspace_id`` may be drawn from: ASCII letters,
#: digits, underscore and hyphen. ADR-0003's prefixed ULIDs (``wsp_...``) are a
#: strict subset. Deliberately NOT the exact ULID grammar: this is a boundary
#: gate whose job is to refuse the shapes that are dangerous downstream —
#: whitespace, control characters, quotes, anything multi-byte — not to be a
#: second implementation of the identifier format, which would go stale the day
#: the prefix vocabulary grows.
WORKSPACE_ID_PATTERN = r"^[A-Za-z0-9_-]+$"

#: Bounds, so that "a character class" is not the only thing standing between an
#: unbounded string and ``set_config``. 4 is below any real prefixed identifier;
#: 64 is comfortably above one and far below anything worth calling a payload.
WORKSPACE_ID_MIN_LENGTH = 4
WORKSPACE_ID_MAX_LENGTH = 64


class CallRecordPayload(BaseModel):
    """The call itself, as the publisher knows it — a ``CallRecordDraft`` on the wire.

    Field for field, this is what ``CallRecordDraft`` accepts, plus the two body
    fields, which travel here as scalars and are reassembled into a
    ``CallBodyDraft`` by :meth:`CallRecordEnvelope.to_draft`.

    ``extra="forbid"``: an unknown field is a version skew between a publisher
    and this consumer, and the honest response to one is a validation failure
    that dead-letters — not a silent discard of a field that might be the point
    of the message.
    """

    model_config = ConfigDict(extra="forbid")

    source: Source
    outcome: Outcome

    #: **The call's OWN time**, and the single easiest thing in this phase to get
    #: subtly wrong. Never drain time and never publish time: a call made on day
    #: 5 and drained on day 12 is priced at day 5's price row (ADR-0019), and
    #: files into day 5's ``period_month``.
    created_at: AwareDatetime

    prompt_id: str | None = None
    version_id: str | None = None
    revision_number: int | None = None
    run_id: str | None = None
    case_id: str | None = None

    #: The caller's correlation, gated on the way in for the same reason
    #: `workspace_id` is: it is customer-authored text that becomes an indexed
    #: column and a URL path segment. The bound and the class are the gateway's,
    #: restated rather than imported — call-ledger may not import from gateway,
    #: and `tests/unit/test_conversation_correlation.py` asserts the two agree so
    #: the restatement cannot drift in silence.
    conversation_id: str | None = Field(
        default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"
    )
    parent_call_id: str | None = Field(
        default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"
    )

    consumer_key_id: str | None = None
    actor_id: str | None = None
    provider_config_id: str | None = None
    upstream_model: str | None = None

    pinned: bool = False
    fallback: bool = False
    streaming: bool = False

    #: Both present or both absent. ``CallRecordDraft.__post_init__`` refuses one
    #: without the other, because usage is present or absent as a whole and half
    #: of it is neither.
    input_tokens: int | None = None
    output_tokens: int | None = None

    added_latency_ms: int | None = None
    upstream_duration_ms: int | None = None
    error_class: str | None = None

    #: The raw provider payloads. Absent for ``source=eval``, which never has a
    #: ``call_body`` row (A-055), and for a gateway call whose body was dropped
    #: under pressure (A-037). These two fields are the reason this module names
    #: A-046 in its docstring.
    request_body: str | None = None
    response_body: str | None = None
    byte_size: int | None = None


class CallRecordEnvelope(BaseModel):
    """INT-018 on the wire: one call record, addressed and versioned.

    ``extra="forbid"``, same reasoning as the payload.
    """

    model_config = ConfigDict(extra="forbid")

    #: ``Literal[1]`` rather than ``int``, deliberately. A version field that
    #: accepts any integer accepts a version this code has never seen and cannot
    #: honour, and then fails somewhere further in with a worse error. Version 2
    #: arrives as a change to this annotation and a branch in ``to_draft``, both
    #: of which are visible in a diff.
    schema_version: Literal[1]

    #: Supplied by the CALLER at request time and never generated here (A-099).
    #: It is the primary key of ``ledger.call_record``, which is what makes
    #: Phase 3's upsert-on-redelivery possible at all.
    call_id: str = Field(min_length=1, max_length=64)

    #: **The gated value.** See the module docstring: this is the one field on
    #: this wire that decides which tenant's rows a transaction may touch.
    workspace_id: str = Field(
        min_length=WORKSPACE_ID_MIN_LENGTH,
        max_length=WORKSPACE_ID_MAX_LENGTH,
        pattern=WORKSPACE_ID_PATTERN,
    )

    #: When this ENVELOPE was produced. A different fact from
    #: ``payload.created_at``, which is when the CALL happened, and the two are
    #: kept separate rather than collapsed because a backlogged publisher makes
    #: them differ and only one of them may price a record.
    #:
    #: Since D-41 it is stamped in ``enqueue()`` — when the CALLER handed the
    #: record over — rather than in the publisher, and **the drain reads it**:
    #: ``_write_group`` closes ``prope_call_ledger_write_lag_seconds`` against it
    #: after the commit, because that metric is declared *"enqueue -> durable"*.
    #: The Phase 2 sentence here said *"nothing in the write path reads this
    #: field"*, which stopped being true in the same change that gave the metric
    #: its observation site. **No value derived from it ever reaches a stored
    #: column**: pricing and ``expires_at`` still come from ``payload.created_at``
    #: alone, which is the separation the paragraph above exists to protect. It
    #: remains the field an operator reads on a dead-lettered message.
    occurred_at: AwareDatetime

    #: Which process published this. ``app`` today; ADR-0028 says ``app``
    #: publishes and never consumes, so there is exactly one value in the MVP.
    #: Bounded so it cannot become a free-text field somebody logs.
    producer: str = Field(min_length=1, max_length=32)

    payload: CallRecordPayload

    def to_draft(self) -> CallRecordDraft:
        """This envelope as the writer's input. No validation happens here.

        Everything refusable was refused by pydantic on the way in, which is the
        point of the split: by the time the drain has an envelope, the value it
        is about to hand to ``set_config`` has already passed its gate, and this
        method is a rename of fields and nothing more.

        ``CallRecordDraft.__post_init__`` will still refuse a half-reported
        usage pair, a parent named without a conversation, and a record that is
        its own parent — those rules are properties of the draft and are asserted
        where they live rather than duplicated here. All three dead-letter, which
        is the right answer: each describes a publisher that has gone wrong, and
        a chain assembled from records that broke them would be a wrong picture
        rather than a missing one.
        """
        body: CallBodyDraft | None = None
        if (
            self.payload.request_body is not None
            or self.payload.response_body is not None
            or self.payload.byte_size is not None
        ):
            body = CallBodyDraft(
                request_body=self.payload.request_body,
                response_body=self.payload.response_body,
                byte_size=self.payload.byte_size,
            )

        return CallRecordDraft(
            call_id=self.call_id,
            workspace_id=self.workspace_id,
            source=self.payload.source,
            outcome=self.payload.outcome,
            created_at=self.payload.created_at,
            prompt_id=self.payload.prompt_id,
            version_id=self.payload.version_id,
            revision_number=self.payload.revision_number,
            run_id=self.payload.run_id,
            case_id=self.payload.case_id,
            conversation_id=self.payload.conversation_id,
            parent_call_id=self.payload.parent_call_id,
            consumer_key_id=self.payload.consumer_key_id,
            actor_id=self.payload.actor_id,
            provider_config_id=self.payload.provider_config_id,
            upstream_model=self.payload.upstream_model,
            pinned=self.payload.pinned,
            fallback=self.payload.fallback,
            streaming=self.payload.streaming,
            input_tokens=self.payload.input_tokens,
            output_tokens=self.payload.output_tokens,
            added_latency_ms=self.payload.added_latency_ms,
            upstream_duration_ms=self.payload.upstream_duration_ms,
            error_class=self.payload.error_class,
            body=body,
        )

    @classmethod
    def from_draft(
        cls, draft: CallRecordDraft, *, occurred_at: datetime, producer: str = "app"
    ) -> "CallRecordEnvelope":
        """The inverse, for the publish side and for tests.

        A publisher that built the envelope by hand would be a second place the
        wire contract is written down. It is built from the draft instead, so
        the round trip ``draft -> envelope -> draft`` is a property this module
        owns end to end.
        """
        return cls(
            schema_version=1,
            call_id=draft.call_id,
            workspace_id=draft.workspace_id,
            occurred_at=occurred_at,
            producer=producer,
            payload=CallRecordPayload(
                source=draft.source,
                outcome=draft.outcome,
                created_at=draft.created_at,
                prompt_id=draft.prompt_id,
                version_id=draft.version_id,
                revision_number=draft.revision_number,
                run_id=draft.run_id,
                case_id=draft.case_id,
                conversation_id=draft.conversation_id,
                parent_call_id=draft.parent_call_id,
                consumer_key_id=draft.consumer_key_id,
                actor_id=draft.actor_id,
                provider_config_id=draft.provider_config_id,
                upstream_model=draft.upstream_model,
                pinned=draft.pinned,
                fallback=draft.fallback,
                streaming=draft.streaming,
                input_tokens=draft.input_tokens,
                output_tokens=draft.output_tokens,
                added_latency_ms=draft.added_latency_ms,
                upstream_duration_ms=draft.upstream_duration_ms,
                error_class=draft.error_class,
                request_body=draft.body.request_body if draft.body else None,
                response_body=draft.body.response_body if draft.body else None,
                byte_size=draft.body.byte_size if draft.body else None,
            ),
        )
