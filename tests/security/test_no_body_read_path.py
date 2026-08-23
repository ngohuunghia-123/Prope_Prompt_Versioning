"""AC-10's full claim, at the three layers that can be asserted today.

**Phase 2 asserted the first third and said so.** ``tests/architecture/
test_route_table.py`` walks the assembled table and the OpenAPI schema for
``FORBIDDEN_FIELD_NAMES``, and its own docstring records that *"CL-10's full
claim is Phase 3's"*. AC-10's words are *"the module's entire HTTP **and
internal** surface"*, and the two layers that sentence reaches which a route walk
does not are the two that are actually at risk:

**The internal Python surface.** ``get_run_totals`` is a function, not a route. A
body reaching a caller through a returned dataclass would satisfy every
route-table assertion in this repository, and would keep satisfying them for
twenty-one more phases. Evaluation calls these seams in process, with no HTTP
between it and them.

**The statements.** ``prope_app``'s privileges on ``ledger.call_body`` are
``SELECT, INSERT, DELETE`` and **the ``SELECT`` is load-bearing** — the retention
``DELETE ... WHERE expires_at <= $1`` reads a column, and since D-34 the body
upsert's ``ON CONFLICT`` reads one too. ``0003_ledger_tables.py:246-252`` says
this in a comment addressed to this phase by name: *"Revoking SELECT here in the
name of 'no read path' would break the retention job. AC-10's no-read-path
guarantee is a property of the ROUTE TABLE (Phase 3), not of the grant matrix."*
**So the database is deliberately not the guarantee here**, and the thing that
stands in for a grant is an enumeration of every statement in ``src/`` that names
the table, asserted as a set that fails in both directions.

**What this file is not.** It is not the cross-module form of AC-10 — that needs
eight modules mounted and is Phase 23's (``.planning/research/PITFALLS.md`` §5).
It is the single-module form, written with the shared helpers
(:func:`prope.session_auth.assembled_routes`) so **Phase 23 extends this file
rather than inventing a fourth**. And it is not a narrowing of ``prope_app``'s
grants: the last test here asserts, deliberately, that ``prope_app`` **can** read
a body, because that privilege is what retention runs on.

**There is a fourth reader none of these three layers can see.** ``prope_report``
is ``LOGIN BYPASSRLS`` and holds ``SELECT`` on ``ledger.call_body``, so one
statement on that credential reads every stored body in every workspace. It is
asserted on purpose in ``tests/security/test_report_role_can_read_bodies.py`` and
routed to ``docs/brainstorm/open_questions/OQ-025.md``, because *"we looked and
decided not to"* and *"nobody looked"* must be distinguishable a year later.

**Every escape hatch below is an entry with a written reason and an asserted
size**, following ``tests/architecture/test_no_sql_interpolation.py``'s rule that
a legitimate exception is an entry in a list and never a relaxed assertion. A
body has to be nameable to be written and to travel, so a small number of
write-side and transport types name one legitimately; an exemption list that
grows silently is an assertion that has stopped asserting.

``FORBIDDEN_FIELD_NAMES`` is **imported, never re-declared**. Two lists would be
two places for the eleventh name to be added to only one.
"""

import ast
import dataclasses
import importlib
import inspect
import pkgutil
import re
import typing
from pathlib import Path
from types import ModuleType
from typing import Any

import pydantic
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

import prope.call_ledger
import prope.worker
from prope.app import app
from prope.call_ledger.domain import CallBodyDraft, WriteResult
from prope.call_ledger.seams import CeilingDecision, EvalUsageRow, RunTotals
from prope.call_ledger.writer import write_records
from prope.db.session import workspace_transaction
from prope.session_auth import assembled_routes
from tests.architecture.test_route_table import (
    EXPECTED_ROUTES,
    FORBIDDEN_FIELD_NAMES,
    SANCTIONED_BODY_FIELDS,
)
from tests.unit import WORKSPACE_A, gateway_draft

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "prope"

