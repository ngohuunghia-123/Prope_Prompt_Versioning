"""The assembled route table, asserted rather than described.

**This is the single-module form of assertions that cannot run in their full
form until Phase 23.** AC-10 (*"every route declares an action from the
vocabulary"*) and prompt-registry's route-uniqueness rule are both properties of
the **assembled** table — what is mounted in total, once every module has had its
say — and seven of the eight modules do not exist yet. PITFALLS § 5 records that
they *"cannot actually run until every module is mounted — i.e. not before phase
23"*. So this file asserts them over the one module that is mounted, using
helpers (``prope.session_auth.assembled_routes``, ``declared_action``,
``declares_session``) that live in the shared module precisely so **Phase 23
extends a test rather than inventing one**.

**CL-10's full claim is Phase 3's and its cross-module form is Phase 23's.** This
phase's obligation is narrower and entirely negative: do not mount a route that
would fail either. The OpenAPI walk below is that floor.

**D-13's explicit composition is what makes any of this writable.** A route that
could appear because a file was named a certain way is the shape these assertions
exist to refuse — the test would be checking a list the discovery mechanism also
produced. ``prope.app`` imports one router by name and includes it, and a
structural assertion here says so.
"""

import ast
import inspect
from pathlib import Path

from fastapi import FastAPI

import prope.app
import prope.worker
from prope.app import app
from prope.session_auth import (
    MANAGEMENT_ACTIONS,
    assembled_routes,
    declared_action,
    declares_action,
    declares_session,
)

#: **The whole table, as literal strings.** Seven paths: INT-028's five plus
#: INT-030's two. Written out rather than derived, because a test that computed
#: its expectation from the application would pass whatever the application
#: happened to mount — which is the failure mode this list exists to catch. An
#: extra route fails here as loudly as a missing one.
#:
#: ``POST|GET /api/v1/prices`` is one line in ``interfaces.md`` and two paths;
#: INT-028's own text settles the count by saying *"5 routes"* beside four bullet
#: lines. Every count in this file is a **path** count.
EXPECTED_ROUTES = frozenset(
    {
        ("POST", "/api/v1/prices"),
        ("GET", "/api/v1/prices"),
        ("GET", "/api/v1/prices/unpriced"),
        ("PUT", "/api/v1/workspaces/{id}/spend-ceiling"),
        ("PUT", "/api/v1/workspaces/{id}/retention"),
        ("GET", "/healthz"),
        ("GET", "/readyz"),
    }
)

#: A-045: ``/healthz`` and ``/readyz`` are unversioned, deliberately outside
#: ``/api/v1``. INT-030 says the same in its own Version column.
UNVERSIONED = frozenset({"/healthz", "/readyz"})

#: Field, property and parameter names that would mean the body store had grown a
#: read path. ``ledger.call_body``'s three columns are ``request_body``,
#: ``response_body`` and ``byte_size``; the rest are the names somebody would
#: reach for while adding one (ADR-0018, A-105, CL-10).
FORBIDDEN_FIELD_NAMES = frozenset(
    {
        "request_body",
        "response_body",
        "byte_size",
        "body",
        "bytes",
        "payload",
        "request_payload",
        "response_payload",
        "raw_body",
        "call_body",
    }
)

APP_SOURCE = Path(prope.app.__file__).read_text(encoding="utf-8")


def _table() -> set[tuple[str, str]]:
    """Every ``(method, path)`` the assembled application serves."""
    table: set[tuple[str, str]] = set()
    for route in assembled_routes(app):
        for method in route.methods:
            table.add((method, route.path))
    return table


def test_the_assembled_table_is_exactly_the_seven_paths() -> None:
    """Seven paths, compared against a literal list. Both directions fail."""
    assert _table() == set(EXPECTED_ROUTES)


def test_the_openapi_schema_agrees_with_the_route_table() -> None:
    """The generated spec and the served table are the same seven paths.

    INT-028's spec line is *"generated from FastAPI + pydantic v2 -> OpenAPI"*,
    so the schema is a real artifact rather than documentation — and a route
    excluded from the schema while still being served is exactly the shape a
    later reader would use to slip a sixth path past the list above.
    """
    documented = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }

    assert documented == set(EXPECTED_ROUTES)


def test_every_versioned_route_declares_a_session_and_an_action() -> None:
    """AC-10's single-module form, and Pitfall 11's answer, over the real table.

    **Not vacuous**: the count is asserted first. ``include_router`` does not
    flatten routes into ``app.routes``, so a walk that missed them would iterate
    an empty set and pass.
    """
    versioned = [route for route in assembled_routes(app) if route.path.startswith("/api/v1")]

    # Both counts, because the difference is the thing that has bitten before:
    # INT-028 registers **5 routes** across **4 distinct paths**, since
    # ``POST|GET /api/v1/prices`` is one line in the interfaces table and two
    # operations here.
    assert len(versioned) == 5, "INT-028 registers five /api/v1 routes"
    assert len({route.path for route in versioned}) == 4, "across four distinct paths"

    for route in versioned:
        assert declares_session(route), route.path
        action = declared_action(route)
        assert action is not None, route.path
        assert action in MANAGEMENT_ACTIONS, action


