"""property-history's one metric. ADR-0030.

The lock's six others are Phase 6's — among them
``prope_property_history_rows_total``, whose declared ``workspace_id`` label
would trip ``test_workspace_id_is_never_a_metric_label``. That conflict is
``OQ-030``.
"""

from prometheus_client import Counter

#: Three label values, mirroring ``RejectionReason``; the only increment site
#: passes an enum member, so a fourth is a lock-file change (D-63).
append_rejected_total = Counter(
    "prope_property_history_append_rejected_total",
    "Appends refused by the vocabulary or the payload allow-list, by reason. Must stay 0.",
    labelnames=("reason",),
)
