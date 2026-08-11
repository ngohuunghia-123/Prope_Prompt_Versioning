"""The eighteen declared call-ledger metrics, and the project-wide log allow-list. ADR-0030.

**The COUNTERS here are Phase 2's and only those** — every metric below is
``prope_call_ledger_*``, and a module's own counters live in its own
``observability.py`` (``src/prope/property_history/observability.py`` is the
first). **``LOGGABLE_FIELDS`` is not scoped that way**: it is one project-wide
allow-list, and Phase 4 is the first phase to extend it from a second module.

**A-046, first, because everything below is constrained by it.** No request
body, response body, prompt body, fallback answer, provider credential, or any
other variable value reaches a log line or a metric label from this module or
from any module that uses it. Metric label cardinality is bounded by
construction: every label declared here has a CLOSED set of values fixed in
source, and ``workspace_id`` — the highest-cardinality identifier in the system
and the one most tempting to add — is deliberately never a label. What a log
line may carry is an ALLOW-LIST (see ``LOGGABLE_FIELDS``), never a deny-list of
field names, because a deny-list fails silently the first time a field is
renamed.

**Eighteen: the lock file's seventeen, plus ``prope_call_ledger_dlq_depth``.**
``docs/modules/call-ledger.lock.yml``'s ``observability_requirements.metrics``
block lists seventeen; its ``security_requirements`` T-005 requires a gauge on
the dead-letter queue's depth and alerts on any non-zero value, and that
eighteenth name appears nowhere in the metrics block. That omission is raised as
``docs/brainstorm/open_questions/OQ-022.md`` rather than absorbed, and the gauge
ships here because a mitigation that is declared in one section and absent from
the other is a mitigation nobody built.

**All eighteen are defined HERE, at import, even where nothing increments them
yet** (D-40). Twelve of them get their increment sites in plans 03-02
(``write_records``), 03-03 (``seams.py``) and 03-04 (``worker.py``), and that is
not a reason to define them later. A metric that first appears the moment it goes
non-zero has no baseline, and no alert can be written against a series that does
not exist. ``prope_call_ledger_missing_version_id_total`` is the sharpest case,
because its whole job is to be zero: ``REGISTRY.get_sample_value`` returns
``None`` — not ``0.0`` — for a metric nothing has touched, so a "must stay 0"
metric defined lazily is indistinguishable from one that was never wired.

**There is still no ``/metrics`` endpoint.** It arrives in plan 03-04, on ``app``
alone, and ``prometheus_client``'s registry is per process — so until then these
are observable from tests and from nothing else. The list of metrics that stay
unscrapable or partial even after that route exists is ``OQ-026``'s subject, not
this module's.
"""

import logging
import sys

import structlog
from prometheus_client import Counter, Gauge, Histogram

#: The allow-list A-046 requires: the ONLY keys any publish-path or drain-path
#: log line may carry beside its event name. Positive, never a deny-list — a
#: deny-list of forbidden field names passes the first time a body is carried on
#: a field nobody thought to forbid, which is every field that has not been
#: invented yet.
#:
#: Every entry is an identifier or a closed-vocabulary token. None of them is a
#: body, a prompt, an answer, or a credential.
LOGGABLE_FIELDS = frozenset(
    {
        "event",
        "call_id",
        "workspace_id",
        "reason",
        "queue",
        "delivery_tag",
        "group_size",
        "window_size",
        #: Added by plan 02-04 on plan 02-03's handoff. ``supervisor.job_crashed``
        #: carries it, and its values are the job-name constants fixed in
        #: ``prope.worker``'s source — a closed set of two, not an identifier and
        #: not a body. Recorded here rather than left in ``deferred-items.md``
        #: because an allow-list with a field outside it is an allow-list
        #: somebody has already stopped believing.
        "job",
        #: Added by plan 04-02 (property-history). Its classification token
        #: travels as ``rejection_reason`` so that ``reason`` above keeps
        #: call-ledger's meaning — a closed-vocabulary token — exclusively.
        #:
        #: **This allow-list cannot express what property-history needs of it.**
        #: The lock forbids logging ``history_event.reason``, a user-authored
        #: column that happens to share a name with call-ledger's token, so
        #: ``log.info("property_history.…", reason=…)`` would pass
        #: ``test_every_logged_key_is_in_the_allow_list`` without a murmur. What
        #: actually protects the column today is the marker tests on the three
        #: driven paths, and convention everywhere else. Phase 6's AC-8
        #: full-corpus source gate is where the predicate belongs; recorded here
        #: rather than left implied, because an allow-list trusted for something
        #: it does not do is worse than one nobody trusts.
        "rejection_reason",
        #: The NAME of a details key that failed the allow-list, never its value.
        "detail_key",
        #: A ``hev_``-prefixed ULID. The event's id is logged; its content is not.
        "event_id",
        #: A registry action name — the closed 31-value vocabulary (A-120).
        "action",
        #: The registry's ``target_type``, closed by ``fk_history_event_action``.
        "target_type",
        #: A prefixed ULID identifying the subject. A value, not a reference.
        "target_id",
        #: A ``prm_``-prefixed ULID. An identifier, never a prompt body.
        "scope_prompt_id",
        #: A ``usr_``-prefixed ULID, opaque and surviving a tombstone (ADR-0054).
        "actor_id",
        #: One of five module ids, a CHECK set in the registry table. Logged by
        #: nothing today; an allow-list is permissive, so this is a pre-listing.
        "writing_module",
    }
)

