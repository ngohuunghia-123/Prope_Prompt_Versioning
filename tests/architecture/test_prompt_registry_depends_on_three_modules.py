"""`dependencies: [access-control, property-history, provider-access, call-ledger, prompt-search]` as a checked property.

`docs/modules/prompt-registry.lock.yml` declares the module dependencies and
names four forbidden edges. **Three of the four still run the other way**:
gateway, evaluation and release-control each call this module and it never calls
back.

**The fourth moved, and ADR-0055 is the record of it.** call-ledger is still a
sink and still gains no outbound edge; what changed is that this module now
*calls into* it, through `seams` alone, for one read — a prompt's call metadata
behind `prompt.read`. ADR-0018's rule is about `ledger.call_body` and is
untouched; that ADR says of the rest, in as many words, *"metadata is
unaffected ... it has readers"*. The reader lives here rather than there because
call-ledger cannot check a permission, and a workspace-wide version of the read
would name a private prompt's id — the disclosure BR-01 closes as not-found.
`test_call_ledger_is_reached_only_through_its_seam_module` is what keeps the new
edge the size it was argued at.

**prompt-search is the same shape again.** A saved revision publishes one
message asking to be indexed, through `seams` alone, after its transaction has
committed and without the power to fail it. The direction that matters is
unchanged: prompt-search reads prompts and revisions from here, and this module
learns nothing back from it — the job's outcome is a row in `search`, never a
value this route waits for.
`test_prompt_search_is_reached_only_through_its_seam_module` bounds it.

Two of the three remaining are worth stating on their own because they are the
ones somebody would write by accident:

*release-control.* The released pointer moves by an INBOUND command (INT-012,
INT-013, INT-014). A ``from prope.release_control import ...`` here would close
the cycle A-041 and ADR-0001 exist to break, and it would do it while looking
like a convenience — *"just check the release record before setting the
pointer"*. There is nothing to check: the constraint is the check.

*evaluation.* The registry does not know what a pass is. Run results are read by
release-control (A-042) and never surfaced here.

FastAPI is permitted: this module mounts eleven routes across eight paths.
"""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "prope" / "prompt_registry"

ALLOWED_PROPE_IMPORTS = frozenset(
    {
        "prope.access_control",
        # ADR-0055, and **only** through `seams`. See `CALL_LEDGER_SURFACE` below,
        # which is what stops this entry becoming a licence to import the module.
        "prope.call_ledger.seams",
        # Module-neutral canonical XML contract shared with prompt-conversion.
        "prope.canonical_prompt",
        "prope.db",
        "prope.dependencies",
        "prope.errors",
        "prope.observability",
        # The sibling of `prope.canonical_prompt` above, and an omission from the
        # move rather than a widening. ADR-0011's two rules — `{{variable}}`
        # substitution and the revision body as the only system message — lived
        # in `prope.gateway.templating` and `prope.gateway.composition` until the
        # playground needed them, and importing them from THERE is the forbidden
        # edge this file's `FORBIDDEN_MODULES` names first. They moved to a
        # module-neutral file with no `prope` imports of its own precisely so
        # this entry could exist; evaluation, prompt-readiness and
        # prompt-improvement have carried it since. The alternative is a second
        # copy of the PLACEHOLDER regex, which is a second definition of what a
        # variable is, in the module that owns what a revision IS.
        "prope.prompt_composition",
        # ADR-0055's shape a second time, and **only** through `seams`. See
        # `PROMPT_SEARCH_SURFACE` below. A saved revision asks to be indexed so
        # the duplicate check can see it; the ask is a message published after
        # the transaction, it cannot fail the save, and prompt-search still
        # calls into this module and not the reverse for everything it reads.
        "prope.prompt_search.seams",
        "prope.prompt_registry",
        "prope.property_history",
        "prope.provider_access",
        "prope.session_auth",
    }
)

FORBIDDEN_MODULES = (
    "prope.gateway",
    "prope.evaluation",
    "prope.release_control",
)

#: The **one** thing this module may take from call-ledger, named rather than
#: bounded by a prefix.
#:
#: ADR-0055 adds an inbound edge to call-ledger for one read — a prompt's call
#: metadata, behind `prompt.read`. Allowing `prope.call_ledger.seams` alone is
#: what keeps that edge the size it was argued at: `prope.call_ledger.writer`,
#: `.enqueue`, `.pricing` and `.retention` are the write path, and an import of
#: any of them from here would be this module reaching into another's internals
#: with a test that had stopped looking.
#:
#: **It reached all three of the middle ones until 2026-08-25.** `trial.py` held
#: `from prope.call_ledger.enqueue import enqueue`, `.pricing` and `.domain`, and
#: this assertion was red for it. The playground turn is a real write and stays
#: one; what changed is that it goes through `record_playground_call` and
#: `quote_playground_cost`, which fix `source = 'playground'` and `streaming` in
#: the module that owns the column. The narrower thing is not the fewer imports
#: — it is that a session-authenticated screen can no longer assemble a
#: `CallRecordDraft` with `Source.GATEWAY` on it.
CALL_LEDGER_SURFACE = "prope.call_ledger.seams"

#: The **one** thing this module may take from prompt-search, on the same terms.
#:
#: A revision that is saved and never indexed is invisible to the duplicate check
#: on the import screen, which is the feature that check exists for. The ask is
#: one function — `enqueue_index_job` — and allowing the whole module would put
#: `repository`, `worker` and `agent` in reach: the registry would then be able
#: to write index rows and call an embedding provider directly, which is A-043's
#: line (`test_no_module_reaches_the_upstream_http_client` below is the other
#: half of the same rule).
PROMPT_SEARCH_SURFACE = "prope.prompt_search.seams"

