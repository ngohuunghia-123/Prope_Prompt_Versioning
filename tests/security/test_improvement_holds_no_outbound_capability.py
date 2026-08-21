"""AC-8 / SR-8 — the third leg of the lethal trifecta, absent by construction.

**Two of the three legs are irreducible here, exactly as they are in
prompt-readiness.** The module reads every released prompt in the workspace
(private data) and one of those bodies may be an attacker's (untrusted content).
That is not a risk it might acquire; it is what the module is *for*. Deck 5 slide
41 says the three together are what turn an injected instruction into an
incident, so the only leg left to remove is the third — and removing it has to be
structural, not a rule somebody follows.

**This module is stricter than prompt-readiness and the difference is the point.**
Readiness dispatches probe cases itself, so its sanctioned set contains
``provider_access``. prompt-improvement contains **no** ``provider_access`` import
at all: everything that spends money goes through somebody else's seam —
``evaluation.seams.score_body_against_suite`` for the gate,
``prompt_readiness.seams.run_probe`` for the scheduled re-probe. A background job
that runs unattended, every day, across every workspace should not also be the
thing that decides where bytes go, and the import graph is where that sentence is
enforced rather than asserted.

**Deck 6's Slack alerting is declined by name** (ADR-0068 §5). Delivery is
pull-only: a person opens the inbox. An outbound notifier here would be a channel
whose content is derived from prompt bodies and whose destination is a
configuration — which is the trifecta completed by a feature request.
"""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "prope" / "prompt_improvement"

#: Top-level module names that ARE an outbound channel, whatever they are used
#: for. Copied from ``test_readiness_holds_no_outbound_capability`` rather than
#: imported: two modules asserting the same property from two files is the shape
#: that survives one of them being relaxed for a reason that does not apply to
#: the other.
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
    """Every top-level package this module imports, with the line it is on.

    Walked with ``ast`` rather than grepped, so a name in a docstring cannot fail
    the build and an import hidden inside a function cannot pass it.
    """
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
        f"{module.name}: {found} — prompt-improvement holds private data (every released prompt "
        "in every workspace) and untrusted content (those same bodies), so the third leg of the "
        "lethal trifecta must be structurally absent. Delivery is pull-only by decision "
        "(ADR-0068 §5); an outbound channel here is the trifecta completed by a feature request."
    )


def test_the_module_cannot_dispatch_to_a_provider_at_all() -> None:
    """**No ``provider_access`` import anywhere in this package.** The stronger claim.

    Everything that spends the workspace's money is somebody else's seam:
    ``evaluation.seams.score_body_against_suite`` runs the gate,
    ``prompt_readiness.seams.run_probe`` runs the scheduled re-probe. Both already
    carry the spend-ceiling check, the metering and provider-access's base-URL
    SSRF guard, and neither can be pointed at an address a prompt body chose.

    This is asserted as an absence rather than as an allow-list because the
    absence is the property. A sweep runs unattended, daily, across every
    workspace; the day it can build its own request is the day an injected
    instruction has somewhere to go.
    """
    offenders: dict[str, int] = {}
    for module in _modules():
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            target = None
            if isinstance(node, ast.ImportFrom) and node.module:
                target = node.module
            elif isinstance(node, ast.Import):
                target = node.names[0].name
            if target and target.startswith("prope.provider_access"):
                offenders[f"{module.name}:{node.lineno}"] = 1

    assert offenders == {}, (
        f"{sorted(offenders)} — this module dispatches through evaluation and prompt-readiness, "
        "never directly. A dispatch built here would be one outside the seams that meter it."
    )


def test_the_only_edges_to_prope_s_own_model_are_the_triage_program_and_its_breaker() -> None:
    """One model call, in one place, behind a circuit breaker.

    ``dspy_program`` declares the signature; ``triage`` owns the breaker and the
    degradation. Nothing else in the package may reach ``app_agent``, because a
    second call site would be a second place where a prompt-derived string is
    handed to a model — and only one of the two would have the coercion that
    drops an unreachable remedy family.
    """
    edges: dict[str, set[str]] = {}
    for module in _modules():
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            target = None
            if isinstance(node, ast.ImportFrom) and node.module:
                target = node.module
            elif isinstance(node, ast.Import):
                target = node.names[0].name
            if target and target.startswith("prope.app_agent"):
                edges.setdefault(module.name, set()).add(target)

    assert edges == {
        # The signature and the bounded output type. No field for a body.
        "dspy_program.py": {"prope.app_agent.dspy_runtime"},
        # The breaker, and the never-raises degradation around it.
        "triage.py": {"prope.app_agent.circuit"},
    }, (
        f"{edges} — the set of files that can reach Prope's own model changed. A second call "
        "site is a second place a model's answer becomes data, and only one of them has "
        "`_coerce`."
    )


def test_no_module_writes_a_file_or_evaluates_a_string() -> None:
    """A finding is a row. It is never a file on the host and never code.

    ``open()`` in this package would be a body-derived string reaching a path.
    ``eval``/``exec``/``compile`` would be a model's answer reaching the
    interpreter — and the model's answer here is a ``detector_id``, a rank and one
    sentence, all of which are strings it chose.
    """
    offenders: list[str] = []
    for module in _modules():
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in {"open", "eval", "exec", "compile"}:
                    offenders.append(f"{module.name}:{node.lineno} {node.func.id}()")
    assert offenders == [], offenders


def test_the_triage_signature_has_no_field_that_can_carry_a_body() -> None:
    """ADR-0068 §3, read off the output type rather than off the prompt text.

    The model ranks anomalies and picks a remedy family. It does not write
    prompts, and the reason that is safe is not that the instruction says so —
    instructions are the thing an injected body argues with. It is that
    ``TriagedAnomaly`` has nowhere to put one: four fields, none of them a body,
    and a model that returned one would have it dropped at validation.
    """
    source = (PACKAGE / "dspy_program.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    fields: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "TriagedAnomaly":
            for statement in node.body:
                if isinstance(statement, ast.AnnAssign) and isinstance(
                    statement.target, ast.Name
                ):
                    fields.append(statement.target.id)

    assert fields, "TriagedAnomaly not found — the assertion below would pass vacuously"
    assert not [name for name in fields if "body" in name or "prompt" in name], fields
    assert set(fields) == {"detector_id", "rank", "remedy_family", "evidence"}, fields