#: The rule that generated both bucket sets below, written once and referenced by
#: the second: ``histogram_quantile`` interpolates linearly INSIDE the bucket that
#: holds the quantile, so **every number this project will ever assert on must be
#: a bucket EDGE**. A target that falls in a bucket's interior can only ever be
#: answered to that bucket's width, and a metric that cannot fail its own target
#: is not a measurement.
#:
#: ``prometheus_client``'s defaults — ``(0.005, 0.01, 0.025, 0.05, 0.075, 0.1,
#: 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, +Inf)`` — are shaped for HTTP
#: request latency, which is the one thing neither of this module's histograms
#: measures. Their first edge is five times ABOVE CL-12's p95 < 1 ms enqueue
#: target, so every observation would land in the first bucket and the p95 would
#: read "somewhere under 5 ms" forever.
#:
#: ``0.001`` is here because CL-12 asserts p95 < 1 ms. Everything else is
#: resolution: the timed span is one ``put_nowait``, one clock read, two counter
#: increments and — at the cap — a 256 KiB ``str.encode()``, so the interesting
#: range is 10 µs to 1 ms and seven of the eleven edges sit inside it. Above
#: 50 ms the answer is "the event loop stalled", and one more edge would not
#: change what anybody did about it.
#:
#: Cardinality: 11 edges × 2 ``source`` values = 22 series, far inside ADR-0030's
#: rule and inside the registry walk in
#: ``tests/broker/test_publish_confirm_failures.py``.
#:
#: A tunable judgement, not a repo decision, recorded so that changing it is a
#: visible act. Unvalidated at real scale, like every number of this kind here.
ENQUEUE_DURATION_BUCKETS = (
    0.00005,
    0.0001,
    0.00025,
    0.0005,
    0.00075,
    0.001,
    0.0025,
    0.005,
    0.01,
    0.05,
    float("inf"),
)

#: The same rule, applied to the other end of the range. ``2.0``, ``10.0`` and
#: ``30.0`` are edges because ``performance_requirements`` states write lag
#: p95 < 2 s and p99 < 10 s and ``LedgerWriteLagHigh`` fires at p95 > 30 s for
#: ten minutes — three numbers this project asserts on, so three edges.
#:
#: Steady state is one drain window (``WINDOW_MS``, 250 ms) plus one write, so
#: four edges under a second keep a healthy p95 legible instead of collapsing
#: into "under 2 s". ``60`` and ``300`` are what distinguish "the threshold was
#: crossed" from "there is a backlog", against the stated *"60 s of traffic
#: drained within 60 s"* target — which is exactly the range in which somebody
#: decides whether it is clearing.
#:
#: Unlabelled, so 12 series. A tunable judgement, not a repo decision, recorded
#: so that changing it is a visible act. Unvalidated at real scale.
WRITE_LAG_BUCKETS = (
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.0,
    5.0,
    10.0,
    30.0,
    60.0,
    300.0,
    float("inf"),
)

