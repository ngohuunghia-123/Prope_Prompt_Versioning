"""A-050's caps, at the edge, in **characters** — and the same numbers the CHECKs carry.

Two rules are enforced twice on purpose, and the duplication is the point rather
than an oversight:

* the **database** CHECKs are what make the cap true regardless of who wrote the
  row, including a future write path and a hand-run ``psql`` session;
* the **pydantic** constraints are what make the author see *"the body is 41,102
  characters and the limit is 32,768"* instead of a 500 naming a constraint they
  cannot read.

A test is needed because two spellings of one number drift, and the drift is
invisible from both sides: a pydantic cap set higher than the CHECK turns an
author's mistake into a server error, and one set lower makes a body the
database would accept unsaveable with no way to find out why.

**Characters, not bytes.** ADR-0053 makes Vietnamese the one interface language,
and the same sentence costs roughly three times as many bytes in Vietnamese as
in English. A byte cap would read to a Vietnamese author as an arbitrary limit
their English colleague does not hit — so the assertions below include a body
that is inside the character cap and far outside any byte one.
"""

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from prope.prompt_registry.domain import (
    MAX_BODY_CHARACTERS,
    MAX_CHANGE_SUMMARY_CHARACTERS,
    MAX_PURPOSE_CHARACTERS,
    MAX_TAG_CHARACTERS,
    MAX_TAGS,
    MAX_TITLE_CHARACTERS,
)
from prope.prompt_registry.schemas import PromptCreate, PromptUpdate, RevisionCreate

MIGRATION = (
    Path(__file__).resolve().parents[2] / "alembic" / "versions" / "0008_registry_schema.py"
)


def _revision(**overrides: object) -> RevisionCreate:
    values: dict[str, object] = {"body": "You are helpful.", "change_summary": "first"}
    values.update(overrides)
    return RevisionCreate(**values)  # type: ignore[arg-type]


def _prompt(**overrides: object) -> PromptCreate:
    values: dict[str, object] = {
        "namespace": "support",
        "name": "refund-classifier",
        "title": "Refund classifier",
    }
    values.update(overrides)
    return PromptCreate(**values)  # type: ignore[arg-type]


def _fields_named(error: ValidationError) -> set[str]:
    return {str(item["loc"][0]) for item in error.errors() if item["loc"]}


def test_a_body_exactly_at_the_cap_is_accepted() -> None:
    """The boundary itself, on the accepting side.

    Asserted because an off-by-one written as ``<`` rather than ``<=`` refuses a
    body the database would take, and nothing else in the suite would notice: the
    only visible symptom is one author, once, unable to save.
    """
    assert len(_revision(body="a" * MAX_BODY_CHARACTERS).body) == MAX_BODY_CHARACTERS


def test_a_body_one_character_over_the_cap_is_refused_naming_the_field() -> None:
    with pytest.raises(ValidationError) as refused:
        _revision(body="a" * (MAX_BODY_CHARACTERS + 1))

    assert _fields_named(refused.value) == {"body"}


def test_an_empty_body_is_refused() -> None:
    """A revision is a saved change, and an empty body is not one.

    The database CHECK caps the length and does not require content, so this half
    of the rule lives only here — which is why it is stated rather than assumed.
    """
    with pytest.raises(ValidationError):
        _revision(body="")


def test_the_cap_counts_characters_and_not_bytes() -> None:
    """A full-cap Vietnamese body is accepted, and it is far over 32,768 bytes.

    ``ề`` is three bytes in UTF-8. A body at the character cap made of it is
    roughly 96 KiB on the wire and must still save, because ADR-0053 makes
    Vietnamese the language this product is written in rather than a translation
    layered over an English one.
    """
    vietnamese = "ề" * MAX_BODY_CHARACTERS

    assert len(_revision(body=vietnamese).body) == MAX_BODY_CHARACTERS
    assert len(vietnamese.encode()) > 3 * MAX_BODY_CHARACTERS - 1


def test_the_change_summary_is_required_and_capped() -> None:
    """A-050 makes it mandatory, and the reason is the search corpus.

    The summary is what recovers *"which prompt did we change for the refund
    thing"* years later — it is folded into ``search_text`` for every revision,
    not only the latest. A field that may be skipped is a field that is skipped.
    """
    with pytest.raises(ValidationError) as missing:
        RevisionCreate(body="x")  # type: ignore[call-arg]
    assert "change_summary" in _fields_named(missing.value)

    with pytest.raises(ValidationError):
        _revision(change_summary="")

    with pytest.raises(ValidationError):
        _revision(change_summary="a" * (MAX_CHANGE_SUMMARY_CHARACTERS + 1))

    assert _revision(change_summary="a" * MAX_CHANGE_SUMMARY_CHARACTERS).change_summary


