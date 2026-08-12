"""The seventeen metrics `access-control.lock.yml` declares. All defined at import.

**Defined at import even where nothing increments them yet** (D-40).
`REGISTRY.get_sample_value` returns `None` — not `0.0` — for a metric nothing has
touched, so a *"must stay 0"* series defined lazily is indistinguishable from one
that was never wired. Three of the alerts below fire on exactly that shape
(`unknown_action_total`, `check_error_total`, `admin_count`), which makes eager
definition a property their rules depend on rather than a style.

**Two label sets here break this project's own cardinality rule, and both are
lock-file-declared.** `prope.observability` states that *"`workspace_id` — the
highest-cardinality identifier in the system and the one most tempting to add —
is deliberately never a label"*, and `admin_count` carries exactly that, because
`AccessControlAdminCountZero` has to name the workspace that reached zero or the
page is unactionable. `key_scope_refusal_total` carries `key_id` for the
neighbouring reason. Both ship as declared and both are raised as **OQ-135**
rather than absorbed — the precedent is call-ledger's
`unpriced_total{provider_config_id, upstream_model}`, which took the same shape.
The bound in both cases is the pilot's scale (a handful of workspaces, tens of
keys), and that bound is a fact about the pilot rather than about the design.

**Nothing here can carry a secret.** No metric takes an email, a password, a
session id or a key secret as a label, and there is no label whose value is
caller-supplied free text — every one of them is a closed set fixed in source or
an identifier the lock file marks loggable (A-046, ADR-0030).
"""

from prometheus_client import Counter, Gauge, Histogram

__all__ = [
    "active_sessions",
    "admin_count",
    "check_duration_seconds",
    "check_error_total",
    "check_total",
    "grant_total",
    "key_auth_duration_seconds",
    "key_auth_total",
    "key_revoked_total",
    "key_scope_refusal_total",
    "last_admin_refused_total",
    "login_duration_seconds",
    "login_rate_limited_total",
    "login_total",
    "unknown_action_total",
    "visible_filter_duration_seconds",
    "visible_filter_ids_size",
]

# --- may() -----------------------------------------------------------------

#: **5 ms is an EDGE, not a bucket interior.** The lock file states `may()` at
#: p95 < 5 ms and the load test asserts that number, so the histogram has to be
#: able to answer it exactly — a bucket spanning 2 ms to 10 ms would make the
#: assertion an interpolation. The same rule governs `KEY_AUTH_BUCKETS` below and
#: is the one call-ledger's `WRITE_LAG_BUCKETS` established.
CHECK_DURATION_BUCKETS = (0.0005, 0.001, 0.002, 0.005, 0.01, 0.025, 0.05, 0.1, float("inf"))

check_duration_seconds = Histogram(
    "prope_access_control_check_duration_seconds",
    "Wall time inside may(), by action and by the answer it gave.",
    labelnames=("action", "result"),
    buckets=CHECK_DURATION_BUCKETS,
)

#: `result` is `allow` or `deny` and there is deliberately no third value. An
#: *error* is not a third answer — it is the absence of one, it is counted on
#: `check_error_total` below, and every caller treats it as a refusal by not
#: catching it (A-142 §2). A `result="error"` here would make the deny rate
#: `AccessControlDenyRateSpike` watches quietly include failures.
check_total = Counter(
    "prope_access_control_check_total",
    "Permission checks, by action and by whether they allowed or denied.",
    labelnames=("action", "result"),
)

check_error_total = Counter(
    "prope_access_control_check_error_total",
    "Checks that could not be evaluated at all. Every caller fails closed, so any "
    "increment is a partial outage of the whole product before it is anything else.",
)

#: A-115's fall-through guard, and it **must stay 0**. An increment means either
#: a caller is sending an action the vocabulary does not hold, or a rename
#: shipped half-applied. It is currently denying, which is safe — and which is
#: also why nobody would notice without this counter: the feature is silently
#: broken and every screen looks like a permissions problem.
unknown_action_total = Counter(
    "prope_access_control_unknown_action_total",
    "may() calls naming an action outside the closed vocabulary. Must stay 0.",
)

# --- consumer keys ---------------------------------------------------------

#: `result` is closed at three: the key authenticated, no such key id exists, or
#: the row carries a `revoked_at`. A hash mismatch counts as `unknown` on
#: purpose — telling a caller apart from an attacker who guessed a live key id
#: would be a distinction visible in a dashboard, and the response shapes are
#: already identical.
key_auth_total = Counter(
    "prope_access_control_key_auth_total",
    "Consumer key authentications, by outcome.",
    labelnames=("result",),
)

#: Tighter than `CHECK_DURATION_BUCKETS` at the bottom: INT-003 and INT-004
#: together hold p95 < 5 ms inside the gateway's 50 ms, and this is one indexed
#: read plus one SHA-256, so the interesting range is sub-millisecond.
KEY_AUTH_BUCKETS = (0.0002, 0.0005, 0.001, 0.002, 0.005, 0.01, 0.025, float("inf"))

