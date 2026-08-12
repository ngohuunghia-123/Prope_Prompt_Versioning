"""AC-1 / T-028 — a corpus scan, not a per-endpoint check.

"Never returned by a read API" is a non-negotiable constraint, and a constraint
enforced by remembering to exclude a column is one that fails the first time
somebody writes SELECT *. The separation of `provider.credential` from
`provider.provider_config` is what makes it structural; these assertions are
what notice if the separation is ever undone.
"""

import ast
from pathlib import Path

from prope.app import app
from prope.observability import LOGGABLE_FIELDS
from prope.provider_access import commands
from prope.provider_access.schemas import ProviderRead

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "prope" / "provider_access"

#: The stored envelope's columns, plus the words somebody would reach for while
#: adding a read path for one of them.
FORBIDDEN_FIELD_NAMES = frozenset(
    {
        "ciphertext",
        "nonce",
        "wrapped_dek",
        "dek",
        "kek",
        "secret",
        "api_key",
        "credential",
        "plaintext",
        "authorization",
        "bearer",
    }
)

#: The one credential-derived value that may cross, and the only one.
PERMITTED = frozenset({"credential_last_four"})


def _response_schema_names() -> set[str]:
    schema = app.openapi()
    named: set[str] = set()
    for path, operations in schema["paths"].items():
        if "/providers" not in path:
            continue
        for operation in operations.values():
            for response in operation.get("responses", {}).values():
                for media in response.get("content", {}).values():
                    reference = media.get("schema", {}).get("$ref", "")
                    if reference:
                        named.add(reference.rsplit("/", 1)[-1])
                    items = media.get("schema", {}).get("items", {}).get("$ref", "")
                    if items:
                        named.add(items.rsplit("/", 1)[-1])
    return named


def test_no_response_model_on_any_provider_route_carries_a_credential_field() -> None:
    schema = app.openapi()
    models = schema["components"]["schemas"]

    offenders = []
    for name in _response_schema_names():
        for field in models.get(name, {}).get("properties", {}):
            if field in PERMITTED:
                continue
            if field.lower() in FORBIDDEN_FIELD_NAMES:
                offenders.append(f"{name}.{field}")

    assert offenders == [], offenders


def test_the_read_model_carries_the_last_four_characters_and_nothing_else() -> None:
    """A-025 as amended: the dashboard shows the last four and nothing else."""
    fields = set(ProviderRead.model_fields)

    assert "credential_last_four" in fields
    assert not {field for field in fields if field.lower() in FORBIDDEN_FIELD_NAMES}


def test_the_credential_is_a_request_field_and_never_a_response_field() -> None:
    """It is write-only across the whole seam (INT-027)."""
    models = app.openapi()["components"]["schemas"]

    assert "credential" in models["ProviderCreate"]["properties"]
    assert "credential" in models["CredentialRotate"]["properties"]
    assert "credential" not in models["ProviderRead"]["properties"]


def test_no_configuration_read_statement_names_a_ciphertext_column() -> None:
    """The two statements every configuration read goes through. If either ever
    joins the envelope columns, the separation has been undone in one line."""
    for statement in (commands.LOAD_ROW, commands.LIST_ROWS):
        rendered = str(statement).lower()

        assert "ciphertext" not in rendered
        assert "wrapped_dek" not in rendered
        assert "nonce" not in rendered
        assert "last_four" in rendered


def test_no_history_event_this_module_writes_carries_any_detail_key() -> None:
    """The registry allows none for all four actions (revision 0005), so there
    is no registered slot a later contributor could put a credential into — and
    this asserts the writing side never tries."""
    source = (PACKAGE / "events.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    passed = [
        keyword.arg
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg in {"details", "reason"}
    ]

    assert passed == []


def test_the_log_allow_list_admits_no_credential_bearing_field() -> None:
    """A-046 is an allow-list, so this is a check that nothing was added to it
    rather than a check that nothing was logged."""
    admitted = {field for field in LOGGABLE_FIELDS if field.lower() in FORBIDDEN_FIELD_NAMES}

    assert admitted == set()


def test_no_module_in_the_package_logs_a_field_outside_the_allow_list() -> None:
    """Every keyword argument to a `log.*` call, checked against A-046's list."""
    offenders: list[str] = []
    for module in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if not isinstance(node.func.value, ast.Name) or node.func.value.id != "log":
                continue
            for keyword in node.keywords:
                if keyword.arg is not None and keyword.arg not in LOGGABLE_FIELDS:
                    offenders.append(f"{module.name}: {keyword.arg}")

    assert offenders == [], offenders
