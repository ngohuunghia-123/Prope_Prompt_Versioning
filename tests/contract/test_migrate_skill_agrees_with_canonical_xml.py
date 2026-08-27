"""`register.py` copies `validate_canonical_xml`. This is what stops the copy rotting.

ADR-0066's script runs in a **customer's** repository, where Prope is not
installed, so it cannot import `prope.canonical_prompt` — it reimplements the
rule. That duplication is deliberate and it buys something real: a manifest of
forty prompts fails on the eleventh *before the first one is created*, naming the
prompt, instead of arriving as a 422 halfway through a partial import.

What it costs is the usual cost of two implementations of one rule: they agree
today. This file is the reason they keep agreeing, and it fails on the change
that would otherwise be discovered by a customer.

Loaded by path rather than imported, because `skills/` is not a package and
should not become one — it is a directory of things that get copied into
somebody else's repository.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

from prope.canonical_prompt import ALLOWED_BLOCKS, MAX_CANONICAL_CHARACTERS, validate_canonical_xml

SKILL = pathlib.Path(__file__).resolve().parents[2] / "skills" / "prope-migrate" / "register.py"


def _load_register():  # noqa: ANN202
    spec = importlib.util.spec_from_file_location("prope_migrate_register", SKILL)
    assert spec and spec.loader, SKILL
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


register = _load_register()


BODIES = [
    "<system>You are helpful.</system>",
    "<system>a</system><instructions>b</instructions><constraints>c</constraints>",
    "<system>Today is {{today}}.</system>",
    "<examples>in: x\nout: y</examples>",
    "<system>Angle brackets: &lt;tag&gt; and an ampersand &amp;.</system>",
    "<context>multi\nline\ntext</context>",
    # --- the nameless block: one body, kept whole, accepted by both ---
    "<>\nYou are helpful.\n</>",
    # Every one of these would be refused as a named-block body, and must be
    # accepted here: inside `<>` nothing is parsed, so nothing can be malformed.
    "<>\nUse a <div> tag and an & ampersand.\n</>",
    "<>\n<!DOCTYPE html> is how an HTML document opens.\n</>",
    "<>\n<persona>not a canonical block</persona>\n</>",
    "<>\nunclosed <tag\n</>",
    "<>\nToday is {{today}}.\n</>",
    # --- each of these must be refused, and by both ---
    "",
    "   ",
    "You are helpful.",
    "You are helpful.<system>Hi</system>",
    "<system>Hi</system>trailing text",
    "<persona>You are helpful.</persona>",
    "<system tone='warm'>Hi</system>",
    "<system>Hi <instructions>no</instructions></system>",
    "<system>unclosed",
    "<system>Hi</system><!DOCTYPE foo>",
    "<!ENTITY x 'y'><system>Hi</system>",
    "<>",
    "</>",
    "<>unclosed",
    # A verbatim body is the WHOLE body; two of them is neither form.
    "<>\na\n</>\n<system>b</system>",
    "<system></system>",
    "x" * (MAX_CANONICAL_CHARACTERS + 1),
    f"<system>{'x' * (MAX_CANONICAL_CHARACTERS + 1)}</system>",
]


def _service_accepts(body: str) -> bool:
    try:
        validate_canonical_xml(body)
    except ValueError:
        return False
    return True


def _skill_accepts(body: str) -> bool:
    try:
        register.check_canonical(body)
    except register.RefusedError:
        return False
    return True


@pytest.mark.parametrize("body", BODIES, ids=lambda body: repr(body[:40]))
def test_the_skill_and_the_service_reach_the_same_verdict(body: str) -> None:
    """The property that matters, in both directions.

    A skill that accepted what the service rejects produces a partial import and
    a confusing 422. A skill that rejected what the service accepts is worse: it
    refuses a prompt the customer is entitled to register, in a script they
    cannot patch remotely, with an error message Prope wrote.
    """
    assert _skill_accepts(body) == _service_accepts(body), body[:80]


def test_the_two_block_vocabularies_are_the_same_set() -> None:
    """The likeliest drift: a block is added to the service and not to the copy.

    Asserted as set equality rather than a subset, because a block the skill
    knows and the service does not is the same defect pointing the other way.
    """
    assert register.ALLOWED_BLOCKS == ALLOWED_BLOCKS


def test_the_size_limits_are_the_same_number() -> None:
    assert register.MAX_CANONICAL_CHARACTERS == MAX_CANONICAL_CHARACTERS


def test_the_skill_names_the_prompt_it_refused() -> None:
    """The whole reason the duplication exists: a message a person can act on."""
    problems = register.check_entry(
        {
            "namespace": "support",
            "name": "broken",
            "title": "t",
            "body": "<persona>no such block</persona>",
            "sources": [{"file": "a.py"}],
        },
        11,
    )

    assert any("prompts[11]" in problem and "support/broken" in problem for problem in problems)
    assert any("persona" in problem for problem in problems)


def test_an_undeclared_placeholder_is_refused_before_anything_is_created() -> None:
    """A prompt whose body needs a variable the manifest does not list registers
    fine and then fails at run time with `missing_variable` — for every caller,
    after the migration has already shipped."""
    problems = register.check_entry(
        {
            "namespace": "support",
            "name": "x",
            "title": "t",
            "body": "<system>Today is {{today}}.</system>",
            "variables": [],
            "sources": [{"file": "a.py"}],
        },
        0,
    )

    assert any("today" in problem for problem in problems)


def test_the_conversion_schema_version_is_the_services_own() -> None:
    """The third copied constant, and the one whose drift is silent.

    `conversion_schema_version` describes the stored artifact — six blocks, no
    attributes, no nesting — so a revision written by the migration and one
    written by `prompt_conversion` must claim the same version or the field
    stops meaning anything. A wrong value here is not refused by anything: it is
    a string column, and the damage shows up years later when somebody filters
    on it.
    """
    from prope.prompt_conversion.service import SCHEMA_VERSION

    assert register.CONVERSION_SCHEMA_VERSION == SCHEMA_VERSION
