"""Cutting edges that land on a node the reader may not see.

The visibility decision itself belongs to `may()` and is proved against a real
database elsewhere. What is proved here is what the route does with the answer,
which is the part that carries the security weight: a dropped node must not be
re-parented onto its grandparent, and a hidden parent must be indistinguishable
from an expired one.

`_conversation_graph_read` is a pure function over rows, so none of this needs a
database, an HTTP client or a container.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from prope.call_ledger.seams import ConversationCall
from prope.prompt_registry.api import _conversation_graph_read

START = datetime(2026, 8, 18, 9, 0, tzinfo=UTC)


def _call(call_id: str, *, parent: str | None = None, prompt: str = "prm_system", step: int = 0):
    return ConversationCall(
        call_id=call_id,
        parent_call_id=parent,
        prompt_id=prompt,
        source="gateway",
        version_id="ver_1",
        revision_number=3,
        consumer_key_id="key_app",
        provider_config_id="pcf_1",
        upstream_model="gpt-4o-mini",
        outcome="ok",
        pinned=False,
        fallback=False,
        streaming=False,
        input_tokens=100,
        output_tokens=20,
        usage_status="reported",
        cost=Decimal("0.0001000000"),
        currency="USD",
        cost_status="priced",
        added_latency_ms=4,
        upstream_duration_ms=900,
        error_class=None,
        created_at=START + timedelta(milliseconds=step),
    )


def _graph(calls, *, titles, hidden=0, truncated=False):
    return _conversation_graph_read(
        "conv-1",
        calls,
        titles=titles,
        labels={"key_app": "Chatbot production"},
        hidden_count=hidden,
        truncated=truncated,
    )


TITLES = {"prm_system": "System prompt", "prm_guard": "Guardrail", "prm_tools": "Tool catalogue"}


def test_a_whole_chain_keeps_every_edge() -> None:
    """The ordinary case: system prompt, guardrail, tool definition, one after another."""
    calls = [
        _call("cal_a", prompt="prm_system", step=0),
        _call("cal_b", parent="cal_a", prompt="prm_guard", step=1),
        _call("cal_c", parent="cal_b", prompt="prm_tools", step=2),
    ]
    graph = _graph(calls, titles=TITLES)
    assert [(n.call_id, n.parent_call_id) for n in graph.nodes] == [
        ("cal_a", None),
        ("cal_b", "cal_a"),
        ("cal_c", "cal_b"),
    ]
    assert graph.hidden_count == 0


def test_a_dropped_node_orphans_its_child_and_is_never_bridged_over() -> None:
    """The load-bearing one.

    `cal_b`'s prompt is private to somebody else, so it is gone. `cal_c` must
    become a root — **not** a child of `cal_a`. Bridging would draw a chain that
    claims the system prompt called the tool catalogue directly, which is a
    different application from the one that ran. A graph that is confidently
    wrong about shape is worse than one that is visibly incomplete.
    """
    calls = [
        _call("cal_a", prompt="prm_system", step=0),
        _call("cal_c", parent="cal_b", prompt="prm_tools", step=2),
    ]
    graph = _graph(calls, titles=TITLES, hidden=1)
    assert [(n.call_id, n.parent_call_id) for n in graph.nodes] == [
        ("cal_a", None),
        ("cal_c", None),
    ]
    assert graph.hidden_count == 1


def test_a_hidden_parent_and_an_expired_parent_produce_the_same_shape() -> None:
    """The uniformity IS the security property.

    If a node whose parent was hidden looked different from one whose parent had
    aged out of retention, the shape itself would answer *does a private prompt
    exist here?* — which is the disclosure private-by-default closes as not-found.
    """
    hidden_parent = _graph([_call("cal_c", parent="cal_b")], titles=TITLES, hidden=1)
    expired_parent = _graph([_call("cal_c", parent="cal_gone")], titles=TITLES, hidden=0)
    assert hidden_parent.nodes[0].parent_call_id == expired_parent.nodes[0].parent_call_id is None


def test_a_fan_out_to_sub_agents_keeps_both_branches() -> None:
    """Two children of one parent is a tree, and the ordering must not flatten it.

    Both sub-agent calls land in the same millisecond, which is the expected case
    for a parallel fan-out rather than an unlucky one. The parent link is what
    carries the shape; the clock cannot.
    """
    calls = [
        _call("cal_a", prompt="prm_system", step=0),
        _call("cal_b", parent="cal_a", prompt="prm_guard", step=1),
        _call("cal_c", parent="cal_a", prompt="prm_tools", step=1),
    ]
    graph = _graph(calls, titles=TITLES)
    assert [n.parent_call_id for n in graph.nodes] == [None, "cal_a", "cal_a"]


def test_a_node_carries_its_prompt_title_and_its_calling_integration() -> None:
    graph = _graph([_call("cal_a", prompt="prm_guard")], titles=TITLES)
    node = graph.nodes[0]
    assert node.prompt_title == "Guardrail"
    assert node.consumer_label == "Chatbot production"
    assert node.revision_number == 3


def test_a_node_has_nowhere_to_put_a_body() -> None:
    """ADR-0018 as a type, not as a promise.

    The graph draws the shape of a chain. The shape is metadata; the content has
    no read path and this model has no field that could carry one.
    """
    forbidden = {"body", "request_body", "response_body", "payload", "raw_body", "byte_size"}
    assert not forbidden & set(type(_graph([_call("cal_a")], titles=TITLES).nodes[0]).model_fields)


def test_truncation_is_reported_rather_than_hidden() -> None:
    """A graph showing the first two hundred of nine thousand calls must say so."""
    assert _graph([_call("cal_a")], titles=TITLES, truncated=True).truncated is True