#: ``body_dropped_total``'s ``reason`` values, chosen in exactly two places in
#: ``prope.call_ledger`` and nowhere else, in the discipline
#: ``enqueue._classify_publish_failure``'s docstring models: one place a value is
#: chosen, so a fourth cannot appear by accident.
#:
#: **The declared set is ``queue_full | oversize`` and neither of those is what
#: the fallback does.** There is no in-process queue to be full — ADR-0041
#: deleted the two-lane in-process queue the label was written for — and a body
#: dropped because its record fell back to a direct PostgreSQL write is not
#: oversize. So ``fallback`` is introduced, and ``queue_full`` is deliberately
#: NOT declared as a constant: it has no producer, and a reused value for a queue
#: that does not exist is worse than a declared deviation.
#: **The conflict is raised as ``OQ-022`` against
#: ``docs/modules/call-ledger.lock.yml`` ``observability_requirements.metrics``,
#: not patched into the spec.**
BODY_DROP_REASON_FALLBACK = "fallback"

#: The body was over ``enqueue.MAX_BODY_BYTES``, or could not be encoded to be
#: measured against it. The record itself always continues with ``body=None``
#: (D-29): metadata is never dropped for a body's sake.
BODY_DROP_REASON_OVERSIZE = "oversize"

#: CL-12's own metric: the whole of the caller's span, measured in the caller's
#: process. ``source`` is ``gateway`` | ``eval``, the ``Source`` vocabulary, which
#: is a database CHECK set and therefore closed.
#:
#: It covers the WHOLE of ``enqueue()`` — the body sizing, the clock read, the
#: ``put_nowait`` and the counter increments — because CL-12's claim is about what
#: the caller waits for, and a measurement that excluded the encode would exclude
#: the largest term in it.
enqueue_duration_seconds = Histogram(
    "prope_call_ledger_enqueue_duration_seconds",
    "Wall time inside enqueue(), by source. The whole of the caller's span.",
    labelnames=("source",),
    buckets=ENQUEUE_DURATION_BUCKETS,
)

#: INT-018's enqueue counter. ``source`` is ``gateway`` | ``eval`` — the
#: ``Source`` vocabulary, which is a database CHECK set and therefore closed.
#: ``outcome`` here is the fate of the HANDOFF, not the ``Outcome`` vocabulary:
#: ``accepted`` when the record entered the buffer, ``dropped`` when the buffer
#: was full or already shut down. Two values, fixed in source.
#:
#: **``oversize`` is NOT a third value, and that is decided here rather than left
#: open.** ``outcome`` means *the fate of the record*; ``oversize`` would mean
#: *the fate of the body*. Two subjects in one label makes the counter unsummable
#: — ``sum(enqueued_total)`` would stop being "records offered", which is the one
#: thing it is for — and D-29 is explicit that a record with an oversize body
#: *always continues with ``body=None``*, so the record IS accepted. The oversize
#: event is fully visible on ``body_dropped_total``, whose subject IS the body.
#: Written here so the next reader does not "complete" the vocabulary.
enqueued_total = Counter(
    "prope_call_ledger_enqueued_total",
    "Call records handed to enqueue(), by source and by what became of the handoff.",
    labelnames=("source", "outcome"),
)

#: D-21's control. The ``reason`` label has exactly three values and the lock
#: file declares the set: ``unroutable`` | ``nacked`` | ``timeout``. They are the
#: three shapes a publisher confirm can fail in, and the publish path classifies
#: into exactly these and never invents a fourth.
publish_failed_total = Counter(
    "prope_call_ledger_publish_failed_total",
    "Publisher confirms that did not arrive as an ack, by reason.",
    labelnames=("reason",),
)

#: What actually reached ``ledger.call_record``. ``source`` only — no
#: ``workspace_id``, see the module docstring.
written_total = Counter(
    "prope_call_ledger_written_total",
    "Call records committed to ledger.call_record by the drain, by source.",
    labelnames=("source",),
)

#: **Unlabelled**, and the declared ``lane = metadata | body`` label is not here.
#: That label describes the two IN-PROCESS lanes ADR-0041 deleted; a broker queue
#: has one depth and no lanes. The deviation rides ``OQ-022``.
#:
#: Read from a passive re-declare of ``prope.call_record`` on an interval, in
#: ``worker`` — plan 03-04's job, not this module's. It is a gauge and not a
#: counter because a depth is a level: it goes down.
queue_depth = Gauge(
    "prope_call_ledger_queue_depth",
    "Messages ready for delivery on prope.call_record, as the broker reports them.",
)