#: Write-side input and transport types. A body must be NAMEABLE to be written
#: and to travel, and these are the four types in the package that name one. An
#: entry is a qualified name and the comment beside it is its reason. Any
#: addition is a claim that a FIFTH type needs to name a body, which is a claim
#: CL-10 and ADR-0018 should be asked about — so the SIZE is asserted below as
#: well as the contents, and
#: ``test_the_exemption_lists_are_exactly_what_names_a_body`` asserts the exact
#: field each entry is exempted for.
#:
#: Matched on the type's DEFINITION site, not on the module the walk found it in,
#: so re-exporting one of these into a second module exempts the same type rather
#: than opening a second hole.
BODY_NAMING_EXEMPT_TYPES: frozenset[str] = frozenset(
    {
        "prope.call_ledger.domain.CallBodyDraft",  # the body a caller hands in
        "prope.call_ledger.domain.CallRecordDraft",  # holds it by composition — field `body`
        "prope.call_ledger.envelope.CallRecordPayload",  # the body on the wire
        "prope.call_ledger.envelope.CallRecordEnvelope",  # the transport wrapper — field `payload`
    }
)

#: FastAPI request-body PARAMETERS, which are a different kind of name from the
#: four above: a route's input, not a stored body. Three route handlers take
#: ``payload``, which is a member of ``FORBIDDEN_FIELD_NAMES``. **A parameter
#: named ``payload`` on a route handler is not the failure CL-10 is about** — the
#: failure is a body coming OUT.
#:
#: Two lists rather than one, and the split is load-bearing: merging these three
#: callables into a frozenset of TYPE names would silently exempt any future type
#: that happened to share a name with one of them.
BODY_NAMING_EXEMPT_PARAMETERS: frozenset[str] = frozenset(
    {
        "prope.call_ledger.api.create_price_row",  # payload: PriceRowCreate
        "prope.call_ledger.api.set_spend_ceiling",  # payload: SpendCeilingSet
        "prope.call_ledger.api.set_retention",  # payload: RetentionSet
        "prope.call_ledger.api.put_observability_content_access",  # payload: controlled read opt-in
    }
)

#: Every file under ``src/`` that may name ``ledger.call_body`` in a SQL context,
#: and why. An entry is a claim that another statement needs to touch the body
#: table, which is a claim ADR-0018 should be asked about. A legitimate exception
#: is an entry here, never a relaxed assertion.
#:
#: **``worker.py`` is the fourth entry and it arrived during this phase**, with
#: D-43's ``oldest_body_age_seconds`` gauge (plan 03-04). It is the only SELECT on
#: the table in ``src/`` and it reads ``min(created_at)`` — an age, never a body
#: column — which is asserted separately by
#: ``test_the_age_gauge_selects_no_body_column`` rather than left to this
#: comment. It is exactly the kind of arrival this map exists to make visible.
BODY_TABLE_WRITERS: dict[str, str] = {
    "call_ledger/writer.py": "UPSERT_CALL_BODY — the one insert (D-34's ON CONFLICT DO NOTHING)",
    "call_ledger/retention.py": "the bounded expiry DELETE (A-132)",
    "call_ledger/models.py": "the Core Table declaration — a name, not a statement",
    "worker.py": "OLDEST_BODY_CREATED_AT — D-43's age gauge, min(created_at) and no body column",
    "call_ledger/seams.py": "ADR-0059's private, prompt-scoped content seam; policy and audit are enforced before it is called",
}

#: A floor, not a target. Four sites match today, one per file above. It exists so
#: a matcher that stopped matching cannot pass by inspecting nothing —
#: ``test_no_sql_interpolation.py``'s rule applies verbatim: **do not raise this
#: to make a failure pass**, investigate what arrived. Lowering it is a different
#: act and belongs with the removal of a map entry.
MINIMUM_BODY_TABLE_SITES = 5

