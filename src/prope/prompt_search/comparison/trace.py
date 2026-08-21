"""The funnel narrating itself: one event per rung, as it happens.

The comparison takes up to twenty-five seconds and used to spend all of it
behind a spinner. That is not only a patience problem — it is the same
legibility problem the redesign exists to fix, one level up. A screen that says
*"checking…"* and then shows two prompts has asserted its answer; a screen that
says *retrieval offered 18, the pre-filter kept 5, the adjudicator judged 5, one
cleared 90%* has shown its working, and a person who thinks the answer is wrong
knows which rung to blame.

**Codes, not sentences, and the same ADR-0053 discipline as everything else
here.** A step is a name from a closed vocabulary plus machine counts, and the
client owns the words. That keeps the trace translatable, and it keeps it
countable if the funnel's shape ever needs measuring from the outside.

**Nothing in an event may be prompt text.** These frames go out over a
long-lived connection and are the easiest place in the system to leak a body by
accident, so :class:`TraceEvent` carries integers and codes and has no field
that could hold one. The candidate bodies and shared terms travel exactly once,
in the final result frame, which is the payload the JSON route already returns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

__all__ = ["STEP_CODES", "Step", "StepState", "TraceEvent"]


class Step(StrEnum):
    """The rungs, in the order they run.

    One entry per thing that can actually take time or actually reject
    something. ``contracts`` earns its place despite costing nothing: it is the
    rung that demotes a ``same`` to a ``variant``, which is the single most
    surprising outcome on the screen and the one a reader most needs to see
    attributed.
    """

    #: Vector + lexical, recall-tuned. The only rung that touches the database.
    RETRIEVAL = "retrieval"
    #: Canonical-block containment over pool-relative IDF. Free.
    PREFILTER = "prefilter"
    #: The one paid call, over at most five candidates.
    ADJUDICATION = "adjudication"
    #: Output contracts, for the sides that do not already have one — the
    #: incoming paste never does, and an index row often does not either.
    #:
    #: **It runs after adjudication, which is not where a reader would put it.**
    #: The order is a cost decision: a pair the adjudicator called `different`
    #: leaves the sheet whatever its contract says, because output findings only
    #: demote. Extracting first would spend a call per candidate to learn
    #: something about candidates nobody will see.
    OUTPUT_CONTRACT = "output_contract"
    #: Variables and output shape, exact and free.
    CONTRACTS = "contracts"
    #: Verdicts resolved, the floor applied, the sheet assembled.
    VERDICT = "verdict"


class StepState(StrEnum):
    """What happened to a rung.

    ``skipped`` is deliberately not ``done`` with a zero: a rung that did not run
    and a rung that ran and found nothing are different facts, and collapsing
    them is how *"the adjudicator was unavailable"* would come to read as *"the
    adjudicator found nothing"*.
    """

    STARTED = "started"
    DONE = "done"
    SKIPPED = "skipped"
    FAILED = "failed"


#: Every step code, closed and in source, for the same reason `FINDING_CODES`
#: is: a contract test reads this tuple and the interface catalogues and refuses
#: a step with no sentence. A trace whose rows render as `output_contract` is a
#: progress display in a language nobody speaks.
STEP_CODES: tuple[str, ...] = tuple(step.value for step in Step)


@dataclass(frozen=True, slots=True)
class TraceEvent:
    """One rung, one moment. Counts and codes only — never a body, never a term."""

    step: Step
    state: StepState
    #: Machine values the sentence interpolates: ``retrieved``, ``kept``,
    #: ``judged``, ``hard``, ``shown``, ``hidden``. Integers and the occasional
    #: bounded string; the same rule as `Finding.params`.
    params: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "step": self.step.value,
            "state": self.state.value,
            "params": dict(self.params),
        }
