"""The conformance table the live lane prints when it finishes.

A live suite that only reports pass/fail throws away the measurement. What
matters about "đổi tên nó rồi chuyển vào thư mục Marketing" is not merely that
the assertion held — it is *which* intent the model picked, *which* tools ran,
what reached the confirmation card, what was queued behind it, and what actually
changed in the database. That is the evidence, and an `F` on its own is not.

So every journey records a row whether it passes or fails, and the rows are
printed as one table at the end. A failure that records first is a data point;
a failure that asserts first is a stack trace.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

__all__ = ["Observation", "RECORDED", "record", "render"]


@dataclass(slots=True)
class Observation:
    """One journey, as the run observed it."""

    #: What the person was trying to do, in the report's own words.
    journey: str
    #: The Vietnamese the person actually typed.
    said: str
    #: What the router decided.
    intent: str = "-"
    #: The tools that executed, in order.
    ran: tuple[str, ...] = ()
    #: The tool on the confirmation card, if a write was staged.
    card: str | None = None
    #: Writes queued behind that card — the second half of a multi-write turn.
    queued: tuple[str, ...] = ()
    #: What changed in the database once every card was approved.
    effect: str = "-"
    #: `ok`, or what fell short.
    verdict: str = "ok"
    #: Free notes worth carrying into the report.
    notes: list[str] = field(default_factory=list)
    #: The test this row belongs to, so a failed assertion can overwrite the
    #: verdict. Without it a row that recorded early and then blew up would
    #: print `ok` beside a red test, which is the one thing a report may not do.
    nodeid: str = ""

    def note(self, text: str) -> None:
        self.notes.append(text)


RECORDED: list[Observation] = []

#: The test currently running, set by the autouse fixture in `conftest.py`.
ACTIVE: str = ""


def record(journey: str, said: str) -> Observation:
    """Open a row before the turn runs, so a failure still reports."""
    observation = Observation(journey=journey, said=said, nodeid=ACTIVE)
    RECORDED.append(observation)
    return observation


def mark_failed(nodeid: str, reason: str) -> None:
    """Overwrite the verdict of every row this test opened."""
    for observation in RECORDED:
        if observation.nodeid == nodeid and observation.verdict == "ok":
            observation.verdict = f"FAILED — {reason}"


def _cell(value: object, width: int) -> str:
    text = "-" if value in (None, (), "") else str(value)
    if len(text) > width:
        return text[: width - 1] + "…"
    return text.ljust(width)


def _configuration() -> str:
    """Which models actually answered, named in the table's own header.

    The whole point of running this lane twice is comparing two models, and a
    table that does not say which one produced it is a measurement you cannot
    file. Read at render time rather than import time so it reports what the run
    really used.
    """
    try:
        from prope.app_agent.client import APP_AGENT_MODEL, APP_OPENAI_BASE_URL
        from prope.chat_orchestrator import dspy_program
    except Exception:  # noqa: BLE001 — a header is never worth failing a run for
        return "configuration unavailable"

    parts = [f"gateway {APP_OPENAI_BASE_URL}", f"app {APP_AGENT_MODEL}"]
    for label, model in (
        ("router", dspy_program.ROUTER_MODEL),
        ("reply", dspy_program.REPLY_MODEL),
        ("draft", dspy_program.DRAFT_MODEL),
    ):
        if model != APP_AGENT_MODEL:
            parts.append(f"{label} {model}")
    body = dspy_program.router_extra_body()
    if body:
        parts.append(f"router extra_body {body}")
    return " · ".join(parts)


def render() -> str:
    """The table, plus the roll-up the report is actually written from."""
    if not RECORDED:
        return "no journeys ran"

    widths = (34, 15, 34, 17, 17, 30)
    header = (
        _cell("JOURNEY", widths[0])
        + _cell("INTENT", widths[1])
        + _cell("TOOLS RUN", widths[2])
        + _cell("CARD", widths[3])
        + _cell("QUEUED", widths[4])
        + _cell("EFFECT", widths[5])
        + "VERDICT"
    )
    lines = ["", "=" * 180, f"CHAT JOURNEYS — {_configuration()}", "-" * 180, header, "-" * 180]

    for item in RECORDED:
        lines.append(
            _cell(item.journey, widths[0])
            + _cell(item.intent, widths[1])
            + _cell(" ".join(item.ran), widths[2])
            + _cell(item.card, widths[3])
            + _cell(" ".join(item.queued), widths[4])
            + _cell(item.effect, widths[5])
            + item.verdict
        )

    passed = [item for item in RECORDED if item.verdict == "ok"]
    lines += [
        "-" * 180,
        f"{len(passed)}/{len(RECORDED)} journeys fulfilled the request end to end.",
    ]

    gaps = [item for item in RECORDED if item.verdict != "ok"]
    if gaps:
        lines.append("")
        lines.append("GAPS")
        for item in gaps:
            lines.append(f"  {item.journey}: {item.verdict}")

    noted = [item for item in RECORDED if item.notes]
    if noted:
        lines.append("")
        lines.append("NOTES")
        for item in noted:
            for note in item.notes:
                lines.append(f"  {item.journey}: {note}")

    lines.append("=" * 180)
    return "\n".join(lines)


def print_report() -> None:
    stream = sys.stdout
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass
    print(render(), file=stream, flush=True)
