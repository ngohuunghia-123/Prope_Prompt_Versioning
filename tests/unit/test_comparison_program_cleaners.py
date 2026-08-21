"""`descriptor_of` and `judgements_of` against a real `dspy.Prediction`.

**Why a real Prediction and not a stub.** These two functions are the boundary
where a model's answer becomes a domain object, and both were written against
`getattr`. A hand-rolled stub with the right attribute names passes that
regardless — which is exactly how the bug below survived: `dspy.Prediction`
inherits a mapping interface from `Example`, so the output field named `keys`
resolves to the bound **method** `Example.keys`, and every extraction raised
`TypeError` before it produced anything.

`extract_output_descriptor` swallows every exception by contract and logs only
the class name, so the failure looked like a prompt that declares no output
contract. The result was that stage 2b never ran: every `output_descriptor`
written since migration 0035 was NULL, and every output-contract comparison
reported *not established* on both sides — a plausible answer, which is what made
it invisible. It was found by counting descriptors after a backfill.

So the assertions here use the type the runtime actually passes.
"""

from __future__ import annotations

import dspy
import pytest

from prope.prompt_search.agent.comparison_program import (
    TaskJudgement,
    descriptor_of,
    judgements_of,
)
from prope.prompt_search.comparison.output_contract import UNSPECIFIED


def test_the_keys_field_is_read_even_though_prediction_defines_keys():
    """The regression. `prediction.keys` is a method; the field is not.

    If this fails with `TypeError: 'method' object is not iterable`, the
    accessor has gone back to `getattr` and the output contract silently stopped
    being extracted everywhere.
    """
    prediction = dspy.Prediction(
        modality="json",
        keys=["decision", "reason"],
        enum_keys=["decision"],
        enum_values=["approve, reject"],
        bare="yes",
        cardinality="one",
        language="en",
        length="short",
    )

    descriptor = descriptor_of(prediction, source_block="output_format")

    assert descriptor.keys == ("decision", "reason")
    assert descriptor.enums == {"decision": ("approve", "reject")}
    assert descriptor.modality == "json"
    assert descriptor.bare == "yes"
    assert descriptor.language == "en"
    assert descriptor.source_block == "output_format"
    assert not descriptor.is_empty


def test_a_silent_prompt_still_yields_a_descriptor_that_says_unspecified():
    """*Undeclared* is a finding about the prompt, not an absence of one.

    A descriptor of every-field-unspecified and a NULL column mean different
    things downstream — the first is the prompt saying nothing, the second is
    nobody having looked — and conflating them is what made the failure above
    read as normal.
    """
    descriptor = descriptor_of(dspy.Prediction(), source_block=UNSPECIFIED)

    assert descriptor.keys == ()
    assert descriptor.modality == UNSPECIFIED
    assert descriptor.is_empty


@pytest.mark.parametrize("field", ["keys", "enum_keys", "enum_values"])
def test_a_field_shadowed_by_a_mapping_method_is_never_returned_as_one(field: str):
    """A callable is discarded rather than passed on.

    `Example` grows methods; a future one colliding with a signature field would
    otherwise reintroduce exactly this bug in a different column. Discarding
    callables makes the collision degrade to *unspecified* instead of to a
    swallowed `TypeError`.
    """
    prediction = dspy.Prediction()
    assert not callable(getattr(descriptor_of(prediction, source_block=UNSPECIFIED), field, None))


def test_judgements_survive_the_same_accessor():
    """The adjudicator's own output field, through the same path.

    Built from `TaskJudgement` rather than from dicts because that is what DSPy's
    typed output field yields, and `judgements_of` reads each item by attribute.
    """
    prediction = dspy.Prediction(
        judgements=[
            TaskJudgement(
                label="C1", relation="same_task", reasons=["same_action_same_object"]
            ),
            TaskJudgement(label="C2", relation="different", reasons=[]),
        ]
    )

    judged = judgements_of(prediction, labels=("C1", "C2"))

    assert judged["C1"] == ("same_task", ("same_action_same_object",))
    assert judged["C2"] == ("different", ())


def test_a_prompt_with_no_discriminating_block_is_never_presented_as_nothing():
    """`present()` must not hand the adjudicator an empty candidate.

    `PRESENTATION_BLOCKS` is `instructions` / `output_format` / `constraints`, so
    a canonical prompt whose content sits entirely in `system`, `context` or
    `examples` used to render as `""`. The model was then asked to compare a real
    prompt against nothing, and it does not abstain: on the labelled set a
    4,500-character prompt presented as zero characters came back `same_task`,
    which resolves to `SAME` and is the recommendation §1.5 calls unrecoverable.
    """
    from prope.prompt_search.comparison.pipeline import present
    from prope.prompt_search.comparison.structural import facts_of

    body = (
        "<system>You are a context compression architect for AI-agent systems.</system>"
        "<context>Agent workloads: tool outputs, logs, RAG chunks, files.</context>"
    )
    facts = facts_of(body)
    assert facts.is_canonical
    assert not facts.blocks.get("instructions")

    presented = present(facts)

    assert presented, "a canonical prompt was presented to the adjudicator as an empty string"
    assert "compression architect" in presented
    # Still labelled, so the model can tell persona from task and weigh it as the
    # weaker evidence it is.
    assert "[system]" in presented


def test_the_per_block_share_is_a_reservation_and_not_a_ceiling():
    """A lone block gets the whole budget; a short block still keeps its guarantee.

    As a hard cap, `limit // 3` meant a prompt the converter placed entirely in
    `<instructions>` was shown a third of the budget and the rest went unspent —
    so raising `PRESENTATION_CHARACTER_LIMIT` bought a single-block prompt only a
    third of the increase. Measured consequence: a prompt pasted against its own
    stored text came back `candidate_narrower`, the adjudicator comparing 4,000
    characters of one side against 1,333 of the identical other.
    """
    from prope.prompt_search.comparison.pipeline import (
        PRESENTATION_CHARACTER_LIMIT,
        present,
    )
    from prope.prompt_search.comparison.structural import facts_of

    limit = PRESENTATION_CHARACTER_LIMIT
    lone = present(facts_of(f"<instructions>{'a' * (limit * 2)}</instructions>"))
    # `[instructions]\n` prefix aside, essentially all of the budget is used.
    assert len(lone) >= limit, f"a single-block prompt used only {len(lone)} of {limit}"

    # The reservation still protects the short, discriminating block from a long
    # neighbour — the property the cap existed for.
    mixed = present(
        facts_of(
            f"<instructions>{'a' * (limit * 2)}</instructions>"
            "<output_format>Return JSON only. Keys: decision, reason.</output_format>"
        )
    )
    assert "Return JSON only" in mixed
    assert "decision, reason" in mixed
