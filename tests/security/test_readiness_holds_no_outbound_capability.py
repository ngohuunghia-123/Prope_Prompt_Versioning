"""AC-10 / SR-5 — the third leg of the lethal trifecta, absent by construction.

**Two of the three legs are irreducible in this module.** It reads every prompt
body in the workspace (private data) and one of those bodies may be an attacker's
(untrusted content) — that is not a risk profile it might acquire, it is what the
module is *for*. Deck 5 slide 41 says the three together are what turn an
injected instruction into an incident, so the only leg left to remove is the
third, and removing it has to be structural rather than a rule somebody follows.

**`chat_orchestrator` asserts the same property over a tool catalogue.** This
module has no tools, so the equivalent surface is its IMPORTS: an HTTP client, a
mail library or a raw socket in this package would be an outbound channel
whatever the code around it did. Walked with ``ast`` rather than grepped, so a
name in a docstring or a comment cannot fail the build and an import hidden
inside a function cannot pass it.

**There are exactly two sanctioned outbound paths and both go through another
module.** ``provider_access.dispatch`` sends probe cases on the workspace's
credential; ``app_agent`` reaches Prope's own model for Lane B. Neither is
reachable except through a seam that already has its own guards, its own metering
and its own base-URL SSRF check — and neither can be pointed at an address a
prompt body chose.
"""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "prope" / "prompt_readiness"

#: Top-level module names that ARE an outbound channel, whatever they are used
#: for. `urllib` is here even though the standard library uses it for parsing:
#: `urllib.request` and `urllib.parse` are one import statement apart, and a
#: module that may not fetch has no business being one keystroke from doing so.
FORBIDDEN_MODULES = frozenset(
    {
        "httpx",
        "requests",
        "aiohttp",
        "urllib",
        "urllib3",
        "http",
        "socket",
        "smtplib",
        "email",
        "ftplib",
        "telnetlib",
        "webbrowser",
        "subprocess",
        "openai",
    }
)


def _modules() -> list[Path]:
    return sorted(path for path in PACKAGE.glob("*.py") if path.name != "__init__.py")


def _imported_roots(module: Path) -> set[tuple[str, int]]:
    """Every top-level package this module imports, with the line it is on."""
    tree = ast.parse(module.read_text(encoding="utf-8"))
    roots: set[tuple[str, int]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add((alias.name.split(".")[0], node.lineno))
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add((node.module.split(".")[0], node.lineno))
    return roots


@pytest.mark.parametrize("module", _modules(), ids=lambda path: path.name)
def test_no_module_imports_an_outbound_capability(module: Path) -> None:
    found = sorted(
        (name, line) for name, line in _imported_roots(module) if name in FORBIDDEN_MODULES
    )
    assert not found, (
        f"{module.name}: {found} — prompt-readiness holds private data (every prompt in the "
        "workspace) and untrusted content (those same bodies), so the third leg of the lethal "
        "trifecta must be structurally absent. The two sanctioned outbound paths are "
        "provider_access.dispatch and app_agent, and both are somebody else's module."
    )


def test_the_only_prope_outbound_edges_are_the_two_sanctioned_seams() -> None:
    """A dispatch that did not go through provider-access would skip its SSRF guard.

    ``validate_base_url`` lives in provider-access and is what stops a
    configuration pointing at an internal address. A probe that built its own
    request would be a probe outside that check, on a code path whose input is a
    prompt body somebody else wrote.
    """
    outbound: dict[str, set[str]] = {}
    for module in _modules():
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            target = None
            if isinstance(node, ast.ImportFrom) and node.module:
                target = node.module
            elif isinstance(node, ast.Import):
                target = node.names[0].name
            if target and target.startswith("prope.provider_access"):
                outbound.setdefault(module.name, set()).add(target)
            if target and target.startswith("prope.app_agent"):
                outbound.setdefault(module.name, set()).add(target)

    assert outbound == {
        # Lane C. The probe, at priority=batch, on the revision's own binding.
        "probe.py": {"prope.provider_access.seams"},
        # Lane B. Prope's own model, through the shared runtime and its breaker.
        "dspy_program.py": {"prope.app_agent.dspy_runtime"},
        "generation.py": {"prope.app_agent.circuit", "prope.app_agent.client"},
    }, (
        "the set of files that can reach outside this process changed. Every entry here is a "
        "deliberate seam with its own metering and its own guards; a new one is a new way for a "
        "prompt body to influence where bytes go."
    )


def test_no_module_writes_a_file() -> None:
    """A readiness finding is a row and a card, never a file on the host.

    ``open()`` in this package would be a body-derived string reaching a path, and
    the shipped red-team catalogue is deliberately read by ``evaluation`` rather
    than here — this module names set ids and never touches the disk they live on.
    """
    offenders: list[str] = []
    for module in _modules():
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in {"open", "eval", "exec", "compile"}:
                    offenders.append(f"{module.name}:{node.lineno} {node.func.id}()")
    assert offenders == [], offenders