def test_the_title_is_required_and_the_purpose_is_not() -> None:
    """A prompt with no title is unfindable; a prompt with no purpose is only unexplained."""
    assert _prompt().purpose == ""

    with pytest.raises(ValidationError):
        _prompt(title="")

    with pytest.raises(ValidationError):
        _prompt(title="a" * (MAX_TITLE_CHARACTERS + 1))

    with pytest.raises(ValidationError):
        _prompt(purpose="a" * (MAX_PURPOSE_CHARACTERS + 1))


def test_tags_are_bounded_in_both_directions() -> None:
    """A count cap and a per-tag length cap, because both are unbounded text otherwise.

    ``tags`` is a ``text[]`` with no CHECK behind it, so unlike every other limit
    in this file these two are enforced **here only** — which makes them the ones
    most worth a test.
    """
    assert _prompt(tags=["a" * MAX_TAG_CHARACTERS] * MAX_TAGS).tags

    with pytest.raises(ValidationError):
        _prompt(tags=["ok"] * (MAX_TAGS + 1))

    with pytest.raises(ValidationError):
        _prompt(tags=["a" * (MAX_TAG_CHARACTERS + 1)])

    with pytest.raises(ValidationError):
        _prompt(tags=[""])


def test_the_binding_is_all_or_nothing() -> None:
    """``ck_revision_binding_is_whole``, restated at the edge so the caller gets a 422.

    Not a length rule, and here for the same reason the length rules are: the
    database refuses half a binding either way, and without this the author's
    request came back as a **revision conflict** — the write path retried the
    INSERT, met the CHECK a second time, and reported *somebody else saved
    first* about a race that never happened.
    """
    assert _revision().provider_config_id is None
    assert _revision(provider_config_id="prv_1", upstream_model="gpt-4o-mini").upstream_model

    for half in ({"provider_config_id": "prv_1"}, {"upstream_model": "gpt-4o-mini"}):
        with pytest.raises(ValidationError, match="together or not at all"):
            _revision(**half)


def test_an_unknown_field_is_refused_rather_than_ignored() -> None:
    """``extra="forbid"``, and the field chosen is the one that matters.

    A client that sent ``status: "active"`` believes it can set a status this API
    does not let it set. Ignoring the field would leave that belief intact and
    the mistake would surface much later, as a prompt somebody thought they had
    retired.
    """
    with pytest.raises(ValidationError) as refused:
        PromptCreate(  # type: ignore[call-arg]
            namespace="support", name="refund", title="Refund", status="active"
        )

    assert "status" in _fields_named(refused.value)


def test_the_patch_shape_cannot_rename_a_prompt() -> None:
    """A-021: ``namespace/name`` is immutable, so the field does not exist to send.

    It is what a consuming product calls. A rename breaks every caller at once
    with no error on either side, which is why this is a missing field rather
    than a permission.
    """
    assert "namespace" not in PromptUpdate.model_fields
    assert "name" not in PromptUpdate.model_fields

    with pytest.raises(ValidationError):
        PromptUpdate(namespace="other")  # type: ignore[call-arg]


def test_an_empty_patch_is_a_valid_document() -> None:
    """Every field optional, so *which* fields moved is decided in the handler.

    The refusal for a PATCH that changes nothing belongs at the route, where it
    can say so; a schema that refused it would answer 422 with a message about a
    missing field for a request that is missing nothing.
    """
    assert PromptUpdate().model_dump(exclude_unset=True) == {}


@pytest.mark.parametrize(
    ("constant", "constraint"),
    [
        (MAX_BODY_CHARACTERS, "ck_revision_body_length"),
        (MAX_CHANGE_SUMMARY_CHARACTERS, "ck_revision_change_summary_length"),
        (MAX_TITLE_CHARACTERS, "ck_prompt_property_title_length"),
        (MAX_PURPOSE_CHARACTERS, "ck_prompt_property_purpose_length"),
    ],
)
def test_each_edge_cap_matches_the_number_in_the_migration(constant: int, constraint: str) -> None:
    """The drift guard, read out of the migration source rather than restated.

    A CHECK and a pydantic ``max_length`` that disagree fail in whichever
    direction is larger, and neither failure names the other number. Reading the
    migration text is crude, and it is crude in the safe direction: it cannot
    pass while the two disagree.
    """
    source = MIGRATION.read_text(encoding="utf-8")

    found = re.search(rf"{constraint}[^\n]*?<=\s*(\d+)", source)
    assert found is not None, f"{constraint} is not in {MIGRATION.name} in the expected shape"
    assert int(found.group(1)) == constant
