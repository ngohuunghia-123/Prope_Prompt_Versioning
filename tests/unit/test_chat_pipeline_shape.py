"""The pipeline the trace graph draws, and the join between it and a trace.

`GET /api/v1/chat/pipeline` exists so the client can draw the nodes a turn did
**not** visit — a picture of only what ran cannot answer *why didn't it search?*.
That only works if two things hold, and both are asserted here rather than hoped
for:

* the node set is the tool catalogue, so a seventh tool appears in the graph
  without anybody editing TypeScript;
* every step the orchestrator can record matches **exactly one** node. Zero
  matches paints a step that ran as one that was skipped; two matches lights up
  two boxes for one event. Both are worse than drawing nothing.

No database, no HTTP, no container. This is a shape.
"""

from prope.chat_orchestrator.api import _PIPELINE
from prope.chat_orchestrator.domain import TOOLS, WRITE_TOOLS, ToolName

#: Every `(agent, action)` pair `orchestrator` can write to a trace, less the
#: workers, which come from the catalogue below. Kept by hand deliberately: this
#: is the list a reader compares against `trace.add` call sites, and generating
#: it from the source would assert that the code agrees with itself.
FIXED_STEPS = (
    ("guardrail.input", "admit"),
    ("guardrail.input", "refuse"),
    ("supervisor", "route"),
    ("supervisor", "respond"),
    ("guardrail.output", "inspect"),
)


def _matching(agent: str, action: str) -> list[str]:
    """The client's rule, in Python. `agent`, then `action` when a node names one."""
    return [
        node.id
        for node in _PIPELINE.nodes
        if node.agent == agent and (node.action is None or node.action == action)
    ]


def test_every_tool_in_the_catalogue_has_a_node() -> None:
    """`domain.TOOLS` calls itself the only place a tool comes into existence.

    A hand-kept second list — here or in TypeScript — would make that false the
    first time somebody adds a tool: it would run in production, and the graph
    would quietly never draw it. Nothing fails loudly in that story.
    """
    drawn = {node.id for node in _PIPELINE.nodes if node.kind == "worker"}
    assert drawn == {f"worker.{name}" for name in TOOLS}
    assert len(drawn) == len(ToolName)


def test_the_two_write_tools_are_marked() -> None:
    """A turn that stopped to ask is a different shape from one that ran out of steps."""
    marked = {node.id for node in _PIPELINE.nodes if node.writes}
    assert marked == {f"worker.{name}" for name in WRITE_TOOLS}


def test_every_step_the_orchestrator_records_matches_exactly_one_node() -> None:
    """The load-bearing property. Zero matches and two matches both lie."""
    steps = [*FIXED_STEPS, *((f"worker.{name}", "execute") for name in TOOLS)]
    for agent, action in steps:
        assert len(_matching(agent, action)) == 1, f"{agent}/{action}"


def test_the_supervisors_two_appearances_are_separated_by_action() -> None:
    """The one node kind where the agent name alone is ambiguous.

    The supervisor routes and then answers, in the same turn, under one agent
    name. A graph that lit up both boxes for one of them would be worse than no
    graph — so the node carries the disambiguator and the client never has to
    know the rule.
    """
    assert _matching("supervisor", "route") == ["supervisor.route"]
    assert _matching("supervisor", "respond") == ["supervisor.respond"]


def test_an_aborted_stage_lands_on_the_stage_that_aborted() -> None:
    """`_unavailable` writes the stage name, not a literal `abort`.

    Both call sites used to write the same entry, so a router that never chose a
    plan and a responder that never wrote an answer had one face. Naming the
    stage is also what lets the graph light up the box that failed.
    """
    assert _matching("supervisor", "route") == ["supervisor.route"]
    assert _matching("supervisor", "respond") == ["supervisor.respond"]
    assert _matching("supervisor", "abort") == []


def test_node_ids_are_unique_and_every_edge_lands_on_one() -> None:
    ids = [node.id for node in _PIPELINE.nodes]
    assert len(ids) == len(set(ids))
    for edge in _PIPELINE.edges:
        assert edge.source in set(ids), edge.source
        assert edge.target in set(ids), edge.target


def test_the_stages_run_in_order_and_the_workers_share_one() -> None:
    """Stage is an ordinal, not a coordinate. Nodes sharing one are alternatives."""
    stage_of = {node.id: node.stage for node in _PIPELINE.nodes}
    assert stage_of["guardrail.input"] < stage_of["supervisor.route"]
    assert stage_of["supervisor.route"] < stage_of["supervisor.respond"]
    assert stage_of["supervisor.respond"] < stage_of["guardrail.output"]
    worker_stages = {node.stage for node in _PIPELINE.nodes if node.kind == "worker"}
    assert len(worker_stages) == 1
    assert stage_of["supervisor.route"] < worker_stages.pop() < stage_of["supervisor.respond"]


def test_the_route_can_reach_the_answer_without_a_worker() -> None:
    """Small talk and a refusal both answer with an empty plan.

    Not a shortcut — the commonest path through the graph. Without this edge the
    picture would claim every turn runs a tool.
    """
    assert any(
        edge.source == "supervisor.route" and edge.target == "supervisor.respond"
        for edge in _PIPELINE.edges
    )


def test_no_node_carries_a_display_string() -> None:
    """ADR-0053: the API returns a key, the client owns the Vietnamese."""
    for node in _PIPELINE.nodes:
        assert node.label_code.startswith("chat.graph.node.")
        assert node.label_code == f"chat.graph.node.{node.id.replace('.', '_')}"
