import ast
from pathlib import Path

import pytest

from prope.observability import LOGGABLE_FIELDS

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "prope"

LOG_METHODS = frozenset({"info", "warning", "error", "debug", "critical"})

ALLOWED_STAR_KWARGS: frozenset[tuple[str, int]] = frozenset({("property_history/domain.py", 86)})


def _source_modules() -> list[Path]:
    modules = sorted(SOURCE_ROOT.rglob("*.py"))
    assert modules, f"no modules found under {SOURCE_ROOT}"
    return modules


def _log_calls(tree: ast.AST) -> list[ast.Call]:
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if (
            isinstance(function, ast.Attribute)
            and function.attr in LOG_METHODS
            and isinstance(function.value, ast.Name)
            and function.value.id == "log"
        ):
            calls.append(node)
    return calls


@pytest.mark.parametrize("module", _source_modules(), ids=lambda p: p.name)
def test_every_log_call_keyword_is_in_the_allow_list(module: Path) -> None:
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    relative = module.relative_to(SOURCE_ROOT).as_posix()

    for call in _log_calls(tree):
        for keyword in call.keywords:
            if keyword.arg is None:
                assert (relative, call.lineno) in ALLOWED_STAR_KWARGS, (
                    f"{relative}:{call.lineno}: a starred kwargs payload is not a "
                    "statically checkable allow-list member; add it to "
                    "ALLOWED_STAR_KWARGS with a reason, or spell out its keys"
                )
                continue
            assert keyword.arg in LOGGABLE_FIELDS, (
                f"{relative}:{call.lineno}: log field {keyword.arg!r} is not in prope.observability.LOGGABLE_FIELDS"
            )


def test_the_walk_actually_found_log_calls() -> None:
    found = sum(len(_log_calls(ast.parse(m.read_text(encoding="utf-8")))) for m in _source_modules())
    assert found >= 10, f"only {found} log calls found under {SOURCE_ROOT}"


def test_every_property_history_module_is_covered_by_this_walk() -> None:
    modules = _source_modules()
    assert (SOURCE_ROOT / "property_history" / "append.py") in modules
    assert (SOURCE_ROOT / "call_ledger" / "schemas.py") in modules
