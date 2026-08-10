"""The source gate ``src/prope/db/session.py``'s docstring claims exists (WR-06).

That module says, of the tenant identifier: *"There is no interpolation of any
kind in this module, and a source gate asserts it."* Phase 1's review logged
WR-06 against that sentence, because no such gate existed. **This is the phase
where the claim has to become true**: from Phase 2 onward ``workspace_id``
arrives inside a broker payload, which makes it the first value in Prope that
reaches SQL from outside the process.

**The gate is a walk over the source, not a claim in a docstring.** Every module
under ``src/prope/`` is parsed with the standard library ``ast`` module and every
argument to a ``text(...)`` call is required to be a plain string constant — no
f-string, no ``%`` formatting, no ``.format()``, no concatenation. It is
deliberately a property of the SOURCE rather than of a test's call sites: a
runtime test can only prove that the inputs it happened to try were safe, while
this proves that no interpolated statement exists to try.

**The file list is discovered, never written down.** ``rglob`` over
``src/prope/``, so a module added in Phase 7 is covered by this test on the day
it is written and nobody has to remember to add it.

**A legitimate exception is an entry in ``ALLOWED``, never a weakening of the
rule.** The list is empty today. If a future phase genuinely needs a composed
statement — a dynamic identifier list in a migration helper, say — it goes in
there with its reason, so the exception is a thing a reviewer reads rather than
a rule that quietly stopped applying.
"""

import ast
from pathlib import Path

import pytest

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "prope"

#: Explicit, reasoned exceptions. Empty, and meant to stay that way. An entry is
#: ``(module path relative to src/prope, line number, why)``.
ALLOWED: frozenset[tuple[str, int]] = frozenset()

#: What a ``text(...)`` argument may be. Nothing else — and specifically not
#: ``ast.JoinedStr`` (an f-string), ``ast.BinOp`` (``+`` or ``%``), or an
#: ``ast.Call`` (``.format()``, ``.join()``).
def _is_plain_string_constant(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _source_modules() -> list[Path]:
    modules = sorted(SOURCE_ROOT.rglob("*.py"))
    assert modules, f"no modules found under {SOURCE_ROOT}; the walk is looking in the wrong place"
    return modules


def _text_calls(tree: ast.AST) -> list[ast.Call]:
    """Every ``text(...)`` call, however it was imported.

    Matches both the bare name (``text(...)``, which is how every module in this
    project writes it) and an attribute access (``sa.text(...)``), so importing
    it differently does not walk around the gate.
    """
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        name = (
            function.id
            if isinstance(function, ast.Name)
            else function.attr
            if isinstance(function, ast.Attribute)
            else None
        )
        if name == "text":
            calls.append(node)
    return calls


@pytest.mark.parametrize("module", _source_modules(), ids=lambda p: p.name)
def test_every_text_call_takes_a_plain_string_constant(module: Path) -> None:
    """No f-string, no %, no .format(), no concatenation reaches ``text()``."""
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    relative = module.relative_to(SOURCE_ROOT).as_posix()

    for call in _text_calls(tree):
        if (relative, call.lineno) in ALLOWED:
            continue

        assert call.args, f"{relative}:{call.lineno}: text() called with no statement"

        for argument in call.args:
            assert _is_plain_string_constant(argument), (
                f"{relative}:{call.lineno}: text() is given a "
                f"{type(argument).__name__} rather than a plain string constant. "
                "Every value reaching SQL is a bound parameter — from phase 2 onward "
                "workspace_id arrives inside a broker payload, and interpolating it "
                "would be an injection site on the value that decides which tenant's "
                "rows a transaction may touch. If this is a genuine exception, add it "
                "to ALLOWED with its reason rather than relaxing this assertion."
            )


def test_the_walk_actually_found_statements_to_check() -> None:
    """Guards the gate against passing because it inspected nothing.

    A walk that matched zero ``text()`` calls would be green for the same reason
    a walk over an empty directory would be, and the two are indistinguishable
    from the outside. This is what tells them apart.
    """
    found = sum(
        len(_text_calls(ast.parse(module.read_text(encoding="utf-8"))))
        for module in _source_modules()
    )
    assert found >= 5, f"only {found} text() calls found under {SOURCE_ROOT}"


def test_the_tenant_seam_is_covered_by_this_walk() -> None:
    """The module whose docstring makes the claim is one of the modules walked."""
    assert (SOURCE_ROOT / "db" / "session.py") in _source_modules()
