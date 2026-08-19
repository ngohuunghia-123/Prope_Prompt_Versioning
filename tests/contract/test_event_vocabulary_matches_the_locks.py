"""AC-6 / PH-06 / ROADMAP SC2 — the registry against the union of five lock files.

property-history's own risk register names the failure this test exists to catch:
*"Eight modules and 30 event types were reconciled here for the first time, and the
reconciliation found real disagreements: five action names, one misfiled event, and
a Success metric naming an event nobody writes. Others may remain."* Its mitigation
is this test: *"AC-6 makes the vocabulary an asserted equality between the registry
and the five lock files rather than a list maintained in six places by hand, so the
next disagreement fails a test instead of surviving to step 6."*

**No list of the 31 action names is committed here, or anywhere under ``tests/`` or
``src/``.** One side of the equality is the migration's seed, read live through
:func:`registered_actions`; the other is parsed from ``docs/modules/*.lock.yml`` at
run time, three ways that must agree with each other before either is compared to
the registry. A fixture of the names would make both sides of the equality the same
artifact — the fixture and the migration would agree, the lock files could drift
out from under both, and this test would stay green regardless.

**If this test goes red**, a lock file's prose changed, or the migration's seed did.
The question is whether the migration should follow the lock file or the lock
file's change was a mistake — do not edit this test to make it pass, and do not
edit a lock file to make the derivation come out right. Either answer is a new
migration or an OQ, never a patch to this file.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.property_history.registry import registered_actions

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULES_DIR = REPO_ROOT / "docs" / "modules"

#: The five modules `property-history.lock.yml` names as writers, in the order its
#: own `inputs[]` block lists them.
WRITING_MODULES: tuple[str, ...] = (
    "prompt-registry",
    "release-control",
    "evaluation",
    "provider-access",
    "access-control",
)

_NAME = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*")
#: `.` `(` `:` `;` or an em dash — the characters that end a comma-separated name
#: list and start prose, in the five paragraphs as they read today.
_TERMINATORS = frozenset({".", "(", ":", ";", "—"})
_COUNT_PREFIX = re.compile(r'^\s*"?\s*(\d+)\s+events\s*[-—]\s*')


def _extract_leading_names(prose: str) -> list[str]:
    """The opening comma-separated run of bare identifiers, and nothing after it.

    A permissive `[a-z_]+_[a-z]+` over the whole paragraph over-extracts —
    `version_id`, `break_glass`, `prompt_grant`, `target_type` and the rest are
    all snake_case words that are not action names — and under-extracts, because
    `retired` carries no underscore at all. This walks the comma-separated items
    instead and stops at the first one that is not a bare identifier followed
    immediately by a terminator or the end of the item.
    """
    names: list[str] = []
    for raw_item in prose.split(","):
        item = raw_item.strip()
        if item.startswith('"'):
            item = item[1:]
        match = _NAME.match(item)
        if match is None:
            break
        name = match.group(0)
        rest = item[match.end() :].lstrip()
        if not rest:
            names.append(name)
            continue
        if rest[0] in _TERMINATORS:
            names.append(name)
            break
        # A phrase, not a name — e.g. "with the prompt_id". The list has ended.
        break
    return names


def _load_lock(module_id: str) -> dict:
    path = MODULES_DIR / f"{module_id}.lock.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _declared_by_writers() -> dict[str, list[str]]:
    """Each writing module's own `outputs[]` entry addressed to property-history."""
    declared: dict[str, list[str]] = {}
    for module_id in WRITING_MODULES:
        lock = _load_lock(module_id)
        entries = [entry for entry in lock["outputs"] if entry["to"] == "property-history"]
        assert len(entries) == 1, (
            f"{module_id}.lock.yml outputs[] names property-history "
            f"{len(entries)} times; expected exactly 1"
        )
        declared[module_id] = _extract_leading_names(entries[0]["what"])
    return declared


def _property_history_int006_inputs() -> list[dict]:
    """property-history's own `inputs[]`, narrowed to the five INT-006 write rows.

    Excludes the sixth entry, `contract_ref: "INT-007"` — the read-side row
    naming prompt-registry, release-control and provider-access again, on the
    read path rather than the write path.
    """
    lock = _load_lock("property-history")
    entries = [entry for entry in lock["inputs"] if "INT-006" in entry["contract_ref"]]
    assert len(entries) == 5, (
        f"property-history.lock.yml inputs[] names {len(entries)} INT-006 entries; "
        "expected exactly 5 (this also excludes the INT-007 read-side row)"
    )
    return entries


def _restated_by_property_history() -> dict[str, list[str]]:
    """The same five lists, as property-history's `inputs[]` restates them."""
    restated: dict[str, list[str]] = {}
    for entry in _property_history_int006_inputs():
        remainder = _COUNT_PREFIX.sub("", entry["what"], count=1)
        restated[entry["from"]] = _extract_leading_names(remainder)
    return restated


def _counts_declared_by_property_history() -> dict[str, int]:
    """The `N events —` count each of the five `inputs[]` entries opens with."""
    counts: dict[str, int] = {}
    for entry in _property_history_int006_inputs():
        match = _COUNT_PREFIX.match(entry["what"])
        assert match is not None, (
            f"property-history.lock.yml inputs[] entry from {entry['from']!r} does not open "
            "with 'N events -'; the count-prefix parser needs updating, not a hardcoded count"
        )
        counts[entry["from"]] = int(match.group(1))
    return counts


def _union(declared: dict[str, list[str]]) -> set[str]:
    union: set[str] = set()
    for names in declared.values():
        union.update(names)
    return union