key_auth_duration_seconds = Histogram(
    "prope_access_control_key_auth_duration_seconds",
    "Wall time inside authenticate_api_key(): one indexed read plus one comparison.",
    buckets=KEY_AUTH_BUCKETS,
)

#: OQ-135's second entry. `key_id` is bounded by the number of keys a workspace
#: has issued, which is small — and the alternative is a counter that says
#: refusals are happening and cannot say which consumer to call.
key_scope_refusal_total = Counter(
    "prope_access_control_key_scope_refusal_total",
    "may_resolve() refusals: a live key asking for a model name outside its scope.",
    labelnames=("key_id",),
)

key_revoked_total = Counter(
    "prope_access_control_key_revoked_total",
    "Consumer keys revoked. Effective on the next request, with no TTL to wait out.",
)

# --- sign-in ---------------------------------------------------------------

#: `result` is `ok`, `bad_password` or `unknown`. **The three are distinguishable
#: HERE and nowhere else** — the responses are byte- and timing-identical
#: (A-144, ADR-0043), and this counter is the only place in the system that can
#: tell them apart. That is the point: the operator needs the distinction and the
#: client must not have it.
login_total = Counter(
    "prope_access_control_login_total",
    "Sign-in attempts that reached the hash, by outcome.",
    labelnames=("result",),
)

#: Buckets around the 500 ms target and around ADR-0043's measured 55–70 ms, so
#: the gap between them stays visible. The failure mode the lock file predicts is
#: this histogram falling *well below* its target, which is evidence somebody
#: lowered the cost parameter — so the low end needs resolution too.
LOGIN_DURATION_BUCKETS = (0.01, 0.05, 0.075, 0.1, 0.25, 0.5, 1.0, 2.5, float("inf"))

login_duration_seconds = Histogram(
    "prope_access_control_login_duration_seconds",
    "Wall time for a sign-in attempt, argon2id included.",
    buckets=LOGIN_DURATION_BUCKETS,
)

#: REQUIRED, not optional (ADR-0043). The limiter rejects **before** the hash, so
#: its rejections never reach `login_total` — and `login_total{result=bad_password}`
#: is the series `AccessControlLoginBruteForce` fires on. Without this counter a
#: working limiter makes that alert *quieter*, and the more effective the limiter
#: is the more it looks like nothing is happening.
login_rate_limited_total = Counter(
    "prope_access_control_login_rate_limited_total",
    "Sign-in attempts rejected by the in-process limiter before any hash was computed.",
    labelnames=("bucket",),
)

active_sessions = Gauge(
    "prope_access_control_active_sessions",
    "Unexpired session rows. Sessions are rows, so this is a count and not an estimate.",
)

# --- visibility ------------------------------------------------------------

#: Coarser than `may()`'s: A-118 budgets this at p95 < 20 ms against a workspace
#: of 1,000 prompts, and 20 ms is an edge for the same reason 5 ms is above.
VISIBLE_FILTER_BUCKETS = (0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.25, float("inf"))

visible_filter_duration_seconds = Histogram(
    "prope_access_control_visible_filter_duration_seconds",
    "Wall time inside visible_subject_filter(), by the mode it returned.",
    labelnames=("mode",),
    buckets=VISIBLE_FILTER_BUCKETS,
)

#: A-118's revisit condition, made observable: *"a workspace's prompt count makes
#: an explicit id list too large to push into a query"*. The top bucket is 1,000
#: because that is the number the performance condition names, so a workspace
#: crossing it shows up as the `+Inf` bucket moving rather than as a slow query
#: somebody has to go looking for.
VISIBLE_FILTER_IDS_BUCKETS = (0, 1, 5, 10, 25, 50, 100, 250, 500, 1000)

visible_filter_ids_size = Histogram(
    "prope_access_control_visible_filter_ids_size",
    "Ids returned per visible_subject_filter() call in mode=ids.",
    buckets=VISIBLE_FILTER_IDS_BUCKETS,
)

# --- the zero-Admin invariant (A-117) --------------------------------------

#: OQ-135's first entry. **Must never read 0 for any workspace.** The gauge
#: exists to prove the refusal below is working rather than to catch a state
#: anybody plans to recover from — there is no cross-workspace operator surface
#: to repair a frozen workspace from, and A-012 rules out building one.
admin_count = Gauge(
    "prope_access_control_admin_count",
    "Active Admin bindings per workspace. Must never be 0.",
    labelnames=("workspace_id",),
)

last_admin_refused_total = Counter(
    "prope_access_control_last_admin_refused_total",
    "Operations refused because they would have left a workspace with no Admin.",
)

# --- grants ----------------------------------------------------------------

#: `operation` is `grant` or `revoke`; `level` is `viewer` or `editor` (A-112).
#: A revoke carries the level the grant *had*, so the two series subtract — a
#: revoke labelled with nothing would make "how many editor grants are live"
#: unanswerable from the counters.
grant_total = Counter(
    "prope_access_control_grant_total",
    "Per-prompt grants written, by level and by whether they were granted or revoked.",
    labelnames=("level", "operation"),
)