#: Floors for the internal walk, in the same posture. Measured against this tree
#: this session — 15 modules, 34 public callables, 23 public dataclasses and
#: pydantic models — as an **agent measurement, labelled as one**: no detector
#: exists in this environment (ORCHESTRATION §0). They sit below today's counts so
#: an ordinary addition does not touch them, and far enough above zero that a walk
#: which imported nothing fails.
MINIMUM_MODULES = 10
MINIMUM_PUBLIC_CALLABLES = 20
MINIMUM_PUBLIC_MODELS = 15

#: ``/api/v1/workspaces/{id}/retention`` — the braces are the path parameter.
PATH_PARAMETER = re.compile(r"\{([^}]+)\}")


def _package_modules() -> list[ModuleType]:
    """Every module in ``prope.call_ledger``, discovered and never listed.

    ``test_no_sql_interpolation.py``'s reason applies verbatim: *"so a module
    added in Phase 7 is covered by this test on the day it is written and nobody
    has to remember to add it"*. A written-down module list is a list somebody
    has to remember to extend, and the one they forget is the one that matters.
    """
    modules = [prope.call_ledger]
    for info in pkgutil.walk_packages(
        prope.call_ledger.__path__, prope.call_ledger.__name__ + "."
    ):
        modules.append(importlib.import_module(info.name))
    assert len(modules) >= MINIMUM_MODULES, (
        f"the package walk found {len(modules)} modules; it is looking in the wrong place"
    )
    return modules


PACKAGE_MODULES = _package_modules()


def _origin(obj: Any) -> str:
    """Where a name was DEFINED, which is the identity an exemption is keyed on."""
    return f"{getattr(obj, '__module__', '?')}.{getattr(obj, '__qualname__', '?')}"


def _is_model(obj: Any) -> bool:
    """A dataclass or a pydantic model — the two shapes a field can hide in."""
    if not inspect.isclass(obj):
        return False
    return dataclasses.is_dataclass(obj) or issubclass(obj, pydantic.BaseModel)


def _field_names(obj: Any) -> list[str]:
    """Public field names, or an empty list for anything that is not a model."""
    if not _is_model(obj):
        return []
    if issubclass(obj, pydantic.BaseModel):
        return [name for name in obj.model_fields if not name.startswith("_")]
    return [field.name for field in dataclasses.fields(obj) if not field.name.startswith("_")]


def _public_members(module: ModuleType) -> list[tuple[str, Any]]:
    """Every public name in a module's namespace that ``prope`` itself defines.

    **Re-exports are included and third-party imports are not**, and both halves
    are deliberate. A body-naming type this package imports and re-exports is
    reachable from ``prope.call_ledger`` and is exactly the shape AC-10 refuses;
    ``pydantic.BaseModel``, which every schema module imports, is a tool rather
    than part of this module's surface, and asserting over it would make this
    test fail on somebody else's release.
    """
    members: list[tuple[str, Any]] = []
    for name, obj in vars(module).items():
        if name.startswith("_"):
            continue
        home = getattr(obj, "__module__", None)
        if not isinstance(home, str) or not (home == "prope" or home.startswith("prope.")):
            continue
        members.append((name, obj))
    return members


def _is_callable(obj: Any) -> bool:
    return inspect.isfunction(obj) or inspect.iscoroutinefunction(obj)


def _return_annotation(function: Any) -> tuple[Any, bool]:
    """The resolved return annotation, and whether resolution succeeded.

    ``typing.get_type_hints`` first, because a module carrying ``from __future__
    import annotations`` stores its annotations as **strings** and a walk that
    compared a string against a set of field names would pass silently — the
    exact vacuity this layer exists to refuse. No module in ``src/`` uses that
    import today; the resolution is asserted rather than assumed so that the day
    one does, this test says so instead of going quiet.
    """
    try:
        hints = typing.get_type_hints(function)
    except Exception:  # pragma: no cover - a resolution failure is reported, not swallowed
        return None, False
    if "return" in hints:
        return hints["return"], True
    annotation = inspect.signature(function).return_annotation
    if annotation is inspect.Signature.empty:
        return None, True
    return annotation, not isinstance(annotation, str)


