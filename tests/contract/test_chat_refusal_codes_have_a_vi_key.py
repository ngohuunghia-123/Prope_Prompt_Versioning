"""Every refusal the confirmation route can send has a sentence in both catalogues.

Same contract as its three siblings, and the same reason: the API sends a machine
``code`` and the client owns every sentence (ADR-0053). i18next falls back to the
key, so a code with no entry renders as ``registry_folder_not_empty`` on a
confirmation card — an identifier, in a language nobody speaks, at the moment
somebody is being told their approval did not go through.

**This file exists because the failure was worse than an untranslated key.** The
route shaped every refusal as ``403 if permission_denied else 404``, so
``chat_tool_folder_not_empty`` — raised on purpose by ``commands.delete_folder``
while a folder still holds prompts — arrived as ``not_found``. It had a sentence,
and the sentence was false: the person was told the folder they were holding an
open card for could not be found. A code with no key is visibly broken; a code
mapped onto the wrong sentence is invisibly wrong, which is why the mapping is
now a table this test reads rather than a conditional expression.

The parse is the same deliberately dumb brace-count over string-blanked source as
its siblings, duplicated rather than shared for the reason stated there.
"""

import re
from pathlib import Path

import pytest

from prope.chat_orchestrator.api import _REFUSAL_SHAPES

LOCALES = Path(__file__).resolve().parents[2] / "src" / "prope-fe" / "locales"
CATALOGUES = {"vi": LOCALES / "vi.ts", "en": LOCALES / "en.ts"}


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


#: Anchored on `refusal:`, which occurs exactly once in each catalogue, rather
#: than walking `chat` -> `refusal`: `chat:` appears twice — the navigation label
#: comes first — and the walk would read the nav entry and report every code as
#: missing. A test that fails for the wrong reason teaches people to edit the
#: test. This assertion keeps the anchor honest.
def _sole_refusal_block(path: Path) -> str:
    source = _stripped(path)
    assert source.count("refusal:") == 1, f"{path.name} no longer has exactly one `refusal:` block"
    return _block(source, ("refusal",))


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


@pytest.mark.parametrize("language", sorted(CATALOGUES))
def test_every_confirmation_refusal_has_a_sentence(language: str) -> None:
    present = _keys(_sole_refusal_block(CATALOGUES[language]))
    # The wire carries the ErrorCode's value, which is what the client looks up.
    missing = sorted({code.value for _status, code in _REFUSAL_SHAPES.values()} - present)
    assert missing == [], (
        f"{CATALOGUES[language].name} has no sentence under chat.refusal for {missing}. "
        "The API sends a `code` and nothing else (ADR-0053), so it renders as itself."
    )


def test_the_fallback_shape_is_the_one_the_catalogue_can_render() -> None:
    """Anything unmapped falls back to `not_found`, so that key must exist.

    The fallback is the only refusal shape no table entry guarantees, and it is
    the one every future `WriteRefused` code lands on until somebody writes a
    sentence for it.
    """
    for path in CATALOGUES.values():
        assert "not_found" in _keys(_sole_refusal_block(path))


def test_permission_denied_is_the_only_refusal_that_is_not_a_conflict_or_a_miss() -> None:
    """The status codes are part of the contract, not decoration.

    403 says *you may not*, 404 says *there is no such thing*, 409 says *it exists
    and is in the wrong state*. Collapsing the third into the second is the bug
    this module was written for, so the shape is asserted rather than assumed.
    """
    assert _REFUSAL_SHAPES["permission_denied"][0] == 403
    assert _REFUSAL_SHAPES["not_found"][0] == 404
    conflicts = {
        code for code, (status, _errorcode) in _REFUSAL_SHAPES.items() if status == 409
    }
    assert "chat_tool_folder_not_empty" in conflicts
    assert all(status in {403, 404, 409} for status, _ in _REFUSAL_SHAPES.values())