def test_every_registered_action_is_declared_exactly_once() -> None:
    """Five members, five routes, no reuse.

    A copy-pasted route that kept its neighbour's action would declare a
    vocabulary member for a thing it does not do, and Phase 7's permission wiring
    would grant on that mistake. ``GET`` and ``POST`` on ``/api/v1/prices`` are
    separate routes with separate actions, which is why this counts operations
    rather than paths.
    """
    declared = []
    for route in assembled_routes(app):
        if not route.path.startswith("/api/v1"):
            continue
        action = declared_action(route)
        declared.extend([action] * len(route.methods))

    assert sorted(declared) == sorted(MANAGEMENT_ACTIONS)


def test_the_health_routes_are_unversioned_and_declare_nothing() -> None:
    """INT-030: unversioned, and reachable by an operator who has no session.

    A health check behind an authentication boundary is a health check the
    compose healthcheck cannot make, and the readiness answer would then depend
    on the module whose availability it is reporting.
    """
    health = [route for route in assembled_routes(app) if route.path in UNVERSIONED]

    assert len(health) == len(UNVERSIONED)
    for route in health:
        assert not route.path.startswith("/api/v1")
        assert not declares_session(route), route.path
        assert declared_action(route) is None, route.path


def test_no_schema_property_or_parameter_exposes_a_stored_body() -> None:
    """ADR-0018 / A-105: the body store has no read path, asserted over the spec.

    Over the **assembled OpenAPI schema** rather than over the source, because
    the claim is about what the API exposes and a model can reach the API through
    a route nobody remembered to read.
    """
    schema = app.openapi()

    offenders: list[str] = []
    for name, model in schema.get("components", {}).get("schemas", {}).items():
        for field in model.get("properties", {}):
            if field.lower() in FORBIDDEN_FIELD_NAMES:
                offenders.append(f"{name}.{field}")

    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            for parameter in operation.get("parameters", []):
                if parameter["name"].lower() in FORBIDDEN_FIELD_NAMES:
                    offenders.append(f"{method.upper()} {path} ?{parameter['name']}")

    assert offenders == []


def test_the_application_is_composed_by_hand_and_not_discovered() -> None:
    """D-13. The list of mounted routers is the import block, and nothing else.

    Three things would break the property, so three things are refused: a
    dynamic import, a filename-based scan, and a call to ``__import__``. The
    positive half is asserted too — the router is imported by name and included —
    because a file that merely *lacks* ``importlib`` is not yet a file that
    composes explicitly.
    """
    tree = ast.parse(APP_SOURCE, filename=prope.app.__file__)

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert "importlib" not in imported
    assert "pkgutil" not in imported

    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "__import__" not in calls

    assert "from prope.call_ledger.api import router as call_ledger_router" in APP_SOURCE
    assert "application.include_router(call_ledger_router)" in APP_SOURCE


def test_both_processes_declare_the_topology_from_one_definition() -> None:
    """D-24, fully asserted for the first time: ``app`` and ``worker`` share it.

    Plan 02-03 could only assert half of this, because ``prope.app`` did not
    exist. Identity rather than a name match: two modules each holding their own
    ``declare_topology`` would satisfy a name check and could then drift, which
    is the exact failure D-24 makes structurally impossible by having one
    definition.
    """
    assert prope.app.declare_topology is prope.worker.declare_topology

    startup = inspect.getsource(prope.app._start_publisher)
    assert "declare_topology(channel)" in startup


def test_the_module_states_the_readiness_rule_and_the_loss_window_that_survives() -> None:
    """D-16 is written at the code, not only in a plan, and that is checked.

    Plan 02-03 established the posture (``test_the_module_names_both_taskgroup_
    traps_and_the_windows_constraint``): a reasoning obligation that is only
    reviewed is an obligation somebody deletes in a tidy-up. The readiness rule
    and the loss window it leaves open are the two most deletable paragraphs in
    this repository, because both read as commentary until the day they matter.

    **This assertion was kept and its subject changed, deliberately.** Plan 02-05
    asserted ``"records genuinely"`` — the Phase 2 sentence saying the fallback
    did not exist yet and records were lost. CL-01 made that sentence false, and a
    docstring that has stopped being true is worse than no docstring, so the
    string that must now be present is ``"A-139"``: the remaining loss window is
    what the paragraph is about, and only the closed form names it.
    """
    assert "degraded-and-counted" in APP_SOURCE
    assert "CL-01" in APP_SOURCE
    assert "metadata_dropped_total" in APP_SOURCE
    assert "A-139" in APP_SOURCE


