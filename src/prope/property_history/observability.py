"""property-history's one metric. ADR-0030.

Separate from ``src/prope/observability.py`` because that file scopes its
*counters* to Phase 2 and every one of them is ``prope_call_ledger_*``.
``LOGGABLE_FIELDS`` stays there and is project-wide.

The lock's six other metrics are Phase 6's and are deliberately absent — among
them ``prope_property_history_rows_total``, which the lock labels by
``workspace_id`` and which would trip
``test_workspace_id_is_never_a_metric_label``. That conflict is ``OQ-030``.
``configure_logging()`` is not re-declared: a second logging configuration is a
second sink, and modules that log do ``structlog.get_logger(__name__)``.
"""

from prometheus_client import Counter

#: The label set has exactly three values — ``unknown_action`` |
#: ``unknown_detail_key`` | ``missing_reason`` — mirrored byte-for-byte by
#: ``RejectionReason``. The only increment site passes an enum member, so the
#: label value cannot be anything else. A fourth value is a lock-file change.
#:
#: **Unlike ``prope_call_ledger_metadata_dropped_total``, the "must stay 0" note
#: here is expected to hold**: every increment is a caller bug that has just
#: failed a user's transaction, and ``PropertyHistoryAppendRejected`` pages on it.
append_rejected_total = Counter(
    "prope_property_history_append_rejected_total",
    "Appends refused by the vocabulary or the payload allow-list, by reason. Must stay 0.",
    labelnames=("reason",),
)
