"""Schema per module (ADR-0027), asserted against the SQL rather than the imports.

Every other edge this system has is policed by an import graph:
``test_prompt_registry_depends_on_three_modules`` and its eleven siblings parse
each module's source and refuse a ``from prope.<other_module> import ...`` that
is not on the allow-list. **A SQL statement is invisible to all of them.** A
``SELECT email FROM access."user"`` inside ``registry``'s repository imports
nothing, passes every dependency test, and still reads another module's table —
which is the one way to add an undeclared edge and have the whole architecture
suite stay green.

That is not hypothetical: it is what this test was written after. The revision
byline was first built as a correlated subquery from ``registry.revision`` into
``access."user"``, and nothing in the suite objected. The fix was
``access_control.seams.user_emails`` — the same shape as ``key_labels``, which
already existed for exactly this reason — and this gate is what stops the
subquery coming back.

**A property of the source, not of a call site.** Like
``test_no_sql_interpolation``, every module under ``src/prope/`` is parsed with
``ast`` and every plain-string argument to a ``text(...)`` call is searched for a
schema-qualified name. A runtime test could only prove that the queries it
happened to run stayed inside their schema; this proves that no statement
crossing one exists to run.

**The file list is discovered, never written down.** ``rglob`` over
``src/prope/``, so a module added later is covered on the day it is written.

**An exception is an entry in ``ALLOWED`` with its reason, never a weakening of
the rule.** There are two today, and both are edges that were argued somewhere
else before they were written here.
"""

import ast
import re
from pathlib import Path

import pytest

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "prope"

#: The schemas ``alembic/`` creates. Checked against the module map below, so a
#: schema added by a migration with no owner named here fails this test rather
#: than being silently unowned.
SCHEMAS = frozenset(
    {
        "access",
        "chat",
        "evaluation",
        "history",
        "improvement",
        "ledger",
        "observation",
        "provider",
        "readiness",
        "registry",
        "release",
        "search",
    }
)

#: ``package under src/prope`` -> ``the one schema it owns``. ADR-0027's
#: schema-per-module, written down where a test can read it.
OWNED: dict[str, str] = {
    "access_control": "access",
    "call_ledger": "ledger",
    "chat_orchestrator": "chat",
    "evaluation": "evaluation",
    "prompt_improvement": "improvement",
    "prompt_observation": "observation",
    "prompt_readiness": "readiness",
    "prompt_registry": "registry",
    "prompt_search": "search",
    "property_history": "history",
    "provider_access": "provider",
    "release_control": "release",
}

#: Reasoned exceptions, as ``(module, schema): why``. Both entries are edges the
#: dependency tests already permit at the import level; they are listed here
#: because reading another module's table directly is a second, wider promise
#: than importing its seam, and the difference should be a thing a reviewer reads.
ALLOWED: dict[tuple[str, str], str] = {
    ("prompt_readiness", "evaluation"): (
        "prompt-readiness declares evaluation as a dependency and lists "
        "`prope.evaluation` in its allowed imports. `repository.py` reads "
        "`evaluation.eval_suite` to render the suites a probe may run, and says "
        "in its own comment that it copies `evaluation.repository`'s shape."
    ),
    ("worker", "ledger"): (
        "`worker.py` is the call-record consumer. Writing `ledger.call_record` "
        "IS its job — ADR-0028's one queue lands here — and it is a top-level "
        "module rather than a package, so it owns no schema of its own."
    ),
}

#: ``schema.identifier``, which is the only form that reaches another module's
#: tables. A bare `revision` resolves through `search_path` and is not what this
#: is looking for; every statement in this codebase qualifies its tables.
QUALIFIED = re.compile(r"\b(" + "|".join(sorted(SCHEMAS)) + r')\.("?[A-Za-z_][A-Za-z_0-9]*"?)')


def _module_of(path: Path) -> str:
    """The package under ``src/prope`` a file belongs to, or its own stem."""
    relative = path.relative_to(SOURCE_ROOT)
    return relative.parts[0] if len(relative.parts) > 1 else relative.stem


def _statements(path: Path) -> list[tuple[int, str]]:
    """Every plain-string argument to a ``text(...)`` call, with its line."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:  # pragma: no cover - a syntax error fails the real suite
        return []

    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id != "text":
            continue
        for argument in node.args:
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                found.append((argument.lineno, argument.value))
    return found


def _source_modules() -> list[Path]:
    modules = sorted(SOURCE_ROOT.rglob("*.py"))
    assert modules, f"no modules found under {SOURCE_ROOT}; the walk is looking in the wrong place"
    return modules


def test_every_schema_has_exactly_one_owner() -> None:
    """The map above covers the database, and no schema is owned twice."""
    owners = list(OWNED.values())
    assert sorted(owners) == sorted(set(owners)), "a schema is claimed by two modules"
    assert set(owners) == set(SCHEMAS), (
        "OWNED and SCHEMAS disagree — a migration added a schema with no module "
        "named for it, or a module names one that no longer exists"
    )


@pytest.mark.parametrize("path", _source_modules(), ids=lambda path: path.name)
def test_a_modules_sql_stays_inside_the_schema_it_owns(path: Path) -> None:
    module = _module_of(path)
    owned = OWNED.get(module)

    for line, statement in _statements(path):
        for match in QUALIFIED.finditer(statement):
            schema = match.group(1)
            if schema == owned:
                continue
            if (module, schema) in ALLOWED:
                continue
            location = f"{path.relative_to(SOURCE_ROOT)}:{line}"
            pytest.fail(
                f"{location} reads `{match.group(0)}` — {module} owns "
                f"{owned or 'no schema'}, so this is an undeclared cross-module "
                f"edge that the import-graph tests cannot see. Reach it through "
                f"the owning module's `seams` (see `access_control.labels`), or "
                f"add a reasoned entry to ALLOWED."
            )
