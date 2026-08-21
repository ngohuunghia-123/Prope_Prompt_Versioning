"""Stage 2a — the input contract. Free, exact, and it runs before anything is spent.

`prompt_composition.render()` raises ``MissingVariable`` for any placeholder
without a value and **ignores extras** — it iterates ``required_variables(body)``
and nothing else. So compatibility between two bodies is set math with a
direction, decided with no model, no dispatch, no threshold and no calibration:

===========================================  ==========
``required(B) == required(A)``               compatible
``required(B)`` subset of ``required(A)``    compatible — callers still send the extras, B ignores them
``required(B)`` superset of ``required(A)``  **breaking** — every caller gets ``MissingVariable``
partial overlap, or a rename                 **breaking** — the new names are never supplied
===========================================  ==========

**This answers breakage, not sameness.** ``{{document}}`` renamed to ``{{text}}``
is mechanically breaking and semantically the same job. What comes out of here
feeds the veto list and contributes *nothing* to the `same job?` question — the
two stay separate, and the direction of the arrow is why: a rename cannot make
two prompts do different work, and it cannot fail to break every caller either.

**The mirror rule.** For *inputs* B must require a subset of A. For *output keys*
(stage 2b) B must produce a superset of A. Reversing either would be a silent
bug that passes every test written from the wrong side, which is why each
direction is a named function and neither is an inline comparison.
"""

from __future__ import annotations

from dataclasses import dataclass

from prope.prompt_composition import required_variables
from prope.prompt_search.comparison.domain import (
    Finding,
    InputContractRelation,
    Severity,
)

__all__ = [
    "InputContractComparison",
    "compare_input_contracts",
    "requires_subset_of",
]

AXIS = "input_contract"


def requires_subset_of(candidate: frozenset[str], released: frozenset[str]) -> bool:
    """Does ``candidate`` require nothing the caller of ``released`` does not send?

    The one direction that matters for breakage, written down once with a name so
    that no reader ever has to work out which side of a ``<=`` is which. Its
    mirror lives in :mod:`prope.prompt_search.comparison.output_contract`.
    """
    return candidate <= released


@dataclass(frozen=True, slots=True)
class InputContractComparison:
    """What the two variable sets are to each other, and what breaks."""

    relation: InputContractRelation
    #: Names B requires that A does not. Every one of these is a caller break.
    added: tuple[str, ...]
    #: Names A requires that B does not. Harmless — `render()` ignores extras.
    dropped: tuple[str, ...]
    shared: tuple[str, ...]

    @property
    def is_breaking(self) -> bool:
        """True when swapping B in makes an existing caller fail.

        Exactly ``added`` being non-empty. Stated as a property rather than
        re-derived at each call site because "breaking" is the word the rest of
        the pipeline reasons with, and it must mean one thing.
        """
        return bool(self.added)

    @property
    def is_compatible(self) -> bool:
        return not self.is_breaking

    def findings(self) -> tuple[Finding, ...]:
        """The comparison as codes, ordered hard first.

        A rename is reported as its own code even though it is mechanically just
        an add plus a drop: it is the one shape where the breakage and the job
        disagree completely, and a reviewer shown *"adds {{text}}, drops
        {{document}}"* has to reconstruct that themselves.
        """
        if self.relation is InputContractRelation.RENAMED:
            return (
                Finding(
                    code="similar.input_contract.renamed",
                    severity=Severity.HARD,
                    axis=AXIS,
                    params={"added": list(self.added), "dropped": list(self.dropped)},
                ),
            )

        found: list[Finding] = []
        if self.added:
            found.append(
                Finding(
                    code="similar.input_contract.requires_more",
                    severity=Severity.HARD,
                    axis=AXIS,
                    params={"added": list(self.added)},
                )
            )
        if self.dropped:
            found.append(
                Finding(
                    # Soft, and deliberately still reported. Dropping a variable
                    # breaks nobody, but a prompt that stopped reading
                    # `{{customer_tier}}` is a prompt that stopped doing part of
                    # the job, and that is a thing to look at.
                    code="similar.input_contract.requires_fewer",
                    severity=Severity.SOFT,
                    axis=AXIS,
                    params={"dropped": list(self.dropped)},
                )
            )
        if not found and self.relation is InputContractRelation.IDENTICAL:
            found.append(
                Finding(
                    code="similar.input_contract.identical",
                    severity=Severity.INFO,
                    axis=AXIS,
                    params={"variables": list(self.shared)},
                )
            )
        return tuple(found)


def compare_input_contracts(*, candidate_body: str, released_body: str) -> InputContractComparison:
    """``required_variables`` of both bodies, related.

    ``candidate_body`` is the incoming prompt (B in the draft), ``released_body``
    the stored one whose callers exist (A). Argument names are keyword-only for
    that reason: the relation is asymmetric and a positional swap would invert
    every verdict silently.
    """
    candidate = frozenset(required_variables(candidate_body))
    released = frozenset(required_variables(released_body))

    added = tuple(sorted(candidate - released))
    dropped = tuple(sorted(released - candidate))
    shared = tuple(sorted(candidate & released))

    if not candidate and not released:
        relation = InputContractRelation.NONE
    elif candidate == released:
        relation = InputContractRelation.IDENTICAL
    elif not added:
        relation = InputContractRelation.SUBSET
    elif not dropped:
        relation = InputContractRelation.SUPERSET
    elif not shared:
        relation = InputContractRelation.RENAMED
    else:
        relation = InputContractRelation.PARTIAL

    return InputContractComparison(
        relation=relation,
        added=added,
        dropped=dropped,
        shared=shared,
    )
