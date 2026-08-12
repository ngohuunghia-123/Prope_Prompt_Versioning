from prometheus_client import Counter, Gauge, Histogram

__all__ = [
    "TURNAROUND_BUCKETS",
    "acknowledged_total",
    "break_glass_total",
    "decision_total",
    "orphaned_pointer_rows",
    "pointer_conflict_total",
    "release_total",
    "review_task_open",
    "review_task_overdue",
    "review_turnaround_seconds",
    "self_approval_total",
    "submit_total",
    "summary_unavailable_total",
    "sweep_pass_total",
    "unapproved_revision_rows",
    "without_approval_rows",
]

TURNAROUND_BUCKETS = (
    300.0,
    900.0,
    3600.0,
    14400.0,
    28800.0,
    86400.0,
    172800.0,
    604800.0,
    float("inf"),
)

submit_total = Counter(
    "prope_release_submit_total",
    "Submissions for review, by what happened to the prompt's open review task.",
    labelnames=("outcome",),
)

decision_total = Counter(
    "prope_release_decision_total",
    "Recorded review decisions, by which one.",
    labelnames=("decision",),
)

acknowledged_total = Counter(
    "prope_release_acknowledged_total",
    "Approvals carrying an acknowledgement reason — a decision taken over failing or "
    "unavailable evidence (ADR-0005).",
)

break_glass_total = Counter(
    "prope_release_break_glass_total",
    "Releases performed with no approval record at all (A-009).",
)

release_total = Counter(
    "prope_release_total",
    "Pointer movements, by kind.",
    labelnames=("kind",),
)

review_turnaround_seconds = Histogram(
    "prope_release_review_turnaround_seconds",
    "Time from a review task opening to the decision that closed it.",
    buckets=TURNAROUND_BUCKETS,
)

pointer_conflict_total = Counter(
    "prope_release_pointer_conflict_total",
    "Compare-and-set losses on the released pointer: two people released one prompt (A-072).",
)

self_approval_total = Counter(
    "prope_release_self_approval_total",
    "Approvals whose reviewer authored the revision. A fact counter, never an error "
    "counter — no alert fires on it (ADR-0010).",
)

summary_unavailable_total = Counter(
    "prope_release_summary_unavailable_total",
    "Review summaries that could not be pulled from evaluation, so the acknowledgement "
    "reason became mandatory (A-070).",
)

review_task_open = Gauge(
    "prope_release_review_task_open",
    "Open review tasks across every workspace, by kind. Produced by the worker sweep.",
    labelnames=("kind",),
)

review_task_overdue = Gauge(
    "prope_release_review_task_overdue",
    "Open break-glass follow-ups past their due_at, across every workspace. The number "
    "that shows whether the gate is real.",
)

without_approval_rows = Gauge(
    "prope_release_without_approval_rows",
    "The Success-metric SQL as a series: pointer-moving releases carrying no approval "
    "with break_glass false. ReleaseWithoutApproval reads this and Prometheus runs no SQL.",
)

unapproved_revision_rows = Gauge(
    "prope_release_unapproved_revision_rows",
    "Released revisions whose status is not Approved. BR-03's database constraint should "
    "make this unreachable; a non-zero value means the constraint is gone.",
)

orphaned_pointer_rows = Gauge(
    "prope_release_orphaned_pointer_rows",
    "Released pointers with no release row behind them — a pointer written by something "
    "other than a release (ADR-0008 as amended).",
)

sweep_pass_total = Counter(
    "prope_release_sweep_pass_total",
    "Completed sweep passes, by which one. A stale gauge and a healthy gauge are "
    "otherwise indistinguishable, which is the risk this counter answers.",
    labelnames=("pass",),
)
