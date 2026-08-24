"""Metrics, the trace-key allow-list, and the Langfuse span for one chat turn.

Deck 6 and deck 3 (p44-47) both land on the same requirement and this module is
where Prope meets it: a multi-agent system is not debuggable without a trace that
shows *which agent ran, in what order, on what, with what result*. Deck 3's
worked example (p45) lists seven fields. Six of them are recorded here.

**The seventh — `input_summary` — is refused, and this is the file that enforces
it.** A summary of a chat turn's input is a summary of what somebody typed, and
in this product what they typed is routinely a whole corporate prompt. A-020
forbids that text leaving the governed path, and the trace leaves it three times
over: into the HTTP response, into `chat.message`, and into Langfuse. So
:data:`SAFE_TRACE_KEYS` is a closed allow-list of scalar keys, and
:func:`safe_detail` drops everything else — including a key somebody adds later
without reading this paragraph.

**Every label below has a closed value set fixed in this file.** ADR-0030 and the
rule in `prope/observability.py`: no `workspace_id`, no `prompt_id`, no
model-supplied string ever becomes a label. `prompt_search.observability` records
a cardinality debt in its own docstring for three counters that predate the rule;
nothing here inherits it.
"""

from typing import Any, Final

from prometheus_client import Counter, Gauge, Histogram

__all__ = [
    "SAFE_TRACE_KEYS",
    "agent_circuit_open",
    "cost_usd_total",
    "directive_dropped_total",
    "grounding_score",
    "input_refused_total",
    "output_rail_total",
    "pending_action_total",
    "prompt_fallback_total",
    "retrieval_dense_unavailable_total",
    "router_total",
    "safe_detail",
    "tokens_total",
    "tool_duration_seconds",
    "tool_total",
    "turn_duration_seconds",
    "turn_total",
]

#: A turn is two model calls plus up to three tool calls, one of which may embed
#: a whole prompt body. The buckets straddle the 8 s target the lock file sets
#: rather than trailing off at 1 s, because a histogram whose top bucket is below
#: the target cannot show a target being missed.
TURN_BUCKETS: Final = (0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0, 30.0, 60.0)
TOOL_BUCKETS: Final = (0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0)

#: outcome = answered | refused | degraded | unavailable.
#:
#: `degraded` is its own value rather than folded into `answered`, and the
#: distinction is deck 4's (p35): a turn that answered with one of its two
#: retrieval legs down looks exactly like a healthy turn on every other signal.
#: `unavailable` is the model or the circuit breaker; `refused` is a guardrail.
turn_total = Counter(
    "chat_turn_total",
    "Chat turns by outcome",
    labelnames=("outcome",),
)

turn_duration_seconds = Histogram(
    "chat_turn_duration_seconds",
    "End-to-end chat turn latency in seconds",
    buckets=TURN_BUCKETS,
)

#: intent = the closed `domain.Intent` vocabulary. Six values, and a seventh
#: costs an edit to that enum.
router_total = Counter(
    "chat_router_total",
    "Routing decisions by intent",
    labelnames=("intent",),
)

#: tool = the closed `domain.ToolName` vocabulary; outcome = ok | error | refused.
#: `refused` is a permission failure — the person asked for something the tool
#: would do and they may not do it — and it is counted separately from `error`
#: because one is the system working and the other is not.
tool_total = Counter(
    "chat_tool_total",
    "Tool executions by tool and outcome",
    labelnames=("tool", "outcome"),
)

tool_duration_seconds = Histogram(
    "chat_tool_duration_seconds",
    "Tool execution latency in seconds",
    labelnames=("tool",),
    buckets=TOOL_BUCKETS,
)

#: reason = the closed `guardrails.RefusalReason` set. Rising on `injection` is
#: the signal deck 5 (p48) says to run a red-team pass against; rising on
#: `off_topic` usually means the product is being asked for something it should
#: consider building.
input_refused_total = Counter(
    "chat_input_refused_total",
    "Turns stopped by an input rail",
    labelnames=("reason",),
)

#: rail = secret_redacted | instruction_leak | ungrounded.
#:
#: **This counter is meant to stay at zero.** Every value means an output rail
#: caught something the input rails and the instructions did not, which is
#: defence in depth doing its job and also a bug report.
output_rail_total = Counter(
    "chat_output_rail_total",
    "Replies modified or replaced by an output rail",
    labelnames=("rail",),
)

#: A directive the validator refused. Unlabelled because the interesting question
#: is whether this is zero, and the *which* belongs on the log line where the
#: allow-list already admits it.
directive_dropped_total = Counter(
    "chat_directive_dropped_total",
    "UI directives dropped by the validator",
)

#: decision = proposed | confirmed | rejected | not_found.
#:
#: The ratio of `confirmed` to `proposed` is the HITL metric deck 5 (p57) asks
#: for by name. Near 1.0 means the confirmation card has become a rubber stamp
#: and the agent is being trusted more than it earned; near 0 means it is
#: proposing the wrong thing and the flow is costing people time.
pending_action_total = Counter(
    "chat_pending_action_total",
    "Proposed writes by what happened to them",
    labelnames=("decision",),
)