VIOLATION = (
    "prompt-registry declares five module dependencies. Three edges run the other way: "
    "gateway, evaluation and release-control all call this module and it never calls back "
    "(A-041, ADR-0001 — the released pointer moves by an inbound command). call-ledger is "
    "INBOUND ONLY and only through `seams` (ADR-0055): that module is a sink and gains no "
    "outbound edge, and its body read path stays closed under ADR-0018. prompt-search is "
    "reached through `seams` alone and for one act — enqueue an indexing job, after the "
    "transaction, soft — while everything it reads it still reads from here."
)


def test_call_ledger_is_reached_only_through_its_seam_module() -> None:
    """ADR-0055's edge, bounded to the surface it was argued at.

    The allow-list above is a set of prefixes, so `prope.call_ledger.seams` also
    permits nothing else — but a later reader "tidying" it to `prope.call_ledger`
    would widen the edge to the whole module, including the write path, and every
    other assertion in this file would still pass. This is the one that would not.
    """
    imported = {name for module in _package_modules() for _, name in _imported_modules(module)}
    reached = sorted(
        name
        for name in imported
        if name.split(".")[0] == "prope"
        and name.startswith("prope.call_ledger")
        and name != CALL_LEDGER_SURFACE
        and not name.startswith(f"{CALL_LEDGER_SURFACE}.")
    )

    assert reached == [], (
        f"{reached} — ADR-0055 opens exactly one door into call-ledger, and it is "
        f"{CALL_LEDGER_SURFACE}. The write PATH is not part of that decision: "
        "`writer`, `enqueue` and `pricing` stay unreachable from here, and the one "
        "write this module makes — a playground turn — goes through a named act on "
        "the seam that fixes `source` where the column lives."
    )


def test_prompt_search_is_reached_only_through_its_seam_module() -> None:
    """The auto-index edge, bounded the same way call-ledger's is.

    `prope.prompt_search.repository` would let this module write index rows
    itself, and `prope.prompt_search.agent` would let it embed — which is an
    upstream call at save time, the thing ADR-0048 rejected and
    `test_no_module_reaches_the_upstream_http_client` asserts the absence of.
    Widening the allow-list entry to `prope.prompt_search` would permit both and
    every other assertion in this file would still pass.
    """
    imported = {name for module in _package_modules() for _, name in _imported_modules(module)}
    reached = sorted(
        name
        for name in imported
        if name.split(".")[0] == "prope"
        and name.startswith("prope.prompt_search")
        and name != PROMPT_SEARCH_SURFACE
        and not name.startswith(f"{PROMPT_SEARCH_SURFACE}.")
    )

    assert reached == [], (
        f"{reached} — the registry asks prompt-search for one thing, through "
        f"{PROMPT_SEARCH_SURFACE}: enqueue an indexing job. Indexing itself, and "
        "the embedding provider behind it, stay on the other side of that door."
    )


def _imported_modules(module: Path) -> list[tuple[int, str]]:
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    imported: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            name = "prope.prompt_registry" if node.level else (node.module or "")
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
    found = _forbidden_prope_imports(module)
    assert not found, f"{module.name}: {found} — {VIOLATION}"


def test_the_three_forbidden_modules_are_imported_at_no_depth() -> None:
    """Stated separately from the allow-list so the failure names the rule
    rather than only the missing entry."""
    imported = {name for module in _package_modules() for _, name in _imported_modules(module)}

    reached = [
        name for name in imported for forbidden in FORBIDDEN_MODULES if name.startswith(forbidden)
    ]
    assert reached == [], f"{sorted(reached)} — {VIOLATION}"


def test_no_module_reaches_the_upstream_http_client() -> None:
    """A-043 and this module's ``external_services: []``.

    **No prompt body leaves the host at save time.** Every upstream call in the
    system goes through provider-access, and an ``httpx`` import here would be
    the first line of the LLM enrichment ADR-0048 rejected — which would have
    sent every body upstream on every save, including drafts and retired prompts
    nobody intended to run.
    """
    imported = {name for module in _package_modules() for _, name in _imported_modules(module)}

    assert not [name for name in imported if name.split(".")[0] in {"httpx", "openai", "requests"}]


def test_the_diff_uses_the_standard_library_and_nothing_else() -> None:
    """A-015's diff is ``difflib``, named in the lock as a library choice.

    Asserted because the alternative — a diff library with a nicer API — would
    also have its own ``autojunk``-shaped heuristics, undeclared, on the one
    screen a reviewer approves from.
    """
    imported = {name for _, name in _imported_modules(PACKAGE / "diff.py")}

    assert "difflib" in imported
    assert not [name for name in imported if name.split(".")[0] == "prope"] or imported & {
        "prope.prompt_registry.domain"
    }


def test_the_walk_found_modules_and_imports_to_inspect() -> None:
    modules = _package_modules()

    assert len(modules) >= 10, modules
    assert sum(len(_imported_modules(module)) for module in modules) >= 30


def test_the_walk_refuses_a_module_that_reaches_another_bounded_context(tmp_path: Path) -> None:
    """The guard is known to have teeth, proven on a file written here."""
    tempting = tmp_path / "check_the_release_first.py"
    tempting.write_text(
        "from prope.release_control.seams import get_release\n"
        "from prope.db.session import workspace_transaction\n",
        encoding="utf-8",
    )

    assert _forbidden_prope_imports(tempting) == [(1, "prope.release_control.seams")]
