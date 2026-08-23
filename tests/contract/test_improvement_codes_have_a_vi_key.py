"""AC-11 — the ``vi`` catalogue is TOTAL over this module's closed vocabularies.

Same contract as ``test_readiness_rules_have_a_vi_key`` and the same reason: the
API sends a machine ``code`` and numbers, the client owns every sentence
(ADR-0053), and the single failure mode of that design is silent. **A detector
added in ``domain.py`` with no key here renders as an empty row in somebody's
inbox** — visibly a finding, invisibly about nothing.

**It is worse here than it is for readiness**, which is why this file checks more
than the detector map. A readiness card is advisory and read beside the body it
describes. This is a queue of things that are wrong in production, and a row that
cannot say what is wrong is a row that gets dismissed — and a dismissal is a
counted signal (OQ-157) that would then be measuring the translation catalogue
rather than the detector.

The parse is the same deliberately dumb brace-count over string-blanked source,
shared in spirit with the readiness test rather than imported from it: two
independent readers of two independent catalogues is the point, and a shared
helper would mean one bug hides both.
"""

import re
from pathlib import Path

import pytest

from prope.prompt_improvement.domain import (
    REACHABLE_FAMILIES,
    DetectorId,
    RemedyFamily,
    RemedyKind,
    Severity,
)
from prope.prompt_improvement.remedies import RemedyRefused, apply

LOCALES = Path(__file__).resolve().parents[2] / "src" / "prope-fe" / "locales"
CATALOGUES = {"vi": LOCALES / "improvement.vi.ts", "en": LOCALES / "improvement.en.ts"}

#: Every detector entry owes these three. ``action`` is not decoration: a finding
#: with no suggested next step is exactly the alert-fatigue shape (deck 6 slide
#: 64) this module was built to avoid producing.
DETECTOR_KEYS = frozenset({"title", "body", "action"})

#: A family entry owes a title and a description, because the description is what
#: a reviewer reads to decide whether the transform is the right one — the card
#: deliberately shows no model-written rationale (ADR-0068 §4), so this text is
#: the whole of what explains the proposed change.
FAMILY_KEYS = frozenset({"title", "body"})


def _stripped(path: Path) -> str:
    """Source with comments and string literals blanked, so braces can be counted."""
    source = path.read_text(encoding="utf-8")
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    source = re.sub(r"//[^\n]*", "", source)
    source = re.sub(r"'(?:[^'\\\n]|\\.)*'", "''", source)
    return re.sub(r'"(?:[^"\\\n]|\\.)*"', '""', source)


def _block(source: str, path: tuple[str, ...]) -> str:
    """The body of a nested object literal, addressed like ``("detector",)``."""
    cursor = 0
    body = source
    for name in path:
        match = re.search(rf"\b{name}:\s*\{{", body[cursor:])
        assert match, f"no `{name}:` block under {path}"
        start = cursor + match.end() - 1
        depth = 0
        for index in range(start, len(body)):
            depth += (body[index] == "{") - (body[index] == "}")
            if depth == 0:
                body, cursor = body[start + 1 : index], 0
                break
        else:  # pragma: no cover - unbalanced literals fail tsc long before this
            raise AssertionError(f"unbalanced braces reading {path}")
    return body


def _keys(block: str) -> set[str]:
    """Keys declared directly in a block, ignoring anything nested inside it."""
    keys: set[str] = set()
    depth = 0
    for line in block.splitlines():
        if depth == 0:
            match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*):", line)
            if match:
                keys.add(match.group(1))
        depth += line.count("{") - line.count("}")
    return keys


@pytest.mark.parametrize("language", sorted(CATALOGUES))
def test_every_detector_has_an_entry(language: str) -> None:
    """The one that matters. A detector with no key is a blank row in the inbox."""
    present = _keys(_block(_stripped(CATALOGUES[language]), ("detector",)))
    missing = sorted(str(detector) for detector in DetectorId if str(detector) not in present)
    assert missing == [], (
        f"{CATALOGUES[language].name} has no entry for {missing}. The API sends a `detector_id` "
        "and a `params` dict and nothing else (ADR-0053), so a detector with no key renders as "
        "an empty finding — visibly something, invisibly about nothing."
    )


@pytest.mark.parametrize("language", sorted(CATALOGUES))
def test_no_entry_names_a_detector_that_does_not_exist(language: str) -> None:
    """The other direction. A stale key is a sentence nobody will ever see again.

    Harmless at runtime, which is exactly why it survives — so it is caught here,
    where removing it costs one line.
    """
    known = {str(detector) for detector in DetectorId}
    present = _keys(_block(_stripped(CATALOGUES[language]), ("detector",)))
    assert sorted(present - known) == []


@pytest.mark.parametrize("language", sorted(CATALOGUES))
def test_every_detector_entry_carries_a_title_a_body_and_an_action(language: str) -> None:
    stripped = _stripped(CATALOGUES[language])
    for detector in DetectorId:
        keys = _keys(_block(stripped, ("detector", str(detector))))
        assert DETECTOR_KEYS <= keys, (
            f"{language}/{detector} is missing {sorted(DETECTOR_KEYS - keys)}"
        )