def _body_naming_offenders(module: ModuleType, *, exempt: bool) -> list[str]:
    """Public names in ``module`` that name a body, as ``qualified.name`` strings.

    ``exempt=False`` is what the exemption test uses to prove the lists are doing
    work: it reports what the walk would have found with both hatches closed.
    """
    offenders: list[str] = []
    for _, obj in _public_members(module):
        origin = _origin(obj)
        if _is_callable(obj):
            if exempt and origin in BODY_NAMING_EXEMPT_PARAMETERS:
                continue
            for parameter in inspect.signature(obj).parameters:
                if parameter.lower() in FORBIDDEN_FIELD_NAMES:
                    offenders.append(f"{origin}({parameter})")
        elif _is_model(obj):
            if exempt and origin in BODY_NAMING_EXEMPT_TYPES:
                continue
            for field in _field_names(obj):
                if field.lower() in FORBIDDEN_FIELD_NAMES:
                    offenders.append(f"{origin}.{field}")
    return offenders


# ---------------------------------------------------------------------------
# LAYER 1 — the assembled HTTP surface
# ---------------------------------------------------------------------------


def _request_body_model(route: Any) -> Any | None:
    """The pydantic model a route accepts as its request body, if it has one."""
    body_field = getattr(route, "body_field", None)
    if body_field is None:
        return None
    return getattr(body_field.field_info, "annotation", None)


def test_no_route_path_parameter_or_request_body_field_names_a_stored_body() -> None:
    """Layer 1, over the served table rather than over the generated spec.

    **The dependency is stated rather than duplicated.**
    ``tests/architecture/test_route_table.py::test_no_schema_property_or_
    parameter_exposes_a_stored_body`` already walks the OpenAPI schema's
    components and parameters for the same names. Repeating it here would give
    Phase 23 two tests to extend. What that walk does not reach is the route
    objects themselves — the path strings, the names in their braces, and the
    model each route binds its request body to — and that is what this asserts.

    ``assembled_routes``, **never** the raw ``routes`` list on the application
    object: ``include_router`` appends one lazy ``_IncludedRouter`` that expands
    on demand, so a naive walk finds the three unversioned routes, no ``/api/v1``
    route at all, and passes vacuously (Broken Window #4). The refused spelling is
    written out in prose nowhere in this file, so the plan's mechanical
    ``grep -c`` criterion for it stays satisfiable — the property is carried by
    the call below, which is the only place it can be enforced anyway.

    Two positive controls, both before the loop reads anything. The route count
    is compared against ``EXPECTED_ROUTES`` — imported, so the number lives in
    one place — and the number of request-body models found is floored at the
    three routes that take one, so a walk that resolved no models cannot report
    an empty offender list.

    **``SANCTIONED_BODY_FIELDS`` is imported for the same reason
    ``FORBIDDEN_FIELD_NAMES`` is.** ``body`` acquired a second meaning in
    Phase 13: prompt-registry's ``body`` is the prompt text an author writes,
    and ledger's is a stored request or response. Both cannot be nameless, so
    the per-field exemptions live beside the walk that first needed them and are
    read here rather than copied — two lists would be two places for the next
    entry to be added to only one, which is the failure this file's header
    already names.
    """
    routes = assembled_routes(app)
    served = sum(len(route.methods) for route in routes)
    assert served == len(EXPECTED_ROUTES), (
        f"{served} operations assembled against {len(EXPECTED_ROUTES)} expected; the walk is "
        "not seeing the table it claims to check"
    )

    offenders: list[str] = []
    body_models = 0
    for route in routes:
        for segment in route.path.strip("/").split("/"):
            name = PATH_PARAMETER.sub(r"\1", segment)
            if name.lower() in FORBIDDEN_FIELD_NAMES:
                offenders.append(f"{route.path} segment {segment!r}")

        model = _request_body_model(route)
        if model is None:
            continue
        body_models += 1
        for field in _field_names(model):
            if f"{model.__name__}.{field}" in SANCTIONED_BODY_FIELDS:
                continue
            if field.lower() in FORBIDDEN_FIELD_NAMES:
                offenders.append(f"{route.path} body {model.__name__}.{field}")

    assert body_models >= 3, (
        f"only {body_models} request-body models resolved; three routes take one, so the "
        "body half of this walk inspected nothing"
    )
    assert offenders == [], f"a route names a stored body: {offenders}"