#: direction = input | output. Two series because output costs 4-6x input at
#: every provider and a single total hides which one moved.
tokens_total = Counter(
    "chat_tokens_total",
    "Tokens consumed by the chat orchestrator",
    labelnames=("direction",),
)

cost_usd_total = Counter(
    "chat_cost_usd_total",
    "Cumulative USD spent on chat turns",
)

#: program = router | responder | drafter. Rising means the Langfuse `production`
#: label stopped resolving and the assistant is silently running in-code instructions.
prompt_fallback_total = Counter(
    "chat_prompt_fallback_total",
    "Model calls that ran on the in-code fallback instruction",
    labelnames=("program",),
)

#: outcome = drafted | invalid | unavailable. `invalid` rising means the drafter
#: model keeps failing the canonical XML contract — an instruction problem, not
#: a person's. `unavailable` covers breaker-open and provider failure.
drafter_total = Counter(
    "chat_drafter_total",
    "Body-drafting attempts by outcome",
    labelnames=("outcome",),
)

#: One continuation turn runs per human decision, so this series tracks HITL
#: follow-through directly: decisions that produce no continuation at all would
#: mean the wiring regressed. Unlabelled on purpose — there is one kind today,
#: and `test_every_chat_metric_label_has_a_closed_value_set` holds the label
#: vocabulary shut until a second kind earns its way in.
continuation_total = Counter(
    "chat_decision_continuation_total",
    "Automatic turns run after a human decision",
)

#: The share of a reply's claims that carry a citation the evidence supports.
#: Deck 5 (p35) calls this the bridge between the RAG pipeline and the trust
#: layer; it is computed deterministically in `orchestrator`, so it costs nothing
#: and cannot itself drift.
grounding_score = Histogram(
    "chat_grounding_score",
    "Deterministic grounding score of a reply, 0.0 to 1.0",
    buckets=(0.0, 0.25, 0.5, 0.75, 0.9, 1.0),
)

#: The documentation corpus answered on the lexical leg alone. Not an error —
#: `knowledge.retrieve` is built to survive it — but it means retrieval quality
#: is degraded and nothing else on the dashboard would say so.
retrieval_dense_unavailable_total = Counter(
    "chat_retrieval_dense_unavailable_total",
    "Documentation retrievals that ran without the embedding leg",
)

agent_circuit_open = Gauge(
    "chat_agent_circuit_open",
    "Whether the chat orchestrator's App Agent circuit breaker is currently open",
)


#: The only keys a `TraceEntry.detail` may carry, and every one of them is a
#: count, an identifier, or a closed-vocabulary token.
#:
#: **Adding a key here is the decision, not adding it at the call site.** The
#: rule this enforces is A-020's: no prompt title, purpose, body, or extracted
#: keyword reaches the trace — and the trace is returned to the client, stored,
#: and mirrored to Langfuse. `query`, `text`, `title`, `purpose`, `body`,
#: `reply`, `snippet` and `summary` are absent on purpose and none of them is an
#: oversight.
SAFE_TRACE_KEYS: Final[frozenset[str]] = frozenset(
    {
        # what happened
        "tool",
        "intent",
        "decision",
        "reason",
        "rail",
        "outcome",
        "mode",
        # how much
        "result_count",
        "evidence_count",
        "citation_count",
        "chunk_count",
        "dropped",
        "step",
        "steps",
        "score",
        "similarity",
        "truncated",
        # which rows
        "prompt_id",
        "version_id",
        "document",
        "corpus",
        # model bookkeeping
        "model",
        "prompt_version",
        "fallback",
        "input_tokens",
        "output_tokens",
        "cost_usd",
    }
)

#: Scalars only. A nested dict is where a body hides from a key allow-list.
_SAFE_TYPES = (str, int, float, bool)

#: A `str` value in a trace is a token or an identifier, never prose. Bounded so
#: that a value which slipped past the key check cannot be a paragraph.
_MAX_TRACE_VALUE_CHARACTERS: Final = 64


def safe_detail(raw: dict[str, Any] | None) -> dict[str, Any]:
    """One trace entry's detail, reduced to what may be recorded.

    Drops rather than raises, for `sanitise_directives`' reason: a trace is
    diagnostic and must never be the thing that fails a turn. What it must be is
    incapable of carrying content, and dropping is how that stays true when
    somebody adds a call site without reading this module.
    """
    if not raw:
        return {}

    detail: dict[str, Any] = {}
    for key, value in raw.items():
        if key not in SAFE_TRACE_KEYS or not isinstance(value, _SAFE_TYPES):
            continue
        if isinstance(value, str):
            value = value[:_MAX_TRACE_VALUE_CHARACTERS]
        detail[key] = value

    return detail