def test_both_publisher_branches_are_supervised_jobs_and_neither_is_a_bare_task() -> None:
    """D-32, asserted over the source because it is a composition property.

    A publisher started as a bare ``asyncio.create_task`` ends silently when an
    exception escapes it: every later ``enqueue`` fills the handoff and then
    drops, with no crash, no restart, and nothing in ``/readyz`` — which is the
    database alone by decision. The fallback makes that reachable, because a
    fallback can raise where ``publish_record`` could not.

    Both branches are asserted, not only the healthy one: **a job made entirely
    of fallback calls is the one that needs the restart most.**

    The refused string is the exact bare-task composition, not the identifier —
    ``run_publisher`` still appears inside the publisher branch's job closure, and
    that is correct.
    """
    assert "asyncio.create_task(run_publisher(" not in APP_SOURCE

    startup = inspect.getsource(prope.app._start_publisher)
    # Counted on the job map rather than on the bare name: the docstring above
    # explains why ``supervise()`` cannot be awaited from a lifespan, and a
    # substring count would count that sentence.
    assert startup.count("supervise({JOB_") == 2, "both branches compose through supervise()"
    assert "JOB_CALL_RECORD_PUBLISHER: publisher_job" in startup
    assert "JOB_CALL_RECORD_FALLBACK: fallback_only_job" in startup
    assert "build_fallback_writer(application.state.sessionmaker)" in startup


def test_the_application_object_makefile_run_targets_exists() -> None:
    """``prope.app:app`` — the target ``Makefile`` has named since Phase 1."""
    makefile = (Path(prope.app.__file__).resolve().parents[2] / "Makefile").read_text(
        encoding="utf-8"
    )

    assert "prope.app:app" in makefile
    assert isinstance(app, FastAPI)


def test_the_router_and_the_health_routes_are_the_only_things_mounted() -> None:
    """No ``/docs``, no ``/redoc``, no ``/openapi.json`` on the served table.

    FastAPI mounts all three by default. INT-028 says the spec is *generated*
    from the code, not that it is served, and three unauthenticated routes behind
    Caddy's single ingress would be three routes nobody decided to have — as well
    as the eighth, ninth and tenth entries in a table this phase asserts holds
    seven.
    """
    served: set[str] = set()
    for route in app.routes:
        expand = getattr(route, "effective_route_contexts", None)
        if expand is not None:
            served.update(context.path for context in expand())
        else:
            served.add(getattr(route, "path", ""))

    assert "/docs" not in served
    assert "/redoc" not in served
    assert "/openapi.json" not in served


def test_the_assembled_table_holds_no_route_this_phase_did_not_declare() -> None:
    """A belt-and-braces count, in the shape Phase 23 will grow.

    Phase 23 replaces the literal set above with eight modules' worth of paths.
    Until then this is the assertion that a router mounted for a side effect —
    a metrics endpoint, a debug route, a second health check — cannot arrive
    unnoticed.
    """
    extra = _table() - set(EXPECTED_ROUTES)
    missing = set(EXPECTED_ROUTES) - _table()

    assert extra == set(), f"routes nobody declared: {sorted(extra)}"
    assert missing == set(), f"routes that stopped being served: {sorted(missing)}"


def test_declares_action_refuses_an_action_outside_the_vocabulary() -> None:
    """A-115's closure, enforced at import so a typo is a startup error.

    ``ManagementAction`` is closed and an unrecognised action is a deny rather
    than an error in INT-001 — because *"a typo that silently allows is the
    failure this closure exists to prevent"*. A route is built at module import,
    so refusing here means the process does not come up rather than coming up
    with a route Phase 7's wiring cannot resolve.
    """
    for outside in ("call_ledger.price.reed", "", None, object()):
        try:
            declares_action(outside)  # type: ignore[arg-type]
        except ValueError:
            continue
        raise AssertionError(f"{outside!r} was accepted into the closed vocabulary")


def test_the_action_vocabulary_is_a_str_enum_of_machine_codes() -> None:
    """Literal ASCII, dotted, and prefixed by the module that owns the route.

    ``domain.py``'s rule for statuses, applied to actions: a value that is
    stored, transmitted or compared is a fact and stays literal wherever it
    travels. The ``call_ledger.`` prefix is what lets seven more modules add
    members to one vocabulary without ``price.read`` colliding.
    """
    for action in MANAGEMENT_ACTIONS:
        assert isinstance(action, str)
        assert action.value.startswith("call_ledger.")
        assert action.value == action.value.lower()


def test_no_route_is_reachable_except_through_the_application() -> None:
    """The router carries the prefix; nothing mounts it a second time.

    ``prope.call_ledger.api.router`` is included exactly once, so every path it
    serves appears once in the assembled table. A router included twice — under
    two prefixes, or by two modules — is prompt-registry's route-uniqueness rule
    broken in the way that is hardest to see, because both copies work.
    """
    paths = [route.path for route in assembled_routes(app) for _ in route.methods]

    assert len(paths) == len(EXPECTED_ROUTES)
    assert APP_SOURCE.count("include_router") == 1