#: T-005's mitigation, and **the eighteenth metric** — required by
#: ``security_requirements`` and absent from the metrics block the ROADMAP counts
#: at seventeen (``OQ-022``). *Any* non-zero value is an alert: a dead-lettered
#: record is genuinely absent from ``ledger.call_record``, and after D-30 this
#: gauge — not ``metadata_dropped_total`` — is the signal that says so.
dlq_depth = Gauge(
    "prope_call_ledger_dlq_depth",
    "Messages sitting in prope.call_record.dlq. Any non-zero value is an alert.",
)

#: Declared *"enqueue -> durable"*, so it is measured from the instant the caller
#: handed the record over (``HandoffItem.occurred_at``, stamped in ``enqueue()``
#: per D-41) and not from the instant the publisher published it. Measuring from
#: the publish moment would put the handoff dwell — the one interval the
#: direct-write fallback exists to protect — outside the one metric named after
#: it.
#:
#: **Observed with ``max(0.0, lag)``, always.** ``occurred_at`` is stamped in
#: ``app`` and the durable moment is read in ``worker``; ``prometheus_client``
#: accepts a negative observation without complaint, decrementing ``_sum`` while
#: incrementing ``_count``, which makes ``rate(_sum[5m])`` negative and any
#: average-latency panel built on it nonsense. Stated positively: this metric is
#: only meaningful because ``app`` and ``worker`` share a host (ADR-0033).
#:
#: Unlabelled, for ``metadata_dropped_total``'s reason.
write_lag_seconds = Histogram(
    "prope_call_ledger_write_lag_seconds",
    "Seconds from enqueue() to the record being durable in PostgreSQL.",
    buckets=WRITE_LAG_BUCKETS,
)

#: A-037's best-effort body, counted when it is not kept. **Once per record, never
#: once per body field**: AC-1's stated equality is *"body_dropped_total equals the
#: number missing from ledger.call_body"*, and one increment per dropped pair is
#: what makes that arithmetic hold.
#:
#: ``reason`` is ``fallback`` | ``oversize`` — see ``BODY_DROP_REASON_FALLBACK``
#: above for why the declared ``queue_full`` has no producer and is not declared.
body_dropped_total = Counter(
    "prope_call_ledger_body_dropped_total",
    "Call bodies not stored, by reason. The record itself is never dropped with them.",
    labelnames=("reason",),
)

#: **Records that exist NOWHERE.** After CL-01 this counter means what ADR-0041
#: says it means — *both* the broker and the database were unavailable — and
#: nothing else. It is unlabelled because every such drop is the same kind of
#: event regardless of who it belonged to, and a label here would be the
#: cardinality leak the module docstring refuses.
#:
#: **There are exactly three kinds of event behind it, and a dead-letter is not
#: one of them.** They are: (1) **the handoff refused the record** — full, already
#: shut down, or the failure nobody predicted, all three in ``enqueue()``; (2)
#: **the direct write did not land** — the database refused it
#: (``fallback.build_fallback_writer``) or something nobody predicted escaped the
#: publisher's handling of it (``enqueue.publish_or_fall_back``); and (3) **the
#: stop deadline expired with records still buffered**
#: (``enqueue.drain_handoff_on_stop``), counted once per record. Plan 03-02
#: removes the two increments in ``drain.py`` that make a dead-letter a fourth
#: kind today.
#:
#: The reason that removal matters is the alert: ``LedgerMetadataDropped`` fires
#: on ``> 0`` and **pages immediately**. A dead-lettered record is in
#: ``prope.call_record.dlq`` with a 30-day TTL, and the signal for it is
#: ``dlq_depth > 0``, a ticket. A page that fired on one malformed envelope would
#: be a page people learn to close, which is the failure mode that would cost the
#: one alert in this module that is genuinely worth waking somebody for.
metadata_dropped_total = Counter(
    "prope_call_ledger_metadata_dropped_total",
    "Call records that reached neither the broker nor PostgreSQL. Must stay 0.",
)

#: ADR-0041's fallback, counted. **Not "must stay 0"** — a rising value is a
#: broker problem being correctly absorbed, and it is the signal that metadata is
#: still safe while ``metadata_dropped_total`` stays at zero. The two are read
#: together: this one rising alone is a degraded write path; both rising is data
#: loss.
#:
#: It is also the only series that rises during the outage ADR-0041 was written
#: about, because ``publish_failed_total``'s three reasons all require a broker
#: that ANSWERED and refused. That asymmetry is the fifth clause of ``OQ-022``.
fallback_direct_write_total = Counter(
    "prope_call_ledger_fallback_direct_write_total",
    "Call records written straight to PostgreSQL because the broker would not take them.",
)