# --- Assertions, ordered from least to most specific: a vacuous walk fails first,
# --- an extraction bug fails second, and only a real registry/lock disagreement
# --- reaches the last two. ------------------------------------------------------


def test_the_three_derivations_agree_on_which_five_modules_write() -> None:
    """Vacuity guard: a walk that found nothing must fail here, not by comparing
    three empty sets and passing — the shape Phase 4's D-56 refused a tenant
    column to prevent, one layer up."""
    declared = _declared_by_writers()
    restated = _restated_by_property_history()
    counts = _counts_declared_by_property_history()
    assert set(declared) == set(WRITING_MODULES) == set(restated) == set(counts)
    assert all(declared.values())


def test_each_modules_extracted_count_matches_its_declared_count() -> None:
    """The assertion that catches an extraction bug, before anything about the
    registry is even read."""
    declared = _declared_by_writers()
    counts = _counts_declared_by_property_history()
    for module_id in WRITING_MODULES:
        assert len(declared[module_id]) == counts[module_id], (
            f"{module_id}: property-history.lock.yml declares {counts[module_id]} events, "
            f"but {len(declared[module_id])} were extracted from {module_id}.lock.yml's own "
            f"outputs[] paragraph: {declared[module_id]}"
        )


def test_writers_and_property_historys_restatement_are_the_same_list() -> None:
    """Two independent statements of the same list, written by different passes
    on different days, must read as the same ordered list."""
    declared = _declared_by_writers()
    restated = _restated_by_property_history()
    for module_id in WRITING_MODULES:
        assert declared[module_id] == restated[module_id], (
            f"{module_id}: {module_id}.lock.yml says {declared[module_id]}, "
            f"property-history.lock.yml's inputs[] restates it as {restated[module_id]}"
        )


def test_no_name_is_claimed_by_two_modules_and_the_union_has_37_distinct_names() -> None:
    declared = _declared_by_writers()
    seen: dict[str, str] = {}
    for module_id, names in declared.items():
        for name in names:
            assert name not in seen, (
                f"{name!r} is claimed by both {seen.get(name)!r} and {module_id!r}"
            )
            seen[name] = module_id
    union = _union(declared)
    assert len(union) == len(seen)


def test_the_union_totals_39() -> None:
    """The one number this file hardcodes. OQ-027 records the vocabulary count as
    30 in six documents and 31 in five — twice inside one file — with 31 adopted:
    the count the five writing modules' own `outputs[]` paragraphs produce with no
    manual adjustment. Two later migrations moved it: revision 0021 added
    `api_key_scope_set` (32) and revision 0022 added the five invitation events
    (37, ADR-0057). Revision 0021's name never reached a lock file, which is the
    drift this file exists to catch and which 0022's pass repaired. If this goes
    red, read the diff between the derived union and 39 before assuming the
    literal is wrong.

    Revision 0026 moved it again, to 39: `namespace_access_granted` and
    `namespace_access_revoked` (ADR-0061). Both reached a lock file in the same
    change as the migration, which is what revision 0021 failed to do and what
    this assertion exists to catch."""
    union = _union(_declared_by_writers())
    assert len(union) == 39, sorted(union)


@pytest.mark.parametrize(
    "excluded",
    [
        "scope_prompt_id",
        "version_id",
        "previous_version_id",
        "break_glass",
        "set_revision_status",
        "prompt_grant",
        "target_type",
        "target_id",
        "actor_id",
        "suite_version",
    ],
)
def test_column_and_field_names_in_the_prose_are_not_mistaken_for_actions(excluded: str) -> None:
    union = _union(_declared_by_writers())
    assert excluded not in union


def test_retired_is_recovered_despite_carrying_no_underscore() -> None:
    union = _union(_declared_by_writers())
    assert "retired" in union


def test_access_level_changed_is_attributed_to_prompt_registry_not_access_control() -> None:
    """`module_map.md` once filed this action under prompt-registry in error in
    the other direction — and access-control's own paragraph names
    `access_level_changed` by word, without owning it. The extraction must not
    be fooled by the mention."""
    declared = _declared_by_writers()
    assert "access_level_changed" in declared["prompt-registry"]
    assert "access_level_changed" not in declared["access-control"]


async def test_registered_actions_matches_the_union_in_both_directions(
    app_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """`registered_actions()` runs on a plain session — INT-008's declared
    consumer, and the registry carries no tenant column (D-56)."""
    union = _union(_declared_by_writers())
    async with app_sessionmaker() as session:
        registry = await registered_actions(session)
    seeded = {row.action for row in registry}
    extra = seeded - union
    missing = union - seeded
    assert not extra and not missing, (
        f"actions seeded that no lock file declares: {sorted(extra)}; "
        f"actions declared that the seed is missing: {sorted(missing)}"
    )


async def test_every_seeded_action_is_attributed_to_the_module_that_declared_it(
    app_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """The misfiled-event check. `module_map.md` really did list `access_granted`
    under prompt-registry, and access-control's own paragraph names
    `access_level_changed` — an action it does not own — so this is the concrete
    case the assertion is written against."""
    declared = _declared_by_writers()
    async with app_sessionmaker() as session:
        registry = await registered_actions(session)
    for module_id in WRITING_MODULES:
        attributed = {row.action for row in registry if row.writing_module == module_id}
        assert attributed == set(declared[module_id]), (
            f"{module_id}: registry attributes {sorted(attributed)}, "
            f"lock files declare {sorted(declared[module_id])}"
        )
