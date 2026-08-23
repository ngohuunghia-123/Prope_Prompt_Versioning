"""AC-10 and SR-4. A candidate body is canonical XML with the same variable set.

**This is the test that keeps a remedy from being a rewrite.** ADR-0068 §3 says
the model picks a family and code produces the body; the property that makes that
worth anything is that the code's transform is bounded — it adds or replaces one
whole block, never reaches inside one carrying an interpolation, and leaves the
declared-variable set untouched. A remedy that dropped a ``{{variable}}`` would
break every call site the moment somebody released it, which is a far worse
outcome than the anomaly it was answering.

**No model and no database here either.** ``apply`` is a pure function over a
string, which is the point: the one artefact in this module that a person might
save into production is produced by code that can be exercised exhaustively from
a test file.
"""

import pytest

from prope.canonical_prompt import ALLOWED_BLOCKS, validate_canonical_xml
from prope.prompt_composition import required_variables
from prope.prompt_improvement import remedies
from prope.prompt_improvement.domain import REACHABLE_FAMILIES, RemedyFamily

#: A body with interpolations in two blocks, which is what makes the round-trip
#: assertion mean something. A single-variable fixture would pass against a
#: transform that happened to preserve the first one it saw.
BODY = (
    "<system>Bạn là trợ lý hỗ trợ khách hàng của {{company}}.</system>"
    "<instructions>Trả lời câu hỏi {{question}} dựa trên {{context_docs}}.</instructions>"
)


@pytest.mark.parametrize("family", list(RemedyFamily))
def test_every_family_produces_canonical_xml_with_the_same_variables(
    family: RemedyFamily,
) -> None:
    """The round trip, for every family in the closed catalogue.

    Parametrised over ``RemedyFamily`` rather than over a literal list, so a
    fourth family added without a transform fails here — before it can be
    offered to somebody as a body to save.
    """
    candidate = remedies.apply(BODY, family)

    validate_canonical_xml(candidate)
    assert required_variables(candidate) == required_variables(BODY)
    assert required_variables(candidate) == ("company", "question", "context_docs")


@pytest.mark.parametrize("family", list(RemedyFamily))
def test_a_family_writes_into_a_block_the_contract_allows(family: RemedyFamily) -> None:
    """The clause goes into a canonical block, never into ``<instructions>``.

    ``<instructions>`` is where the interpolations live in every body this
    product produces. A transform that wrote there would be adding text beside
    the thing SR-4 exists to protect, and the accident it invites is one nobody
    would see until release.
    """
    block_tag, _ = remedies.clause_for(family)

    assert block_tag in ALLOWED_BLOCKS
    assert block_tag != "instructions"


@pytest.mark.parametrize("family", list(RemedyFamily))
def test_applying_the_same_family_twice_is_refused(family: RemedyFamily) -> None:
    """**The module does not argue with a fix somebody already took.**

    Proposing a clause that is already in the body is the shape of nagging that
    gets a tool switched off — deck 6 slide 64 arriving through the remedy side
    rather than the detector side. The refusal is a ``code``, not a silent
    no-op, so the sweep can count it rather than quietly proposing nothing.
    """
    once = remedies.apply(BODY, family)

    with pytest.raises(remedies.RemedyRefused) as refusal:
        remedies.apply(once, family)

    assert refusal.value.code == "clause_already_present"


def test_a_missing_block_is_created_and_an_existing_one_is_appended_to() -> None:
    """Two shapes, one transform, and never two blocks with the same tag.

    ``BODY`` has no ``<constraints>``, so the refusal clause creates one. Applied
    to a body that already has constraints, the same family appends to it — the
    existing text survives, because a remedy that replaced somebody's constraints
    with Prope's would be destroying a decision to answer a metric.
    """
    created = remedies.apply(BODY, RemedyFamily.TIGHTEN_REFUSAL_BLOCK)
    assert created.count("<constraints>") == 1

    with_constraints = BODY + "<constraints>Không đưa ra lời khuyên y tế.</constraints>"
    appended = remedies.apply(with_constraints, RemedyFamily.TIGHTEN_REFUSAL_BLOCK)

    assert appended.count("<constraints>") == 1
    assert "Không đưa ra lời khuyên y tế." in appended


def test_a_block_carrying_an_interpolation_is_left_alone() -> None:
    """The refusal that keeps SR-4 true by construction rather than by luck.

    A ``<constraints>`` block with a ``{{variable}}`` in it cannot have its text
    rewritten without risking the variable, and inventing a second
    ``<constraints>`` beside it is a shape nothing else in this product produces.
    So the transform declines, the anomaly gets no edit proposal, and the person
    gets a finding they can act on themselves — which is strictly better than a
    candidate nobody can trust.
    """
    interpolated = BODY + "<constraints>Chỉ trả lời trong phạm vi {{scope}}.</constraints>"

    with pytest.raises(remedies.RemedyRefused) as refusal:
        remedies.apply(interpolated, RemedyFamily.TIGHTEN_REFUSAL_BLOCK)

    assert refusal.value.code == "block_carries_an_interpolation"


def test_an_unparseable_body_gets_no_candidate() -> None:
    """No guessing. A body that will not parse produces a refusal, not a repair.

    prompt-registry refuses such a body at save, so reaching this means the row
    predates a validation change. Reconstructing a candidate from it is where a
    bounded transform would start inventing, and the whole argument for this
    module's safety is that it does not.
    """
    with pytest.raises(remedies.RemedyRefused) as refusal:
        remedies.apply("<system>unclosed", RemedyFamily.ADD_BREVITY_CLAUSE)

    assert refusal.value.code == "body_is_not_canonical_xml"

    with pytest.raises(remedies.RemedyRefused):
        remedies.apply("", RemedyFamily.ADD_LENGTH_RULE)


def test_no_family_exists_that_a_detector_cannot_reach() -> None:
    """The catalogue and the reachability map agree, in both directions.

    A family with no detector behind it is a transform waiting for somebody to
    call it from somewhere unsanctioned; a detector pointing at a family that
    does not exist is a ``KeyError`` in a background job. Neither shows up
    anywhere else, because the two maps live in different files.
    """
    reachable = {family for families in REACHABLE_FAMILIES.values() for family in families}

    assert reachable == set(RemedyFamily)
    for family in reachable:
        assert remedies.clause_for(family)


@pytest.mark.parametrize("family", list(RemedyFamily))
def test_the_clause_carries_no_interpolation_of_its_own(family: RemedyFamily) -> None:
    """A clause with a ``{{...}}`` in it would ADD to the declared variable set.

    That is the other direction of SR-4 and it is easier to get wrong: nothing
    about the round-trip check is asymmetric, but a clause written by somebody
    reaching for a nice placeholder would fail it at runtime, on a candidate,
    inside a sweep. Catching it here costs nothing.
    """
    _, clause = remedies.clause_for(family)

    assert required_variables(clause) == ()
