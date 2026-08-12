import ast
from pathlib import Path

import prope.app
from prope.app import app
from prope.session_auth import assembled_routes

APP_SOURCE = Path(prope.app.__file__).read_text(encoding="utf-8")

VERSION_PREFIXES = ("", "/api/v1", "/api/v2", "/v1")


def _paths() -> set[str]:
    return {route.path for route in assembled_routes(app) for _ in route.methods}


def test_no_route_path_names_history() -> None:
    for path in _paths():
        assert "history" not in path.lower(), path


def test_no_history_path_exists_at_any_version() -> None:
    served = _paths()
    for prefix in VERSION_PREFIXES:
        assert f"{prefix}/history" not in served


def test_the_openapi_schema_names_no_history_path() -> None:
    for path in app.openapi()["paths"]:
        assert "history" not in path.lower(), path


def test_prope_app_imports_only_the_registry_functions_from_property_history() -> None:
    tree = ast.parse(APP_SOURCE, filename=prope.app.__file__)

    imported: list[tuple[str, list[str]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "prope.property_history.registry":
            imported.append((node.module, [alias.name for alias in node.names]))
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("prope.property_history"):
            assert node.module == "prope.property_history.registry", (
                f"prope.app imports from {node.module!r}, not just the registry module"
            )

    assert imported, "prope.app does not import the action registry at all"
    names = {name for _, module_names in imported for name in module_names}
    assert names == {"install_registry", "load_action_registry"}
