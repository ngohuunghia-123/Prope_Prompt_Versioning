"""The Phase 2 counters, and only those. ADR-0030.

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

**Phase 2 wires four counters and nothing else.** This resolves the CONTEXT
discretion item "whether Phase 2 wires any Prometheus/structlog at all". The
answer is: only the counters D-16, D-21 and D-23 name as their own controls. The
full 17-metric set from ``docs/modules/call-ledger.lock.yml``, the ``dlq_depth``
gauge, and every alert rule are Phase 3's T-005 sweep. **There is no
``/metrics`` endpoint in this phase**, so these counters are observable from
tests and from nothing else yet. That is a stated gap, not an oversight — a
counter with no scraper still makes the failure it counts *countable*, which is
what turns Phase 2's known-lossy window from a claim into a measurement.

**A note that will read as a contradiction and is not.**
``prope_call_ledger_metadata_dropped_total`` carries the lock file's
``# must stay 0 — see the failure mode`` note. **It will not stay 0 in Phase
2.** Phase 2 ships the broker path with no direct-write fallback (CL-01) and no
idempotent upsert on ``call_id`` (CL-02), so a full handoff buffer, a failed
confirm and a dead-lettered record each genuinely lose a record and each
increments this counter. CL-01 and CL-02 are what return it to zero. Written
here, at the counter, so a reader of this module learns it from the same place
they learn the counter exists.
"""

import logging
import sys

import structlog
from prometheus_client import Counter

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
    }
)

#: INT-018's enqueue counter. ``source`` is ``gateway`` | ``eval`` — the
#: ``Source`` vocabulary, which is a database CHECK set and therefore closed.
#: ``outcome`` here is the fate of the HANDOFF, not the ``Outcome`` vocabulary:
#: ``accepted`` when the record entered the buffer, ``dropped`` when the buffer
#: was full. Two values, fixed in source.
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

#: Unlabelled, because every drop is the same kind of event regardless of who it
#: belonged to, and a label here would be the cardinality leak the module
#: docstring refuses. **This will be non-zero in Phase 2**; see the docstring.
metadata_dropped_total = Counter(
    "prope_call_ledger_metadata_dropped_total",
    "Call records that will never reach ledger.call_record. Phase 2 has no fallback; "
    "CL-01 and CL-02 are what return this to zero.",
)


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