#: At-least-once delivery working, read from ``AbstractIncomingMessage.redelivered``
#: — the BROKER's own view of what it re-sent. Increment site is the drain, plan
#: 03-02. Paired with ``duplicate_call_id_total`` below, and deliberately not
#: derived from it: ``LedgerDuplicateCallIds`` reads the two together, and that
#: comparison is impossible if either side is computed from the other.
redelivered_total = Counter(
    "prope_call_ledger_redelivered_total",
    "Messages the broker delivered more than once, as the broker reports them.",
)

#: The DATABASE's own view of what was already there: rows offered minus
#: ``call_id``s returned by the idempotent insert. Increment site is
#: ``write_records``, plan 03-02, which is what gives all three of its callers —
#: the drain, the fallback and ``price_usage`` — the count for free (INT-019).
#:
#: Duplicates that track redeliveries are the broker working; duplicates that
#: exceed them are a caller generating ``call_id``s badly.
duplicate_call_id_total = Counter(
    "prope_call_ledger_duplicate_call_id_total",
    "Records the writer offered that were already present, by call_id.",
)

#: **The closest thing in this module to an unbounded label set, and it ships
#: because the lock file declares it.** ``provider_config_id`` and
#: ``upstream_model`` are both bounded in practice — a workspace configures a
#: handful of providers and a handful of models — but they are identifiers rather
#: than a vocabulary, so the bound is a fact about deployments and not about the
#: source.
#:
#: The consequence worth writing down: **a ``provider_config_id`` resolves to
#: exactly one workspace**, which matters the moment plan 03-04 serves this
#: registry over an unauthenticated ``/metrics`` route. Plan 03-04 raises
#: ``OQ-023`` against that exposure. A declared label is not dropped here to avoid
#: raising the question.
#:
#: Increment site is ``write_records``, plan 03-02.
unpriced_total = Counter(
    "prope_call_ledger_unpriced_total",
    "Records stored with cost_status=unpriced, by provider config and upstream model.",
    labelnames=("provider_config_id", "upstream_model"),
)

#: Records whose provider returned no usage object at all. Never a zero standing
#: in for an absent count (ADR-0019) — the tokens are NULL and this counter is how
#: often that happened. Increment site is ``write_records``, plan 03-02.
unknown_usage_total = Counter(
    "prope_call_ledger_unknown_usage_total",
    "Records stored with usage_status=unknown, by source.",
    labelnames=("source",),
)

#: **Must stay 0**, and it is the success metric *"100% of gateway calls record a
#: version ID"* expressed as a series. Its increment site arrives with plan
#: 03-02's explicit refusal in ``write_records``: today a ``source=gateway`` draft
#: with a NULL ``version_id`` dies as an ``IntegrityError`` under
#: ``ck_call_record_gateway_calls_carry_version_id`` and dead-letters under a
#: CONSTRAINT's name rather than under this counter's.
#:
#: It is defined now anyway, and it is the sharpest case for D-40: a metric whose
#: whole job is to be zero is exactly the metric that must exist before it is
#: needed, because ``REGISTRY.get_sample_value`` answers ``None`` — not ``0.0`` —
#: for a metric nothing has touched.
missing_version_id_total = Counter(
    "prope_call_ledger_missing_version_id_total",
    "Gateway call records offered without a version_id. Must stay 0.",
)

