"""The ``vi`` catalogue is TOTAL over the comparison funnel's closed vocabularies.

Same contract as ``test_readiness_rules_have_a_vi_key`` and
``test_improvement_codes_have_a_vi_key``, and the same reason: the API sends a
machine ``code`` and a ``params`` dict, the client owns every sentence
(ADR-0053), and the single failure mode of that design is silent.

**Here the missing key renders as the code itself**, because i18next falls back
to the key. A row reading ``similar.output_contract.bare_relaxed`` on the import
dialog is worse than no finding: the reader is being warned about something in a
language nobody speaks, on the one screen where the wrong answer — attaching an
incoming prompt as a revision of an unrelated one — is the path of least
resistance.

The parse is the same deliberately dumb brace-count over string-blanked source
as its two siblings, and it is duplicated rather than shared for the reason
stated there: independent readers of independent catalogues is the point, and a
shared helper would mean one bug hides all three.
"""

import re
from pathlib import Path

import pytest

from prope.prompt_search.comparison.domain import FINDING_CODES, REASON_CODES, Verdict
from prope.prompt_search.comparison.trace import STEP_CODES

LOCALES = Path(__file__).resolve().parents[2] / "src" / "prope-fe" / "locales"
CATALOGUES = {"vi": LOCALES / "lifecycle.vi.ts", "en": LOCALES / "lifecycle.en.ts"}


def _stripped(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    source = re.sub(r"//[^\n]*", "", source)
    source = re.sub(r"'(?:[^'\\\n]|\\.)*'", "''", source)
    return re.sub(r'"(?:[^"\\\n]|\\.)*"', '""', source)


def _block(source: str, path: tuple[str, ...]) -> str:
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
    keys: set[str] = set()
    depth = 0
    for line in block.splitlines():
        if depth == 0:
            match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*):", line)
            if match:
                keys.add(match.group(1))
        depth += line.count("{") - line.count("}")
    return keys


def _code_path(code: str) -> tuple[str, ...]:
    """``similar.input_contract.renamed`` -> the catalogue path under ``similarity``.

    The ``similar.`` prefix is dropped and the rest is a nested path, which is
    exactly what the dialog does when it builds the key. Encoding that mapping in
    two places is deliberate: if either side changes the shape, this test fails
    rather than the screen silently rendering identifiers.
    """
    return ("similarity", "findings", *code.removeprefix("similar.").split("."))


@pytest.mark.parametrize("language", sorted(CATALOGUES))
def test_every_finding_code_has_a_sentence(language: str) -> None:
    stripped = _stripped(CATALOGUES[language])
    missing: list[str] = []
    for code in FINDING_CODES:
        *parent, leaf = _code_path(code)
        if leaf not in _keys(_block(stripped, tuple(parent))):
            missing.append(code)
    assert missing == [], (
        f"{CATALOGUES[language].name} has no sentence for {missing}. The API sends a `code` and "
        "a `params` dict and nothing else (ADR-0053), so a code with no key renders as itself."
    )


@pytest.mark.parametrize("language", sorted(CATALOGUES))
def test_no_sentence_names_a_code_that_does_not_exist(language: str) -> None:
    """The other direction: a stale key is a sentence nobody will ever see again."""
    stripped = _stripped(CATALOGUES[language])
    known = {_code_path(code) for code in FINDING_CODES}
    for axis in _keys(_block(stripped, ("similarity", "findings"))):
        for leaf in _keys(_block(stripped, ("similarity", "findings", axis))):
            assert ("similarity", "findings", axis, leaf) in known, (
                f"{CATALOGUES[language].name} translates similar.{axis}.{leaf}, which no code emits"
            )


@pytest.mark.parametrize("language", sorted(CATALOGUES))
def test_every_verdict_has_a_label_and_a_hint(language: str) -> None:
    """A verdict with no words is a badge that says nothing beside a decision.

    The hint matters as much as the label: `supersedes` and `variant` are exactly
    the two verdicts a reader has no prior intuition for, and they are the two
    where the obvious action is the wrong one.
    """
    stripped = _stripped(CATALOGUES[language])
    labels = _keys(_block(stripped, ("similarity", "verdict")))
    hints = _keys(_block(stripped, ("similarity", "verdictHint")))
    expected = {verdict.value for verdict in Verdict}
    assert expected <= labels, f"{language} verdict labels missing {sorted(expected - labels)}"
    assert expected <= hints, f"{language} verdict hints missing {sorted(expected - hints)}"


@pytest.mark.parametrize("language", sorted(CATALOGUES))
def test_every_adjudicator_reason_has_a_sentence(language: str) -> None:
    """The reason codes are the whole of *why* a verdict was reached.

    The adjudicator is constrained to this closed vocabulary precisely so its
    answer can be translated and counted rather than rendered as whatever the
    model felt like writing. An untranslated code turns that guarantee inside
    out: the reader is shown `candidate_covers_more_cases` on the one screen
    where they are being asked to decide whether to keep their own prompt.
    """
    present = _keys(_block(_stripped(CATALOGUES[language]), ("similarity", "reason")))
    missing = sorted(code for code in REASON_CODES if code not in present)
    assert missing == [], f"{CATALOGUES[language].name} has no sentence for {missing}"


@pytest.mark.parametrize("language", sorted(CATALOGUES))
def test_no_reason_sentence_names_a_code_the_adjudicator_cannot_return(language: str) -> None:
    present = _keys(_block(_stripped(CATALOGUES[language]), ("similarity", "reason")))
    assert sorted(present - set(REASON_CODES)) == []


@pytest.mark.parametrize("language", sorted(CATALOGUES))
def test_every_funnel_step_has_a_name_and_a_sentence(language: str) -> None:
    """The trace sheet renders these while somebody waits on it.

    Two keys per rung, and both are load-bearing. ``step`` is the row's name;
    ``detail`` is what it did, and it is the half that carries the counts — the
    difference between *"Compare the job"* and *"one call over 5 candidates, 5
    judged"*. A rung whose name renders as ``output_contract`` on a progress
    display is the ADR-0053 failure at its most visible: the screen is up
    precisely because the person is being asked to wait for it.
    """
    stripped = _stripped(CATALOGUES[language])
    names = _keys(_block(stripped, ("similarity", "trace", "step")))
    details = _keys(_block(stripped, ("similarity", "trace", "detail")))
    expected = set(STEP_CODES)
    assert expected <= names, f"{language} trace step names missing {sorted(expected - names)}"
    assert expected <= details, f"{language} trace step details missing {sorted(expected - details)}"


@pytest.mark.parametrize("language", sorted(CATALOGUES))
def test_no_trace_sentence_names_a_step_the_funnel_cannot_report(language: str) -> None:
    stripped = _stripped(CATALOGUES[language])
    for section in ("step", "detail"):
        present = _keys(_block(stripped, ("similarity", "trace", section)))
        assert sorted(present - set(STEP_CODES)) == []


@pytest.mark.parametrize("language", sorted(CATALOGUES))
def test_every_rung_state_has_a_sentence_including_the_ones_that_did_not_run(
    language: str,
) -> None:
    """`skipped` and `failed` are the two that matter and the two easiest to omit.

    A rung that did not run and a rung that ran and found nothing are different
    facts about the answer, and the whole reason the trace is on screen is that
    *"no duplicates"* means one thing when every rung ran and another when the
    adjudicator was unavailable.
    """
    present = _keys(_block(_stripped(CATALOGUES[language]), ("similarity", "trace", "state")))
    expected = {"pending", "running", "skipped", "failed"}
    assert expected <= present, f"{language} trace states missing {sorted(expected - present)}"
