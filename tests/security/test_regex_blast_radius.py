"""AC-11 and T-009 — a user-authored regex is code, and its blast radius is bounded.

A regex assertion is the one place in Prope where a prompt owner — a designer, a
marketer, somebody with no code review — supplies an expression that the
``worker`` container then executes against attacker-influenceable input. A
catastrophically backtracking pattern against a long model output is not a
hypothetical: ``(a+)+b`` against a few thousand ``a``s is minutes of CPU in a
single expression nobody would look at twice.

Three assertions, and the third is the one the library choice exists for:

* the match **aborts inside its own budget**, rather than running to completion;
* the case records ``outcome=error`` and never ``fail`` (A-057) — a timeout is
  the absence of an answer, and calling it a failure would tell the reviewer the
  prompt is worse when nothing was measured;
* **other work in the same process completes during the same window.** That is
  the blast radius. A pure-Python bound around ``re`` would hold the GIL for the
  whole match and every other coroutine in the container — call-ledger's drain,
  provider-access's dispatch — would stop with it.

The companion assertion is structural: **stdlib ``re`` is not imported on the
assertion path**. ``re.search`` has no timeout at any version, so an import of it
in ``assertions.py`` would mean the budget above is unenforceable no matter what
the tests say.
"""

import ast
import asyncio
import sys
import time
from pathlib import Path

import pytest

from prope.evaluation import assertions
from prope.evaluation.assertions import (
    AssertionTimeout,
    CaseObservation,
    evaluate,
)
from prope.evaluation.domain import (
    MAX_ASSERTION_INPUT_CHARACTERS,
    REGEX_TIMEOUT_SECONDS,
    AssertionSpec,
    AssertionType,
    CaseErrorCode,
    OutputModality,
)

ASSERTIONS_SOURCE = Path(assertions.__file__)

#: The classic. Nested quantifiers over an alternation the engine must try every
#: way of splitting, with a trailing literal that never matches — so the engine
#: explores the whole exponential space before answering "no".
CATASTROPHIC = r"(a+)+$"

#: Long enough that an unbounded match would not finish inside this test run, and
#: short enough that building it costs nothing.
LONG_OUTPUT = "a" * 5_000 + "!"


def _regex_spec() -> AssertionSpec:
    return AssertionSpec(type=AssertionType.REGEX, value=CATASTROPHIC)


def test_a_catastrophic_pattern_aborts_inside_its_budget() -> None:
    """AC-11's first claim, timed. The budget is the constant, not a guess."""
    observation = CaseObservation(content=LONG_OUTPUT, latency_ms=10)

    started = time.perf_counter()
    with pytest.raises(AssertionTimeout) as raised:
        evaluate(_regex_spec(), observation, OutputModality.TEXT)
    elapsed = time.perf_counter() - started

    assert raised.value.assertion_type is AssertionType.REGEX
    assert elapsed < REGEX_TIMEOUT_SECONDS * 5


def test_a_timeout_is_an_error_code_and_never_a_failed_assertion() -> None:
    """AC-11's second claim, at the seam the executor reads.

    ``AssertionTimeout`` carries a ``CaseErrorCode`` rather than an
    ``AssertionOutcome(passed=False)``, which is what makes it structurally
    impossible for the executor to write it as a ``fail``: there is no outcome
    object to record.
    """
    with pytest.raises(AssertionTimeout) as raised:
        evaluate(
            _regex_spec(),
            CaseObservation(content=LONG_OUTPUT, latency_ms=10),
            OutputModality.TEXT,
        )

    assert raised.value.error_code is CaseErrorCode.ASSERTION_TIMEOUT
    assert raised.value.error_code.value == "assertion_timeout"


async def test_other_work_in_the_same_process_completes_during_the_same_window() -> None:
    """AC-11's third claim, and the reason the ``regex`` module is a dependency.

    A ticker coroutine runs beside the assertion. ``regex``'s timeout is checked
    inside the C matching loop and it RELEASES THE GIL while it runs, so the
    ticker keeps being scheduled; an equivalent bound built around stdlib ``re``
    would hold the GIL for the whole match and the ticker would record nothing
    until the match finished.

    The assertion is that the ticker made progress, not that it made a specific
    amount of it: the exact count is a property of the machine and the threshold
    would be a flake.
    """
    ticks = 0
    running = True

    async def ticker() -> None:
        nonlocal ticks
        while running:
            ticks += 1
            await asyncio.sleep(0.01)

    beat = asyncio.create_task(ticker())
    await asyncio.sleep(0.05)
    before = ticks

    def _match() -> None:
        with pytest.raises(AssertionTimeout):
            evaluate(
                _regex_spec(),
                CaseObservation(content=LONG_OUTPUT, latency_ms=10),
                OutputModality.TEXT,
            )

    await asyncio.to_thread(_match)

    running = False
    await beat

    assert ticks > before


def test_the_input_is_length_bounded_before_the_match_runs() -> None:
    """The other half of T-009. A budget alone is not a bound.

    The timeout limits how long ONE match may run; the length cap limits how bad
    the input can be in the first place. Both, because a 40 MB output would spend
    the whole budget on every case in the suite and turn a bounded assertion into
    a bounded assertion twenty times over.
    """
    oversized = "x" * (MAX_ASSERTION_INPUT_CHARACTERS + 1_000)
    bounded = assertions._bounded(oversized)

    assert len(bounded) == MAX_ASSERTION_INPUT_CHARACTERS


def test_stdlib_re_is_not_imported_on_the_assertion_path() -> None:
    """The companion assertion T-009 asks for, read from the source tree.

    Asserted against the parsed AST rather than against ``sys.modules``: ``re``
    is imported by half of Python's standard library, so ``"re" in sys.modules``
    is true in every process and would make this test vacuous. What matters is
    that THIS module never binds it, because ``re.search`` takes no timeout at
    any version and one call would put an unbounded match on the path.
    """
    tree = ast.parse(ASSERTIONS_SOURCE.read_text(encoding="utf-8"))

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert "re" not in imported
    assert "regex" in imported


def test_the_module_actually_bound_is_the_third_party_one() -> None:
    """The import name could be right and the object wrong — a shim, a stub, a
    monkeypatch in a conftest. ``regex`` carries a ``__version__`` and stdlib
    ``re`` does not, and only ``regex.compile(...).search`` accepts ``timeout``."""
    assert assertions.regex is not sys.modules.get("re")
    assert hasattr(assertions.regex, "__version__")

    pattern = assertions.regex.compile("a")
    assert pattern.search("a", timeout=REGEX_TIMEOUT_SECONDS) is not None
