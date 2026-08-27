"""The catalogues are TOTAL over the router combo's refusal codes. ADR-0069.

Same contract as ``test_readiness_rules_have_a_vi_key``,
``test_improvement_codes_have_a_vi_key`` and ``test_similarity_codes_have_a_vi_key``,
for the same reason: the API sends a machine ``code`` and nothing else
(ADR-0053), the client owns every sentence, and the failure mode of that design
is silent.

**The router dialog degrades rather than renders the code** — its ``errorKey``
falls through to ``lifecycle.router.error.unknown`` for anything it does not
recognise. That is a softer failure than the funnel's (which shows the raw
identifier) and a worse one to leave untested: *"That could not be completed"*
is a sentence somebody will read as a network blip while the server is actually
telling them the combo was deleted under them, or that the name is taken. The
specific answer is the one that says which control to touch.

**Three codes and a deliberate extension of `lifecycle`.** The plan's tiebreak
was that a refusal enum of three or four fixed codes extends the existing
catalogue and only a growing one of five or more earns its own namespace; the
cost paid here is walking two nesting levels instead of one, which is the whole
of the difference. If a fifth code arrives, the split is what to reach for.

The parse is the same deliberately dumb brace-count over string-blanked source
as its three siblings, duplicated rather than shared for the reason stated
there: independent readers of independent catalogues is the point, and a shared
helper would mean one bug hides all four.
"""

import re
from pathlib import Path

import pytest

from prope.errors import ErrorCode

LOCALES = Path(__file__).resolve().parents[2] / "src" / "prope-fe" / "locales"
CATALOGUES = {"vi": LOCALES / "lifecycle.vi.ts", "en": LOCALES / "lifecycle.en.ts"}

#: Every registry code whose only reader is the router surface. Derived from the
#: enum rather than typed out, so a new `REGISTRY_ROUTER_*` member fails this
#: test until somebody writes both sentences.
ROUTER_CODES = frozenset(
    code.value
    for code in ErrorCode
    if code.value.startswith("registry_router_") or code.value == "registry_unknown_router_combo"
)

#: Not a router code, but the dialog renders it from the same block: a person
#: without `provider.configure` gets a 403 here, and "you do not have
#: permission" is the one refusal on this screen that is not about the combo.
SHARED_CODES = frozenset({"permission_denied", "mockMode", "unknown"})


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


def test_the_enum_still_holds_the_three_codes_this_test_is_about() -> None:
    """A guard on the derivation above, not on the catalogue.

    If a rename made ``ROUTER_CODES`` empty, every assertion below would pass
    vacuously and the screen would be untested while the suite stayed green.
    """
    assert ROUTER_CODES == {
        "registry_unknown_router_combo",
        "registry_router_combo_empty",
        "registry_router_combo_name_taken",
    }


@pytest.mark.parametrize("language", sorted(CATALOGUES))
def test_every_router_refusal_has_a_sentence(language: str) -> None:
    present = _keys(_block(_stripped(CATALOGUES[language]), ("router", "error")))
    missing = sorted(code for code in ROUTER_CODES if code not in present)
    assert missing == [], (
        f"{CATALOGUES[language].name} has no sentence for {missing}. The API sends a `code` and "
        "nothing else (ADR-0053), and the dialog degrades an unknown one to a generic message — "
        "so the reader is told the save failed and never told the combo was deleted under them."
    )


@pytest.mark.parametrize("language", sorted(CATALOGUES))
def test_no_router_sentence_names_a_code_the_server_cannot_return(language: str) -> None:
    """The other direction: a stale key is a sentence nobody will ever see."""
    present = _keys(_block(_stripped(CATALOGUES[language]), ("router", "error")))
    unexpected = sorted(present - ROUTER_CODES - SHARED_CODES)
    assert unexpected == [], (
        f"{CATALOGUES[language].name} translates {unexpected}, which no refusal on this screen emits"
    )


def test_the_two_catalogues_hold_the_same_router_keys() -> None:
    """Structural parity, one level at a time.

    ADR-0053 ships Vietnamese and mirrors English, so a key present in one and
    absent in the other is a screen that reads correctly in exactly one locale —
    and the one it reads correctly in is usually the one the author was looking
    at.
    """
    stripped = {language: _stripped(path) for language, path in CATALOGUES.items()}

    for path in [
        ("router",),
        ("router", "empty"),
        ("router", "card"),
        ("router", "snapshot"),
        ("router", "dialog"),
        ("router", "error"),
    ]:
        vi = _keys(_block(stripped["vi"], path))
        en = _keys(_block(stripped["en"], path))
        assert vi == en, f"lifecycle.{'.'.join(path)} differs: vi-only {sorted(vi - en)}, en-only {sorted(en - vi)}"


def test_the_composer_strings_exist_in_both_catalogues() -> None:
    """The editor half, which lives under `editor` beside the provider strings.

    Deliberately not a namespace of its own: the combo select renders two lines
    under the provider select, and splitting would put the two labels in
    different catalogues.
    """
    expected = {
        "bindingMode",
        "bindingModeSingle",
        "bindingModeCombo",
        "combo",
        "comboUnset",
        "comboRequired",
        "comboSnapshotHint",
        "combosLoading",
        "combosLoadError",
        "noCombos",
        "createCombo",
        "manageCombos",
        "routeDriftTitle",
        "routeDriftBody",
    }
    for language, path in CATALOGUES.items():
        present = _keys(_block(_stripped(path), ("editor",)))
        missing = sorted(expected - present)
        assert missing == [], f"{path.name} `editor` is missing {missing}"


def test_the_settings_destination_has_a_navigation_label() -> None:
    """Without it the fifth settings entry renders as `lifecycle.navigation.router`.

    Read by anchoring on the TOP-LEVEL `navigation:` — two spaces of indent, at
    the start of a line — rather than through `_block`, which finds the first
    `navigation: {` in the file and that one belongs to the product tour. The
    sibling tests never hit this because none of their namespaces share a name
    with a nested block.
    """
    for language, path in CATALOGUES.items():
        match = re.search(r"^  navigation: \{(.*?)\}", _stripped(path), flags=re.MULTILINE | re.DOTALL)
        assert match, f"{path.name} has no top-level `navigation` block"
        assert "router" in _keys(match.group(1).replace(",", "\n")), (
            f"{path.name} has no `navigation.router` label"
        )