#: INT-020's control, in the lock file's declared shape: **all three branches**,
#: labelled ``result = allowed | refused | failed_open``.
#:
#: **``result`` is a THIRD vocabulary and it is neither of the other two.** It is
#: not ``domain.Outcome``, which is a call's fate at the provider, and it is not
#: ``enqueued_total``'s ``outcome`` above, which is the fate of the HANDOFF. This
#: one names the fate of a single **check**: ``allowed`` when the ceiling was
#: evaluated and the workspace may run, ``refused`` when it was evaluated and the
#: workspace may not, ``failed_open`` when it could not be evaluated at all and
#: the run was allowed anyway. Three values, chosen in exactly one place —
#: ``seams.CeilingCheckResult`` — so a fourth cannot appear by accident. Spelled
#: out because a reader who has met the other two vocabularies will otherwise
#: assume this is one of them.
#:
#: **The three are mutually exclusive and jointly exhaustive**, one increment per
#: call, which is what makes ``failed_open`` readable as a share of the total
#: rather than as a bare number nobody can size. A single site keyed off
#: ``decision.allowed`` could not have produced them: ``allowed`` is ``True`` on
#: two different branches — the workspace was under its ceiling, and the check
#: could not be evaluated — and telling those two apart is the whole job.
#:
#: **AC-7's control, and the reason the fail-open BRANCH is allowed to exist.**
#: INT-020 makes ``check_spend_ceiling`` the one seam in Prope that fails open: a
#: check it cannot evaluate returns ``allowed`` rather than raising into
#: evaluation, because the ceiling guards an optional, off-by-default feature and
#: blocking a reviewer's evidence over a billing lookup is the worse trade
#: (A-104). **An open-failing check nobody watches is an off switch**, so the
#: mitigation for T-02-26 is this counter rather than the branch. That argument
#: was originally written under Phase 2's separate fail-open counter, retired by
#: plan 03-03 into ``result="failed_open"`` (see the note below the last metric in
#: this file); it is an argument about the *branch*, so it survives the counter it
#: was written under and is carried here rather than deleted with the constant.
#:
#: **No label carries a figure, and that is what keeps A-056 intact.**
#: ``seams.CeilingDecision`` has exactly two fields and must never grow one that
#: carries a number; this counter counts BRANCHES. There is no ``workspace_id``
#: either — the workspace whose check could not be evaluated is exactly the label
#: ADR-0030 forbids, and every open failure is the same kind of event regardless
#: of whose it was. So "make the ceiling observable" is satisfied here without the
#: ``remaining`` field that request would otherwise have arrived carrying.
ceiling_check_total = Counter(
    "prope_call_ledger_ceiling_check_total",
    "Spend-ceiling checks by result: allowed, refused, or allowed because unevaluable.",
    labelnames=("result",),
)

#: Body rows the retention sweep deleted. Unlabelled: a per-workspace label here
#: would be the cardinality leak, and the question the number answers — "is the
#: retention promise still true" — is answered on ``oldest_body_age_seconds``
#: below rather than on this one. Increment site is ``worker``, plan 03-04.
retention_deleted_total = Counter(
    "prope_call_ledger_retention_deleted_total",
    "Expired ledger.call_body rows deleted by the retention sweep.",
)

#: **The alert measures the DATA, not the job** — ``LedgerRetentionOverdue`` reads
#: this gauge and not the sweep's exit status, because a deletion job that runs
#: successfully every night and deletes nothing looks healthy from the job's side.
#:
#: Unlabelled, for ``metadata_dropped_total``'s reason — with the consequence
#: stated rather than hidden: the alert's threshold is *per workspace* (*"the
#: workspace's retention window plus one day"*) and this series is not, so a rules
#: file can only compare against the default window. That mismatch is the fourth
#: clause of ``OQ-022``. Set in ``worker``, plan 03-04.
oldest_body_age_seconds = Gauge(
    "prope_call_ledger_oldest_body_age_seconds",
    "Age in seconds of the oldest surviving ledger.call_body row, across enumerated workspaces.",
)

# Phase 2's `ceiling_failed_open_total` stood here and plan 03-03 retired it. It
# was never a declared metric: the lock file declares `ceiling_check_total`
# labelled `result = allowed | refused | failed_open`, and `result="failed_open"`
# is the same number under the name six alert rules will be written against.
#
# Not kept alongside — two names for one number fail in one specific way, which is
# that one of them stops being incremented in a refactor nobody reviews for that.
# Not aliased either: `prometheus_client` has no alias primitive, so an alias is a
# second `Counter` incremented beside the first, which is "keep alongside" with a
# nicer word on it.
#
# This comment is the only surviving mention of the old name anywhere in `src/`,
# and it is here so that a reader meeting
# `prope_call_ledger_ceiling_failed_open_total` in an old plan, dashboard or log
# can find out where it went in one grep.


def configure_logging() -> None:
    """structlog, JSON, to stdout (ADR-0030). Idempotent.

    JSON because the line is going to be read by a machine before it is read by
    a person, and stdout because ADR-0033 runs everything under docker-compose,
    whose log driver is what collects it. No file handler, no rotation, no
    second sink — the container runtime owns all three.

    Called from the process entrypoints (``app``, ``worker``), which arrive in
    plans 02-03 and 02-04. Tests call it directly.
    """
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=False,
    )
