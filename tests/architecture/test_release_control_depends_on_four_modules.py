"""`dependencies: [prompt-registry, access-control, property-history, evaluation]`
as a checked property.

`docs/modules/release-control.lock.yml` declares four module dependencies —
three hard, one soft — and names four forbidden edges. Three are ordinary and one
is a trap.

*gateway.* Release-control changes what the gateway resolves; it must never call
it. A management surface inside the latency-critical path is the failure ADR-0001
already routed around, and there is nothing to tell the gateway even if this
module were permitted to — its resolution cache EXPIRES within 30 s and nothing
invalidates it (ADR-0012).

*provider-access.* This module never calls a model. A transitive path exists in
the module graph (release-control → prompt-registry → provider-access) and
carries nothing on any call this module makes: `get_revision`, `get_diff` and
`get_released_revision` are reads of registry tables and reach the catalogue on
none of them.

*call-ledger.* The ledger is a sink and its read path is gated by OQ-013. The
transitive path here is live rather than theoretical — this module depends on
evaluation and evaluation depends on call-ledger — so the edge is only as strong
as what `get_review_summary()` does at render time, which is read stored columns.
The consequence is accepted and stated: the withdraw confirmation cannot show how
much live traffic the model name is currently taking.

*property-history — the trap.* That module appears in BOTH `dependencies`
(criticality: hard) and `forbidden_dependencies`, and the two say opposite things
unless the qualifier is read. What is forbidden is a **direct INSERT into
`history.history_event`**, not the edge and not INT-006. This module MUST call
`append()`, for eight events, in the same transaction as the decision — it is the
module whose product claim that call IS. The lock says a literal reading of the
forbidden-dependency entry *"would delete the guarantee rather than protect it"*.

**`aio_pika` is forbidden.** This is the second module in `worker` with no broker
involvement at all (ADR-0051). Fanout invalidation on withdrawal was re-argued on
merit in the step-4 pass, now that A-012's no-broker clause is gone, and rejected:
it would fire only on the rarest action in the product, it would make `app` a
broker consumer for the first time, and it would not close the window under a
restart.

**`httpx` is forbidden.** `external_services` is `[]` and OQ-015 resolved to no
outbound channel at all — the review queue is in-app only (A-071).

**`difflib` is forbidden.** The diff on the review screen is prompt-registry's
`get_diff`, which chose `SequenceMatcher(autojunk=False)` in its own pass. This
module renders it; it does not compute it, and it must not acquire a second
implementation.
"""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "prope" / "release_control"

ALLOWED_PROPE_IMPORTS = frozenset(
    {
        "prope.access_control",
        "prope.db",
        "prope.dependencies",
        "prope.errors",
        "prope.evaluation",
        "prope.prompt_registry",
        "prope.property_history",
        "prope.release_control",
        "prope.session_auth",
    }
)

FORBIDDEN_MODULES = (
    "prope.gateway",
    "prope.provider_access",
    "prope.call_ledger",
)

VIOLATION = (
    "release-control declares four module dependencies. The three forbidden edges are the "
    "gateway (a management surface may not sit in the latency-critical path — ADR-0001, and "
    "there is nothing to tell it anyway because the cache EXPIRES — ADR-0012), provider-access "
    "(a decision recorder holds no path to a credential-bearing dispatcher — A-025, A-043), and "
    "call-ledger (a sink whose read path is gated by OQ-013 — the stated cost is that the "
    "withdraw confirmation cannot show live traffic volume)."
)


def _imported_modules(module: Path) -> list[tuple[int, str]]:
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    imported: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            name = "prope.release_control" if node.level else (node.module or "")
            imported.append((node.lineno, name))
    return imported


def _forbidden_prope_imports(module: Path) -> list[tuple[int, str]]:
    return [
        (line, name)
        for line, name in _imported_modules(module)
        if name.split(".")[0] == "prope"
        and not any(
            name == allowed or name.startswith(f"{allowed}.") for allowed in ALLOWED_PROPE_IMPORTS
        )
    ]


def _package_modules() -> list[Path]:
    modules = sorted(PACKAGE.rglob("*.py"))
    assert modules, f"no modules found under {PACKAGE}; the walk is looking in the wrong place"
    return modules


def _all_imports() -> set[str]:
    return {name for module in _package_modules() for _, name in _imported_modules(module)}


@pytest.mark.parametrize("module", _package_modules(), ids=lambda p: p.name)
def test_no_module_imports_a_prope_package_outside_the_allow_list(module: Path) -> None:
    found = _forbidden_prope_imports(module)
    assert not found, f"{module.name}: {found} — {VIOLATION}"


def test_the_three_forbidden_modules_are_imported_at_no_depth() -> None:
    """Stated separately from the allow-list so the failure names the rule
    rather than only the missing entry."""
    reached = [
        name
        for name in _all_imports()
        for forbidden in FORBIDDEN_MODULES
        if name.startswith(forbidden)
    ]
    assert reached == [], f"{sorted(reached)} — {VIOLATION}"


def test_the_broker_client_is_imported_nowhere_in_this_module() -> None:
    """`events.publishes: []` is a DECISION rather than a limitation, and this
    is where it stops being a paragraph.

    A broker EXISTS (ADR-0028) and this module still publishes nothing, because
    nothing needs to be told: the gateway's resolution entry expires within 30 s
    with no coordination between processes (ADR-0012), and no other module
    reacts to a release at all. Fanout invalidation would fire only on
    withdrawal — the rarest action in the product — would make `app` a broker
    consumer for the first time, and would not close the window under a restart.
    """
    broker = [name for name in _all_imports() if name.split(".")[0] in {"aio_pika", "aiormq"}]

    assert broker == [], (
        f"{sorted(broker)}: release-control runs in `worker` for a TIMER, not a queue "
        "(ADR-0051). It is the second module resident there that touches RabbitMQ not at all."
    )