# ---------------------------------------------------------------------------
# LAYER 2 — the internal Python surface, which is the one actually at risk
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("module", PACKAGE_MODULES, ids=lambda m: m.__name__)
def test_no_public_callable_or_model_in_the_module_names_a_body(module: ModuleType) -> None:
    """No public parameter and no public field in ``prope.call_ledger`` is a body.

    Parametrized over the discovered modules so a failure names the offending
    module rather than reporting a list somebody then has to search.

    The exemptions are all **inputs** — the write-side types a body arrives in and
    the three route handlers whose request-body parameter happens to be called
    ``payload``. AC-10 is about outputs, and the output direction is asserted
    separately in ``test_no_public_callable_returns_a_type_that_names_a_body``
    and ``test_the_read_side_types_name_no_body``, because that half cannot be
    satisfied by growing a list.
    """
    offenders = _body_naming_offenders(module, exempt=True)
    assert offenders == [], (
        f"{module.__name__} exposes a stored body: {offenders}. If one of these is a genuine "
        "write-side or transport name, add it to BODY_NAMING_EXEMPT_TYPES or "
        "BODY_NAMING_EXEMPT_PARAMETERS with its reason and move the asserted size — never "
        "relax this assertion."
    )


@pytest.mark.parametrize("module", PACKAGE_MODULES, ids=lambda m: m.__name__)
def test_no_public_callable_returns_a_type_that_names_a_body(module: ModuleType) -> None:
    """The direction AC-10 is actually about, asserted with **no** exemption list.

    ``get_run_totals`` is a function and not a route, so a body reaching a caller
    through a returned dataclass would satisfy every route-table assertion in this
    repository. There is no hatch here on purpose: a returned type that names a
    body is the failure, not a special case of it.

    The resolution is asserted too. An annotation that could not be resolved is
    reported rather than skipped, because a walk that quietly stopped
    understanding its own annotations is indistinguishable from one that found
    nothing wrong.
    """
    offenders: list[str] = []
    unresolved: list[str] = []
    for _, obj in _public_members(module):
        if not _is_callable(obj):
            continue
        returned, resolved = _return_annotation(obj)
        if not resolved:
            unresolved.append(_origin(obj))
            continue
        for field in _field_names(returned):
            if field.lower() in FORBIDDEN_FIELD_NAMES:
                offenders.append(f"{_origin(obj)} -> {_origin(returned)}.{field}")

    assert unresolved == [], (
        f"{module.__name__}: return annotations that could not be resolved and were therefore "
        f"not checked: {unresolved}. A `from __future__ import annotations` module would make "
        "this walk pass by comparing strings."
    )
    assert offenders == [], f"{module.__name__} returns a stored body: {offenders}"


