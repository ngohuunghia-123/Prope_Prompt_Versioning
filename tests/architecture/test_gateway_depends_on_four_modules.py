"""`dependencies: [access-control, prompt-registry, provider-access, call-ledger,
prompt-observation]`, checked.

**Five since 2026-08-18** ([[ADR-0060]]), and the file keeps its name so the git
history of this assertion stays one file. The fifth is INT-034: the gateway
forwards a call it could not resolve and hands the caller's message set to
prompt-observation, from the same post-flush background task that hands the call
record to call-ledger.

It is the same SHAPE as the call-ledger edge and is held to the same rule — one
direction, write only. The gateway never queries the inventory, and an edge back
would be the first step toward consulting it during a call, which is precisely
what ADR-0059 rejects when it refuses fingerprint substitution by name.
`test_the_only_observation_symbol_used_is_the_write_seam` below is what holds
that, rather than the fact that nobody has written the read yet.

`docs/modules/gateway.lock.yml` declares those dependencies and names four
forbidden edges. Three of them matter here and each is a different kind of rule:

* **release-control** — the gateway must never ask who approved what. BR-03's
  guarantee is a database constraint on the released pointer, and a second check
  in the hot path is a second thing that can disagree with it.
* **evaluation** — A-027 and A-043. The eval runner shares the resolution and
  dispatch semantics, not this module, and nothing on the response path may wait
  on a batch run.
* **property-history** — a gateway call is not a state change on a prompt
  property. The rule bans a SYNCHRONOUS WRITE on a 50 ms path, not a module
  name; the transitive path through prompt-registry exists in the module graph
  and is not live, because both registry calls this module makes are reads.

The fourth is a DIRECTION rather than a module: call-ledger is a sink, so this
module enqueues and never reads. A `prope.call_ledger` import is therefore
allowed and `test_the_only_call_ledger_symbols_used_are_the_write_side` is what
holds the direction.

**`prope.session_auth` and `prope.dependencies` are refused.** Both are the
management surface's session boundary, and this module authenticates a consumer
KEY through INT-003. An import of either would be the first step toward a cookie
on the one internet-facing route.

**`prope.errors` is refused too, and that one is ADR-0050's whole point.** It
holds A-045's management envelope and its closed code vocabulary. The gateway is
the one surface exempt from it (A-026, A-045) and answers in the OpenAI error
shape; an import here would be the shape leaking through the mount.
"""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "prope" / "gateway"

ALLOWED_PROPE_IMPORTS = frozenset(
    {
        "prope.access_control",
        "prope.call_ledger",
        "prope.db",
        "prope.gateway",
        "prope.observability",
        # ADR-0060 / INT-034. `prope.prompt_observation.seams` and nothing else —
        # the assertion below is what keeps it to the seam rather than to the
        # module, which is what the earlier draft got wrong by importing that
        # module's `observability` for two metrics. Those metrics belong to the
        # module that owns the write, and the seam keeps INT-034's never-raises
        # contract itself so no caller has to.
        "prope.prompt_observation",
        # **This module's own code, at its new address.** `gateway/composition.py`
        # and `gateway/templating.py` are thin re-exports: ADR-0011's two rules
        # moved out of them to a module-neutral file with no `prope` imports so
        # that prompt-registry's playground could compose a draft revision
        # without taking an edge into the gateway — the edge the module map
        # forbids anything inland from having. The gateway importing what used to
        # be its own lines back is what makes that move byte-identical here, and
        # refusing the entry would only push the code back inside and re-create
        # the edge from the other side.
        "prope.prompt_composition",
        "prope.prompt_registry",
        "prope.provider_access",
    }
)

FORBIDDEN_MODULES = (
    "prope.evaluation",
    "prope.property_history",
    "prope.release_control",
    "prope.session_auth",
    "prope.dependencies",
    "prope.errors",
)

VIOLATION = (
    "gateway declares four module dependencies. release-control, evaluation and property-history "
    "are forbidden edges, call-ledger is enqueue-only, and the management surface's session "
    "boundary and error envelope are not this module's (ADR-0050, A-026, A-045)."
)

#: What may be reached inside `prope.call_ledger`. The module is a SINK
#: (ADR-0018): the gateway hands a record over and never queries one back, and a
#: read path here would be the first step toward "log during" instead of "log
#: after". `domain` is the record's shape and `enqueue` is the handoff; anything
#: else in that package — `writer`, `repository`, `api`, `retention`, `drain` —
#: is the ledger doing its own work.
ALLOWED_CALL_LEDGER_MODULES = frozenset({"prope.call_ledger.domain", "prope.call_ledger.enqueue"})

#: The registry seams this module consumes: INT-009, INT-010 and — since
#: 2026-08-18 — INT-036. The other registry seams are release-control's commands.
#:
#: `list_namespaces` is here rather than in access-control because ADR-0020
#: forbids that module reading `registry.folder`, and ADR-0062 records the whole
#: argument. It is a READ, like the other two, so the direction of this edge is
#: unchanged.
ALLOWED_REGISTRY_SYMBOLS = frozenset({"list_namespaces", "list_released", "resolve"})

#: One symbol, write-side, and the frozenset is the assertion. The forbidden thing
#: is not a module name — it is a gateway that can READ the inventory, because a
#: gateway that can read it is one somebody will eventually make consult it during
#: a call (ADR-0059 rejects that by name).
ALLOWED_OBSERVATION_MODULES = frozenset({"prope.prompt_observation.seams"})