def test_no_module_reaches_an_http_client_or_a_notification_channel() -> None:
    """`external_services: []`, and OQ-015's answer.

    The review queue is in-app only in the MVP (A-071) — no email, no Slack, no
    webhook. An outbound channel would be the first external service in the
    entire system, and OQ-015 was resolved by the user rather than by an agent
    reaching for `httpx`.
    """
    imported = _all_imports()

    assert not [
        name
        for name in imported
        if name.split(".")[0] in {"httpx", "requests", "smtplib", "email", "aiosmtplib"}
    ]


def test_the_diff_is_not_recomputed_here() -> None:
    """NOT difflib. The review screen renders prompt-registry's diff.

    `get_diff` chose `SequenceMatcher(autojunk=False)` in prompt-registry's own
    pass, and `autojunk` is load-bearing there. A second implementation in this
    module would be a second answer that can disagree with the first, on the one
    screen where a reviewer decides whether text reaches production.
    """
    imported = _all_imports()

    assert "difflib" not in imported, (
        "the diff on the review screen is prompt-registry's get_diff (INT-011). This module "
        "renders it and must not acquire a second implementation."
    )
    assert "prope.prompt_registry.seams" in imported


def test_history_is_written_through_the_validating_writer_and_never_by_table() -> None:
    """The `forbidden_dependencies` trap, asserted in both directions.

    The positive half matters more here than anywhere else in the build: this is
    the module whose product claim is *no release without a trail*, and a module
    that merely LACKS an import of `property_history.models` is not yet a module
    that records its eight events.
    """
    imported = _all_imports()

    assert "prope.property_history.append" in imported, (
        "release-control MUST call append() — eight events, in the same transaction as the "
        "decision they describe (ADR-0023). Its absence is not a missing feature; it is the "
        "product claim gone."
    )
    assert "prope.property_history.models" not in imported, (
        "a direct INSERT into history.history_event skips the action registry, the details "
        "allow-list (A-124) and requires_reason — and requires_reason is what enforces the three "
        "mandatory reasons this module promises (A-009, A-069, ADR-0024)."
    )


def test_the_registry_is_reached_through_its_seams_and_not_its_internals() -> None:
    """INT-011 through INT-014 are seams; `commands` and `repository` are not.

    This module issues three state-changing commands into prompt-registry and
    reads three things from it, and every one of the six arrives through
    `prompt_registry.seams`. Reaching past it — to `repository`, `commands` or
    `models` — is the shape ADR-0008's import contract exists to refuse, and it
    is the exact route by which a module that can write `revision.status` could
    defeat BR-03 by writing 'Approved' first.
    """
    reached = sorted(
        name
        for name in _all_imports()
        if name.startswith("prope.prompt_registry.")
        and name not in {"prope.prompt_registry.seams", "prope.prompt_registry.domain"}
    )

    assert reached == [], f"release-control reaches past prompt-registry's seam: {reached}"


def test_evaluation_is_reached_only_through_its_seam() -> None:
    """A-042: this module PULLS `get_review_summary` and evaluation never calls back.

    Evaluation is the one SOFT dependency in the list. The review screen renders
    without it and the eval panel says the evidence could not be loaded; approval
    stays possible and the reason becomes mandatory (A-070), because unknown
    evidence is treated like failing evidence and never like passing evidence.
    """
    reached = sorted(
        name
        for name in _all_imports()
        if name.startswith("prope.evaluation.") and name != "prope.evaluation.seams"
    )

    assert reached == [], f"release-control reaches past evaluation's seam: {reached}"


def test_the_module_writes_no_table_it_does_not_own() -> None:
    """ADR-0008, as far as an import walk can see it.

    One process (ADR-0026) and one role (ADR-0027) mean `prope_app` holds UPDATE
    on `registry.revision` whatever code is executing, so this rule is a checked
    convention rather than a seam. CI catches the SHAPE — no cross-module table
    model is imported, and no statement in this package names another module's
    schema — and the hourly reconciliation query catches the INSTANCE at runtime.
    """
    foreign_schemas = ("registry.", "evaluation.", "history.", "access.", "ledger.", "provider.")

    offenders: list[str] = []
    for module in _package_modules():
        source = module.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(module))
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
            if name != "text" or not node.args:
                continue
            statement = node.args[0]
            if not isinstance(statement, ast.Constant) or not isinstance(statement.value, str):
                continue
            for schema in foreign_schemas:
                if schema in statement.value:
                    offenders.append(f"{module.name}:{node.lineno} names {schema}")

    assert offenders == [], (
        f"{offenders}: release-control writes and reads no table it does not own. "
        "revision.status and prompt_property.released_version_id both move by COMMAND "
        "(INT-012, INT-013, INT-014), and a raw statement naming another module's schema is the "
        "runtime path the import contract cannot see."
    )


def test_the_walk_found_modules_and_imports_to_inspect() -> None:
    modules = _package_modules()

    assert len(modules) >= 9, modules
    assert sum(len(_imported_modules(module)) for module in modules) >= 30


def test_the_walk_refuses_a_module_that_reaches_another_bounded_context(tmp_path: Path) -> None:
    """The guard is known to have teeth, proven on a file written here."""
    tempting = tmp_path / "tell_the_gateway_to_drop_its_cache.py"
    tempting.write_text(
        "from prope.gateway.cache import reset_resolution_cache\n"
        "from prope.db.session import workspace_transaction\n",
        encoding="utf-8",
    )

    assert _forbidden_prope_imports(tempting) == [(1, "prope.gateway.cache")]
