"""AC-4 — the ``vi`` catalogue is TOTAL over the rule catalogue, checked in CI.

**ADR-0053 makes the client render the ``code``, never the ``message``**, and
this module has no ``message`` on the wire at all: a finding is a ``rule_id``, a
``params`` dict and nothing else. That design has exactly one failure mode, and
it is silent — a rule added in ``domain.py`` with no key here renders as a blank
row on a readiness card. A blank warning is worse than no card, because the
reader can see that something was found and cannot see what.

**The check has to cross the language boundary to be worth anything.** The Python
enum and the TypeScript catalogue are the two artifacts that must agree, and
nothing in either toolchain can see the other — ``tsc`` does not know ``RuleId``
exists and ``mypy`` does not read ``.ts``. So this reads both, the way
``test_migrate_skill_agrees_with_canonical_xml`` reads a skill file and a Python
module and refuses to let them drift.

The parse is deliberately dumb — brace counting over string-stripped source,
against a prettier-formatted file. A real TypeScript parser here would be a
dependency added so a test could be cleverer than the thing it guards.
"""

import re
from pathlib import Path

import pytest

from prope.prompt_readiness.domain import RuleId, Severity, lane_for_rule
from prope.prompt_readiness.profile import _ADMISSION_STEM

LOCALES = Path(__file__).resolve().parents[2] / "src" / "prope-fe" / "locales"
CATALOGUES = {"vi": LOCALES / "readiness.vi.ts", "en": LOCALES / "readiness.en.ts"}

#: The refusal codes ``POST .../probe`` can answer with. Each needs a sentence,
#: because a refusal the client cannot name renders as the generic *try again* —
#: which is wrong advice for a spend ceiling and useless advice for a revision
#: with no model bound.
PROBE_REFUSALS = ("spend_ceiling_reached", "no_applicable_sets", "revision_has_no_binding")

#: Every key a rule entry owes. ``action`` is included: a finding with no
#: suggested next step is the alert-fatigue shape this module exists to measure
#: in other people's tools.
RULE_KEYS = frozenset({"title", "body", "action"})


def _stripped(path: Path) -> str:
    """Source with string literals and comments blanked, so braces can be counted.

    Rule bodies are full of ``{{count}}`` interpolations and the file opens with a
    doc comment that quotes them. Both are balanced, so counting would *probably*
    work — but "probably balanced" is not a property anybody maintains, and the
    day somebody writes ``'{'`` this test would fail in a way that looks like a
    missing key.
    """
    source = path.read_text(encoding="utf-8")
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    source = re.sub(r"//[^\n]*", "", source)
    source = re.sub(r"'(?:[^'\\\n]|\\.)*'", "''", source)
    return re.sub(r'"(?:[^"\\\n]|\\.)*"', '""', source)


def _block(source: str, path: tuple[str, ...]) -> str:
    """The body of a nested object literal, addressed like ``("probe", "refusal")``."""
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
        else:  # pragma: no cover - an unbalanced literal fails tsc long before this
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
def test_every_rule_has_an_entry(language: str) -> None:
    """The one that matters. A rule with no key is a blank row on somebody's card."""
    present = _keys(_block(_stripped(CATALOGUES[language]), ("rule",)))
    missing = sorted(str(rule) for rule in RuleId if str(rule) not in present)
    assert missing == [], (
        f"{CATALOGUES[language].name} has no entry for {missing}. The API sends a `code` and "
        "nothing else (ADR-0053), so a rule with no key renders as an empty warning."
    )


@pytest.mark.parametrize("language", sorted(CATALOGUES))
def test_no_entry_names_a_rule_that_does_not_exist(language: str) -> None:
    """The other direction. A stale key is a sentence nobody will ever see again.

    Harmless at runtime and precisely why it survives — so it is caught here,
    where the cost of removing it is one line.
    """
    known = {str(rule) for rule in RuleId}
    present = _keys(_block(_stripped(CATALOGUES[language]), ("rule",)))
    assert sorted(present - known) == []


@pytest.mark.parametrize("language", sorted(CATALOGUES))
def test_every_entry_carries_a_title_a_body_and_an_action(language: str) -> None:
    stripped = _stripped(CATALOGUES[language])
    for rule in RuleId:
        keys = _keys(_block(stripped, ("rule", str(rule))))
        assert RULE_KEYS <= keys, f"{language}/{rule} is missing {sorted(RULE_KEYS - keys)}"


@pytest.mark.parametrize("language", sorted(CATALOGUES))
def test_the_supporting_vocabularies_are_total(language: str) -> None:
    """Lanes, severities, admission clauses and refusals — each a closed set in Python.

    The lane badge is the part a reader uses to weigh a row: *measured* and
    *the model suggested* are not the same claim, and an untranslated badge would
    flatten that distinction into a raw identifier.
    """
    stripped = _stripped(CATALOGUES[language])

    lanes = {lane_for_rule(rule) for rule in RuleId}
    assert lanes <= _keys(_block(stripped, ("lane",)))
    assert {member.value for member in Severity} <= _keys(_block(stripped, ("severity",)))

    clauses = set(_ADMISSION_STEM.values()) | {"always"}
    assert clauses <= _keys(_block(stripped, ("admitted",)))

    assert set(PROBE_REFUSALS) <= _keys(_block(stripped, ("probe", "refusal")))


def test_the_two_catalogues_declare_the_same_keys() -> None:
    """``en`` is a development convenience and drift in it is still drift.

    Vietnamese is the MVP's interface language (ADR-0053), so ``vi`` is the one
    the four non-negotiables are read in. But a key that exists in only one file
    means one of the two was edited without the other, and the next edit is a
    coin flip about which is current.
    """
    blocks = [("rule",), ("card",), ("lane",), ("severity",), ("admitted",), ("probe",)]
    for block in blocks:
        vi = _keys(_block(_stripped(CATALOGUES["vi"]), block))
        en = _keys(_block(_stripped(CATALOGUES["en"]), block))
        assert vi == en, f"{'.'.join(block)} differs: vi-only={sorted(vi - en)}, en-only={sorted(en - vi)}"


def test_the_catalogue_is_registered_at_the_translation_root() -> None:
    """``t('readiness.card.title')`` resolves only if ``vi.ts`` imports and mounts it.

    A catalogue that is complete and unmounted fails exactly the same way as a
    catalogue with no keys, and does it while every assertion above passes.
    """
    for language in ("vi", "en"):
        root = (LOCALES / f"{language}.ts").read_text(encoding="utf-8")
        assert f"readiness.{language}" in root, f"{language}.ts does not import the catalogue"
        assert re.search(rf"^    readiness: readiness{language.capitalize()},$", root, re.MULTILINE), (
            f"{language}.ts imports the catalogue but does not mount it at the translation root"
        )