def test_the_read_side_types_name_no_body() -> None:
    """The four read-side types, named individually because a reviewer reads names.

    All four fall out of the general walk above. They are asserted again here
    because *"a body reaching a caller through a returned dataclass"* is the exact
    failure layer 2 exists to catch, and a named test is what makes that visible
    in a test report rather than implied by the absence of a failure.

    ``RunTotals`` is INT-021's six registered fields and none of them is a body.
    ``EvalUsageRow`` carries **no body field at all, on purpose** — A-055 says no
    ``call_body`` row may exist for a ``source = 'eval'`` record, and there is no
    database constraint behind that rule (``test_eval_no_body_boundary.py``), so
    the strongest thing the seam can do is make an eval body unrepresentable in
    its input type.
    """
    for read_side in (RunTotals, CeilingDecision, WriteResult, EvalUsageRow):
        named = [f for f in _field_names(read_side) if f.lower() in FORBIDDEN_FIELD_NAMES]
        assert named == [], f"{read_side.__name__} names a stored body: {named}"

    assert len(_field_names(RunTotals)) == 6, "INT-021 registers six fields"
    assert not [f for f in _field_names(EvalUsageRow) if "body" in f.lower()], (
        "EvalUsageRow grew a body-shaped field; A-055's last line of defence is that an eval "
        "body is unrepresentable in this type"
    )


def test_the_exemption_lists_are_exactly_what_names_a_body() -> None:
    """The hatches are doing work, and they are doing no more than they claim.

    Both sizes are written out rather than derived, in ``EXPECTED_ROUTES``'
    posture, so growing a list and shrinking one both fail. Then the walk is run
    with **both hatches closed** and its output compared against a literal
    enumeration: every exempted name is proved to be a name that really does
    reach a body, and no exempted entry is allowed to be stale bookkeeping for a
    type that stopped naming one.

    This is what stops the lists swallowing the walk. With
    ``BODY_NAMING_EXEMPT_TYPES`` emptied, the eight strings below become
    offenders in ``test_no_public_callable_or_model_in_the_module_names_a_body``;
    with ``BODY_NAMING_EXEMPT_PARAMETERS`` emptied, the three after them do.
    """
    assert len(BODY_NAMING_EXEMPT_TYPES) == 4, "a fifth type naming a body is a CL-10 question"
    assert len(BODY_NAMING_EXEMPT_PARAMETERS) == 4, "a fifth handler taking `payload` is a change"

    unexempted: set[str] = set()
    for module in PACKAGE_MODULES:
        unexempted.update(_body_naming_offenders(module, exempt=False))

    assert unexempted == {
        "prope.call_ledger.domain.CallBodyDraft.request_body",
        "prope.call_ledger.domain.CallBodyDraft.response_body",
        "prope.call_ledger.domain.CallBodyDraft.byte_size",
        "prope.call_ledger.domain.CallRecordDraft.body",
        "prope.call_ledger.envelope.CallRecordPayload.request_body",
        "prope.call_ledger.envelope.CallRecordPayload.response_body",
        "prope.call_ledger.envelope.CallRecordPayload.byte_size",
        "prope.call_ledger.envelope.CallRecordEnvelope.payload",
        "prope.call_ledger.api.create_price_row(payload)",
        "prope.call_ledger.api.set_spend_ceiling(payload)",
        "prope.call_ledger.api.set_retention(payload)",
        "prope.call_ledger.api.put_observability_content_access(payload)",
    }

    assert {name.split("(")[0] for name in unexempted if "(" in name} == (
        BODY_NAMING_EXEMPT_PARAMETERS
    )
    assert {name.rsplit(".", 1)[0] for name in unexempted if "(" not in name} == (
        BODY_NAMING_EXEMPT_TYPES
    )


def test_the_walk_would_have_found_one() -> None:
    """The positive control the exemption lists are measured against.

    ``CallBodyDraft`` is the write-side input and is expected to name bodies. The
    walk therefore has to exempt it **by name**, and this is the assertion that
    the exemption is covering something real rather than covering a hole in the
    walk.
    """
    fields = _field_names(CallBodyDraft)

    assert "response_body" in fields
    assert "request_body" in fields
    assert set(fields) & FORBIDDEN_FIELD_NAMES, (
        "CallBodyDraft no longer names a body, so the exemption above is stale and the walk "
        "has nothing to prove itself against"
    )


