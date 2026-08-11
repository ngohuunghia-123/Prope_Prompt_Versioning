"""No statement under ``src/prope/`` or ``alembic/`` may supply its own ``seq``.

``tests/security/test_history_seq_cannot_be_supplied.py`` proves that
``OVERRIDING SYSTEM VALUE`` bypasses ``GENERATED ALWAYS`` at the engine, with
no privilege requirement attached. PH-04's entire guarantee is that ``seq`` is
assigned by the engine and only by the engine, so a property whose only
defence is "nobody would do that" is a property nobody is defending — the
same argument that built ``test_no_sql_interpolation.py`` for a value nobody
had interpolated. This gate proves that no such statement **exists to be
executed**, where a runtime test can only prove that the statements it
happened to try were safe.

**Deviation one from the analog: the walk covers ``alembic/`` too.**
``test_no_sql_interpolation.py`` walks ``src/prope/`` only, correctly, because
its rule is about runtime values reaching SQL. This rule is about a token
that would break the total order, and a data revision running as
``prope_migrate`` could break it just as thoroughly — more so, because a
migration runs once, with no review of its effect on rows already present.

**Deviation two: the gate reads string constants that are not docstrings, not
raw file text.** A raw ``in`` over the file's text is wrong here specifically
because the revision's own docstring, ``append.py``'s docstring and the
security test above all *explain* why the token is not used — a gate that
reddens on its own explanation is a gate somebody deletes. Comments are not
in the AST at all, so a ``#`` comment may discuss the rule freely.
"""

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "prope"
ALEMBIC_ROOT = REPO_ROOT / "alembic"

#: (root name, path relative to that root, line number, why). A legitimate
#: exception is an entry, never a weakening of the rule. Empty, and it ships
#: empty on purpose: the only legitimate use of the token in this repository
#: is ``tests/security/test_history_seq_cannot_be_supplied.py``'s
#: ``INSERT_WITH_OVERRIDING_SYSTEM_VALUE``, which lives under ``tests/`` —
#: outside both roots this gate walks — by construction.
ALLOWED: frozenset[tuple[str, str, int]] = frozenset()

TOKEN = "overriding system value"


def _modules(root: Path) -> list[Path]:
    modules = sorted(root.rglob("*.py"))
    assert modules, f"no modules found under {root}; the walk is looking in the wrong place"
    return modules


def _docstring_nodes(tree: ast.Module) -> set[ast.Constant]:
    """The module docstring plus every function/class docstring, by identity."""
    nodes: set[ast.Constant] = set()
    candidates: list[ast.AST] = [tree]
    candidates.extend(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    )
    for candidate in candidates:
        body = getattr(candidate, "body", None)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            if isinstance(body[0].value.value, str):
                nodes.add(body[0].value)
    return nodes


def _overriding_hits(tree: ast.Module) -> list[ast.Constant]:
    """Every non-docstring string constant containing the token, case-insensitive."""
    exempt = _docstring_nodes(tree)
    hits: list[ast.Constant] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if node in exempt:
            continue
        if TOKEN in node.value.lower():
            hits.append(node)
    return hits


def _all_modules() -> list[tuple[str, Path]]:
    return [("src/prope", module) for module in _modules(SRC_ROOT)] + [
        ("alembic", module) for module in _modules(ALEMBIC_ROOT)
    ]


@pytest.mark.parametrize("entry", _all_modules(), ids=lambda entry: entry[1].name)
def test_no_module_supplies_its_own_seq(entry: tuple[str, Path]) -> None:
    root_name, module = entry
    root = SRC_ROOT if root_name == "src/prope" else ALEMBIC_ROOT
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    relative = module.relative_to(root).as_posix()

    for hit in _overriding_hits(tree):
        if (root_name, relative, hit.lineno) in ALLOWED:
            continue

        raise AssertionError(
            f"{root_name}/{relative}:{hit.lineno}: contains 'OVERRIDING SYSTEM VALUE' (or "
            "OVERRIDING USER VALUE) outside a docstring. That token lets any role holding "
            "INSERT supply its own history_event.seq — the only sort key this module has "
            "(A-125, ADR-0024) and the only thing giving two events in one transaction a "
            "defined order. A genuine exception is an ALLOWED entry with its reason, never "
            "a relaxed assertion."
        )


def test_the_walk_actually_found_modules_to_check() -> None:
    """A walk over an empty directory is green for the same reason a clean walk
    is, and the two are indistinguishable from outside."""
    assert len(_modules(SRC_ROOT)) >= 5
    assert len(_modules(ALEMBIC_ROOT)) >= 5


def test_the_append_path_is_covered_by_this_walk() -> None:
    assert (SRC_ROOT / "property_history" / "append.py") in _modules(SRC_ROOT)


def test_the_gate_ignores_docstrings_but_catches_a_non_docstring_constant() -> None:
    """A committed, in-suite proof — not a temporary local edit reverted before
    commit, which would leave nothing in CI. Same snippet also proves the
    docstring exemption: the identical lowercase token inside a module
    docstring passes."""
    caught = ast.parse(
        '"""a module docstring"""\n'
        'STATEMENT = "insert into t (a) overriding system value values (1)"\n'
    )
    assert _overriding_hits(caught), "a non-docstring constant carrying the token must be caught"

    clean = ast.parse(
        '"""this docstring explains overriding system value and must not be flagged"""\n'
        "X = 1\n"
    )
    assert not _overriding_hits(clean), "the module docstring must be exempt"