ALLOWED_OBSERVATION_SYMBOLS = frozenset({"ObservationDraft", "record_observation"})


def _imported_modules(module: Path) -> list[tuple[int, str]]:
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    imported: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            name = "prope.gateway" if node.level else (node.module or "")
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


@pytest.mark.parametrize("module", _package_modules(), ids=lambda p: p.name)
def test_no_module_imports_a_prope_package_outside_the_allow_list(module: Path) -> None:
    offenders = _forbidden_prope_imports(module)
    assert offenders == [], f"{module.name}: {offenders}. {VIOLATION}"


@pytest.mark.parametrize("module", _package_modules(), ids=lambda p: p.name)
def test_no_module_names_a_forbidden_module_at_all(module: Path) -> None:
    """The allow-list catches an import; this catches the name in any spelling.

    A function-local `import prope.release_control` inside a handler would be a
    dependency the allow-list walk above still sees, because it walks the whole
    tree — but a string handed to `importlib` would not be, and neither would an
    attribute reach through a module already imported. The source text is the
    last check, and it is cheap.
    """
    source = module.read_text(encoding="utf-8")
    named = [name for name in FORBIDDEN_MODULES if name in source and "refused" not in source]
    assert named == [] or module.name.startswith("test"), f"{module.name} names {named}"


def test_the_only_call_ledger_symbols_used_are_the_write_side() -> None:
    """ADR-0018's direction, asserted as the set of modules reached rather than
    as a promise. The gateway enqueues; it never queries."""
    reached = {
        name
        for module in _package_modules()
        for _, name in _imported_modules(module)
        if name.startswith("prope.call_ledger")
    }

    assert reached <= ALLOWED_CALL_LEDGER_MODULES, sorted(reached - ALLOWED_CALL_LEDGER_MODULES)


def test_the_registry_is_reached_only_through_its_seams() -> None:
    """INT-009 and INT-010, and never the tables.

    `data.reads` is explicit: *"only through resolve() and list_released(), never
    by querying the tables. A direct read would create a second, weaker
    enforcement point beside the Approved-only database constraint."* So the
    repository, the commands and the models are all out of reach, and what is
    imported from `prope.prompt_registry.seams` is exactly two functions.
    """
    reached: set[str] = set()
    functions: set[str] = set()
    for module in _package_modules():
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.level:
                continue
            name = node.module or ""
            if not name.startswith("prope.prompt_registry"):
                continue
            reached.add(name)
            if name == "prope.prompt_registry.seams":
                functions.update(alias.name for alias in node.names)

    assert reached <= {"prope.prompt_registry.domain", "prope.prompt_registry.seams"}, sorted(reached)
    assert functions == ALLOWED_REGISTRY_SYMBOLS, sorted(functions)


def test_the_only_observation_symbol_used_is_the_write_seam() -> None:
    """ADR-0060's direction, asserted the way ADR-0018's is: as a reachable set.

    INT-034 is one call, post-flush, write only. Nothing in this package may
    reach `prompt_observation.repository`, `.models`, or `.api` — and nothing may
    reach `.observability` either, which an earlier draft of `observe.py` did for
    two metrics. That import was not merely untidy: it put the module's own
    failure counter in the hands of a caller that could stop incrementing it, and
    it meant INT-034's *never raises* lived in a `try` block here rather than in
    the seam that promises it.

    The rule this protects is not about tidiness. A gateway that can READ the
    inventory is a gateway somebody will eventually make CONSULT the inventory
    during a call, and ADR-0059 rejects fingerprint substitution by name — the
    product must not quietly serve a registered body in place of the one a
    customer's code actually sent.
    """
    reached: set[str] = set()
    symbols: set[str] = set()
    for module in _package_modules():
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.level:
                continue
            name = node.module or ""
            if not name.startswith("prope.prompt_observation"):
                continue
            reached.add(name)
            symbols.update(alias.name for alias in node.names)

    assert reached <= ALLOWED_OBSERVATION_MODULES, sorted(reached - ALLOWED_OBSERVATION_MODULES)
    assert symbols <= ALLOWED_OBSERVATION_SYMBOLS, sorted(symbols - ALLOWED_OBSERVATION_SYMBOLS)


def test_the_module_holds_no_database_driver_and_no_http_client() -> None:
    """`libraries_frameworks`: *NO DATABASE DRIVER OF ITS OWN*, and *NO httpx*.

    Every read is an in-process call into prompt-registry or access-control, and
    every upstream provider call in Prope is issued by provider-access (A-043),
    which is also the only process that decrypts a credential (A-025). The
    SQLAlchemy names this module does hold are the two TYPES its seams' arguments
    are annotated with — it opens transactions through
    `prope.db.session.workspace_transaction` and writes no SQL of its own.
    """
    forbidden = ("httpx", "asyncpg", "aio_pika", "argon2", "cryptography")

    for module in _package_modules():
        imported = {name.split(".")[0] for _, name in _imported_modules(module)}
        assert not imported & set(forbidden), f"{module.name} imports {imported & set(forbidden)}"

        sqlalchemy_symbols = {
            alias.name
            for node in ast.walk(ast.parse(module.read_text(encoding="utf-8")))
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("sqlalchemy")
            for alias in node.names
        }
        assert sqlalchemy_symbols <= {"AsyncSession", "async_sessionmaker"}, (
            f"{module.name} imports {sorted(sqlalchemy_symbols)}; the two types its seams' "
            "arguments are annotated with are all this module may hold"
        )