def test_the_internal_walk_inspected_the_package_it_claims_to_cover() -> None:
    """Floors, so a walk that imported nothing cannot report an empty offender list.

    Counted on the definition site rather than on every namespace a name appears
    in, so a re-export does not inflate the figure. These are floors and not
    targets: plans 03-01 through 03-04 added to all three during this phase, and
    the numbers were chosen to sit below the result rather than to describe it.
    """
    callables: set[str] = set()
    models: set[str] = set()
    for module in PACKAGE_MODULES:
        for _, obj in _public_members(module):
            if _is_callable(obj):
                callables.add(_origin(obj))
            elif _is_model(obj):
                models.add(_origin(obj))

    assert len(callables) >= MINIMUM_PUBLIC_CALLABLES, f"only {len(callables)} public callables"
    assert len(models) >= MINIMUM_PUBLIC_MODELS, f"only {len(models)} public models"


# ---------------------------------------------------------------------------
# LAYER 3 — every statement in src/ that names the table, enumerated
# ---------------------------------------------------------------------------


def _callee(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _body_table_sites(tree: ast.AST) -> list[int]:
    """Line numbers where a module names ``ledger.call_body`` in a SQL context.

    Three shapes, and prose is deliberately none of them: a ``text()`` argument
    carrying the name, a Core construct reaching ``models.call_body``, and the
    binding of the ``Table`` object itself. Nine modules under ``src/`` mention
    ``call_body`` in a docstring or a comment — ADR-0018 is discussed where it
    binds — and a grep would report all nine. What matters is which modules can
    *issue a statement against the table*, which is an AST question.
    """
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _callee(node.func) == "text":
            for argument in node.args:
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    if "call_body" in argument.value:
                        lines.add(node.lineno)
        elif isinstance(node, ast.Attribute) and node.attr == "call_body":
            lines.add(node.lineno)
        elif isinstance(node, ast.Name) and node.id == "call_body":
            lines.add(node.lineno)
    return sorted(lines)


def _modules_naming_the_body_table() -> dict[str, list[int]]:
    modules = sorted(SOURCE_ROOT.rglob("*.py"))
    assert modules, f"no modules found under {SOURCE_ROOT}; the walk is looking in the wrong place"

    found: dict[str, list[int]] = {}
    for module in modules:
        sites = _body_table_sites(ast.parse(module.read_text(encoding="utf-8")))
        if sites:
            found[module.relative_to(SOURCE_ROOT).as_posix()] = sites
    return found


def test_only_the_declared_writers_name_the_body_table() -> None:
    """Layer 3: prove the absence by listing what is present, in both directions.

    **The grant matrix is deliberately not the guarantee here.** ``prope_app``
    holds ``SELECT`` on ``ledger.call_body`` because the retention ``DELETE``
    reads a column and D-34's ``ON CONFLICT`` reads one too
    (``0003_ledger_tables.py:246-252``, and
    ``test_prope_app_can_read_a_body_and_that_is_the_point`` below asserts it).
    So the assertion that stands in for a privilege is this: the set of files that
    can issue a statement against the table is exactly the declared set.

    **Both directions fail.** A file that names the table and is not in the map is
    an offender — that is the arrival this test exists to catch. A file in the map
    that no longer names it is stale bookkeeping, and a map describing a file that
    stopped mattering is how the next entry gets waved through.

    The file list is discovered with ``rglob``, never written down, so a module
    added in a later phase is covered on the day it is written.
    """
    found = _modules_naming_the_body_table()

    unexpected = set(found) - set(BODY_TABLE_WRITERS)
    stale = set(BODY_TABLE_WRITERS) - set(found)

    assert unexpected == set(), (
        f"a file names ledger.call_body and is not declared: {sorted(unexpected)}. A third "
        "statement touching the body table is a claim ADR-0018 should be asked about — add an "
        "entry with its reason, do not relax this assertion."
    )
    assert stale == set(), (
        f"declared body-table files that no longer name it: {sorted(stale)}. Remove the entry "
        "in the same change that removed the statement."
    )

    for path, reason in BODY_TABLE_WRITERS.items():
        assert reason.strip(), f"{path} is declared with no reason"


def test_the_body_table_walk_found_statements_to_check() -> None:
    """The matcher matches, and it is looking at the right tree.

    A walk that matched nothing would be green for the same reason a walk over an
    empty directory would be, and the two are indistinguishable from outside.
    ``test_no_sql_interpolation.py``'s instruction applies unchanged: **do not
    raise this floor to make a failure pass** — investigate what left.
    """
    found = _modules_naming_the_body_table()
    sites = sum(len(lines) for lines in found.values())

    assert found, "no file under src/ names ledger.call_body; the matcher stopped matching"
    assert sites >= MINIMUM_BODY_TABLE_SITES, f"only {sites} sites matched under {SOURCE_ROOT}"


def test_the_age_gauge_selects_no_body_column() -> None:
    """The fourth map entry, bounded by an assertion rather than by its reason.

    ``worker.OLDEST_BODY_CREATED_AT`` is the only ``SELECT`` on
    ``ledger.call_body`` anywhere in ``src/``, added with D-43's
    ``oldest_body_age_seconds`` gauge. It reads ``min(created_at)`` — the age of
    the oldest surviving body, which is what ``LedgerRetentionOverdue`` compares
    against a workspace's window — and it must never grow a body column, because
    the moment it does, the statement that measures the data becomes the statement
    that reads it.
    """
    statement = str(prope.worker.OLDEST_BODY_CREATED_AT).lower()

    assert "ledger.call_body" in statement, "the gauge stopped reading the body table"
    assert "min(created_at)" in statement
    for column in ("request_body", "response_body"):
        assert column not in statement, f"the age gauge selects {column}"


COUNT_BODIES = text("SELECT count(*) FROM ledger.call_body")
READ_BODY = text(
    "SELECT request_body, response_body FROM ledger.call_body WHERE call_id = :call_id"
)

BODY_CALL_ID = "cal_01J00000000000000000BODY1"


async def test_prope_app_can_read_a_body_and_that_is_the_point(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    """The uncomfortable half of layer 3, asserted against the live engine.

    ``prope_app`` holds ``SELECT`` on ``ledger.call_body`` and **the ``SELECT`` is
    load-bearing**: the retention ``DELETE ... WHERE expires_at <= $1`` reads a
    column, and every form of ``ON CONFLICT`` requires ``SELECT`` on the columns
    it reads, which is what makes D-34's body upsert legal. Revoking it in the
    name of "no read path" would break the retention job and the idempotent write
    together.

    **If this test starts failing, do not "fix" it.** It failing means somebody
    narrowed a grant those two paths need. Read the comment at
    ``alembic/versions/0003_ledger_tables.py:246-252`` — *"SELECT is required
    alongside DELETE, and is not an oversight … AC-10's no-read-path guarantee is
    a property of the ROUTE TABLE (Phase 3), not of the grant matrix"* — before
    touching anything.

    So the guarantee is the **absence of a reader in ``src/``**, enumerated by the
    test above, and the database is not backing it up. Anybody adding a ``SELECT``
    on ``ledger.call_body`` will be refused by that test and by nothing else.

    The body is seeded through the real write path, and read back through
    ``migrate_engine`` first: without that positive control the ``prope_app`` read
    below would prove that zero rows are readable rather than that a privilege
    exists.
    """
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        result = await write_records(session, [gateway_draft(call_id=BODY_CALL_ID)])
    assert result.bodies_written == 1

    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_BODIES)).scalar_one() == 1

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        row = (await session.execute(READ_BODY, {"call_id": BODY_CALL_ID})).one()

    assert row.request_body == "a request"
    assert row.response_body == "a response"