@pytest.mark.parametrize("language", sorted(CATALOGUES))
def test_every_remedy_family_is_described_in_the_reader_s_language(language: str) -> None:
    """**The family description is the whole explanation of a proposed edit.**

    ADR-0068 §4 refuses to render a model-written rationale, so nothing else on
    the card says what the change does. An untranslated family would leave a
    reviewer approving a body diff with a raw identifier above it, which is the
    rubber-stamp shape the eval gate exists to prevent — arriving through the
    interface instead of through the queue.
    """
    stripped = _stripped(CATALOGUES[language])
    present = _keys(_block(stripped, ("family",)))

    assert {str(family) for family in RemedyFamily} <= present
    for family in RemedyFamily:
        keys = _keys(_block(stripped, ("family", str(family))))
        assert FAMILY_KEYS <= keys, f"{language}/{family} is missing {sorted(FAMILY_KEYS - keys)}"


@pytest.mark.parametrize("language", sorted(CATALOGUES))
def test_the_supporting_vocabularies_are_total(language: str) -> None:
    """Severity and remedy kind — two closed sets in Python, two badges on a row.

    ``kind`` carries real weight: *information*, *proposed cases* and *proposed
    edit* ask three different things of a reader, and an untranslated badge
    flattens them into one identifier that suggests nothing about what accepting
    would do.
    """
    stripped = _stripped(CATALOGUES[language])

    assert {member.value for member in Severity} <= _keys(_block(stripped, ("severity",)))
    assert {member.value for member in RemedyKind} <= _keys(_block(stripped, ("kind",)))


@pytest.mark.parametrize("language", sorted(CATALOGUES))
def test_the_gate_s_honest_limit_is_on_the_card(language: str) -> None:
    """**The one sentence that must not be dropped in translation.**

    *"Did not regress on this suite" is exactly as strong as the suite* — the
    26/30 → 9/30 collapse. A gate result rendered without it reads as an
    endorsement, and a reviewer who reads it that way is doing the rubber-stamp
    this module's whole design is built to refuse. So the key is asserted by name
    rather than left to the general totality checks, which would happily pass a
    catalogue that had quietly lost it.
    """
    keys = _keys(_block(_stripped(CATALOGUES[language]), ("proposal",)))

    assert "gateLimit" in keys, "the gate result would render as an endorsement without it"
    assert "acceptHint" in keys, "accepting writes nothing, and the card has to say so (SR-6)"


def test_the_two_catalogues_declare_the_same_keys() -> None:
    """``en`` is a development convenience and drift in it is still drift.

    A key in only one file means one was edited without the other, and the next
    edit is a coin flip about which is current.
    """
    for block in [("inbox",), ("severity",), ("proposal",), ("kind",), ("family",),
                  ("schedule",), ("detector",)]:
        vi = _keys(_block(_stripped(CATALOGUES["vi"]), block))
        en = _keys(_block(_stripped(CATALOGUES["en"]), block))
        assert vi == en, (
            f"{'.'.join(block)} differs: vi-only={sorted(vi - en)}, en-only={sorted(en - vi)}"
        )


def test_the_catalogue_is_registered_at_the_translation_root() -> None:
    """A catalogue that is complete and unmounted fails exactly like an empty one.

    ``t('improvement.detector.fallback_rising.title')`` resolves only if the root
    file both imports and mounts it — and it does so while every assertion above
    passes, which is what makes this worth a separate test.
    """
    for language in ("vi", "en"):
        root = (LOCALES / f"{language}.ts").read_text(encoding="utf-8")
        assert f"improvement.{language}" in root, f"{language}.ts does not import the catalogue"
        assert re.search(
            rf"^    improvement: improvement{language.capitalize()},$", root, re.MULTILINE
        ), f"{language}.ts imports the catalogue but does not mount it at the translation root"


def test_a_family_s_clause_is_written_in_the_interface_language() -> None:
    """The one string this module generates that no catalogue can translate.

    ``remedies`` writes its clause directly into a prompt body, so it is not a
    ``code`` the client renders — it is text a person may release. ADR-0053's
    boundary does not reach it, and the lock records that as a stated limitation
    rather than a gap. This asserts the limitation is the one that was accepted:
    the clause is Vietnamese, matching the pilot's prompts, and a change to
    English would be a decision somebody has to make on purpose.
    """
    for family in RemedyFamily:
        try:
            candidate = apply("<system>Xin chào.</system>", family)
        except RemedyRefused as refusal:  # pragma: no cover - none of the three refuse here
            raise AssertionError(f"{family} refused a minimal body: {refusal.code}") from refusal
        # A Vietnamese diacritic, which no English clause would carry.
        assert re.search(r"[ăâđêôơưàáảãạèéẻẽẹìíỉĩịòóỏõọùúủũụ]", candidate, re.IGNORECASE), family


def test_every_reachable_family_is_reachable_from_a_translated_detector() -> None:
    """The two maps and the catalogue, joined once.

    A family reachable only from a detector with no ``vi`` key would render as a
    proposal attached to a blank finding. Each half is covered above; this is the
    join, and it is the shape that actually reaches a person.
    """
    present = _keys(_block(_stripped(CATALOGUES["vi"]), ("detector",)))

    for detector, families in REACHABLE_FAMILIES.items():
        assert str(detector) in present, detector
        assert families, detector
