"""The Chung catalogue: read-only datasets that ship inside the image.

**Why files rather than rows.** ``evaluation`` is under row-level security —
deny-by-default, ``SET LOCAL app.workspace_id``, and a row belonging to no
workspace is a row nobody can read (ADR-0035, ADR-0045). A catalogue that must
be byte-identical in every workspace therefore cannot live in Postgres. The two
alternatives were a per-workspace copy seeded at bootstrap, which drifts the
moment one set is corrected and makes *"passes the safety set"* mean different
things in two installs, and an exception in the tenant policy for one table,
which is the property the architecture treats as non-negotiable. So the
catalogue ships as reviewed files that change through a pull request, the same
posture ``chat_orchestrator.knowledge`` takes.

**Validation happens at import, not at attach.** :func:`load_catalogue` runs
every case through the same :func:`compile_assertions` the API uses, so a regex
that does not compile or an assertion type the declared modality does not allow
fails the process at start-up. A malformed set that only failed when somebody
ticked it would be a deployment that looks healthy and breaks for one person.

**The fingerprint covers the cases and nothing else.** Renaming a set or fixing
its description does not change what it measures, and must not force a new
suite version onto every prompt that attached it. Bumping ``version`` in the
YAML *does* mint a new id, which is a different dataset entirely — a prompt
attached to ``@1`` stays on ``@1`` until somebody re-ticks, so a shipped fix
never silently changes what a prompt is measured against between releases.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, Final

import yaml

from prope.evaluation.assertions import compile_assertions
from prope.evaluation.domain import (
    MAX_CASES_PER_SUITE,
    AssertionSpec,
    AssertionType,
    CaseDraft,
    DatasetKind,
    DatasetSpec,
    OutputModality,
    fingerprint_cases,
)

__all__ = [
    "BUILTIN_PREFIX",
    "CATALOGUE_DIRECTORY",
    "CatalogueInvalid",
    "list_builtin_datasets",
    "load_catalogue",
    "resolve_builtin",
]

CATALOGUE_DIRECTORY: Final = Path(__file__).parent / "common_datasets"

#: Every builtin id starts with this. ``dataset_attachment``'s shape CHECK
#: admits ``builtin:<slug>@<version>`` and ``dst_<ULID>`` and nothing else, so
#: this prefix is what tells the two apart without a lookup.
BUILTIN_PREFIX: Final = "builtin:"


class CatalogueInvalid(Exception):  # noqa: N818
    """A shipped dataset file is malformed. Raised at import, never at runtime."""

    def __init__(self, path: Path, detail: str) -> None:
        super().__init__(f"{path.name}: {detail}")
        self.path = path
        self.detail = detail


def _require(document: dict[str, Any], key: str, path: Path) -> Any:
    if key not in document:
        raise CatalogueInvalid(path, f"missing required key {key!r}")
    return document[key]


def _case_draft(raw: Any, path: Path, ordinal: int) -> CaseDraft:
    if not isinstance(raw, dict):
        raise CatalogueInvalid(path, f"case {ordinal} is not a mapping")

    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise CatalogueInvalid(path, f"case {ordinal} has no name")

    messages = raw.get("input_messages")
    if not isinstance(messages, list) or not messages:
        raise CatalogueInvalid(path, f"case {ordinal} has no input_messages")
    for message in messages:
        if not isinstance(message, dict) or "role" not in message or "content" not in message:
            raise CatalogueInvalid(
                path, f"case {ordinal} has a message without both a role and a content"
            )

    raw_assertions = raw.get("assertions") or []
    if not isinstance(raw_assertions, list):
        raise CatalogueInvalid(path, f"case {ordinal} has a non-list assertions block")

    specs: list[AssertionSpec] = []
    for entry in raw_assertions:
        if not isinstance(entry, dict) or "type" not in entry:
            raise CatalogueInvalid(path, f"case {ordinal} has an assertion with no type")
        try:
            assertion_type = AssertionType(entry["type"])
        except ValueError as error:
            raise CatalogueInvalid(
                path, f"case {ordinal} names an unknown assertion type {entry['type']!r}"
            ) from error
        specs.append(AssertionSpec(type=assertion_type, value=entry.get("value")))

    return CaseDraft(
        name=name,
        input_messages=tuple(messages),
        input_variables=dict(raw.get("input_variables") or {}),
        assertions=tuple(specs),
    )


def _dataset_spec(path: Path) -> DatasetSpec:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise CatalogueInvalid(path, f"is not valid YAML: {error}") from error

    if not isinstance(document, dict):
        raise CatalogueInvalid(path, "the top level of a dataset file is a mapping")

    slug = _require(document, "slug", path)
    if not isinstance(slug, str) or slug != path.stem:
        raise CatalogueInvalid(
            path, f"slug {slug!r} does not match the file name — the id embeds the slug"
        )

    version = _require(document, "version", path)
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise CatalogueInvalid(path, "version is a positive integer")

    try:
        modality = OutputModality(_require(document, "output_modality", path))
    except ValueError as error:
        raise CatalogueInvalid(path, f"unknown output_modality: {error}") from error

    try:
        kind = DatasetKind(_require(document, "kind", path))
    except ValueError as error:
        raise CatalogueInvalid(path, f"unknown kind: {error}") from error

    raw_cases = _require(document, "cases", path)
    if not isinstance(raw_cases, list) or not raw_cases:
        raise CatalogueInvalid(path, "a dataset with no cases measures nothing")
    if len(raw_cases) > MAX_CASES_PER_SUITE:
        # Caught here rather than at materialisation, where it would be a
        # runtime refusal on a set that was already shipped and already ticked.
        raise CatalogueInvalid(
            path, f"{len(raw_cases)} cases exceeds the {MAX_CASES_PER_SUITE} a suite holds"
        )

    cases = tuple(
        _case_draft(raw, path, ordinal) for ordinal, raw in enumerate(raw_cases, start=1)
    )

    # The same gate the API applies to a hand-written suite. A shipped regex
    # that does not compile must fail the process, not the first person to tick
    # the set.
    for ordinal, case in enumerate(cases, start=1):
        compile_assertions(case.assertions, modality, ordinal)

    applicability = document.get("applicability")
    if applicability is not None and not isinstance(applicability, str):
        raise CatalogueInvalid(path, "applicability is a string or absent")

    return DatasetSpec(
        id=f"{BUILTIN_PREFIX}{slug}@{version}",
        name=str(_require(document, "name", path)),
        description=str(document.get("description") or ""),
        kind=kind,
        output_modality=modality,
        cases=cases,
        fingerprint=fingerprint_cases(cases),
        applicability=applicability.strip() if isinstance(applicability, str) else None,
        # Every builtin sits in the Chung group: it applies workspace-wide and
        # belongs to no one domain area.
        folder="",
        read_only=True,
    )


@lru_cache(maxsize=1)
def load_catalogue() -> tuple[DatasetSpec, ...]:
    """Every shipped dataset, in file-name order, validated.

    Cached for the process lifetime — the files cannot change under a running
    container, and re-reading five files per request to list a sidebar is work
    nobody asked for.
    """
    specs = [_dataset_spec(path) for path in sorted(CATALOGUE_DIRECTORY.glob("*.yml"))]

    seen: dict[str, Path] = {}
    for spec, path in zip(specs, sorted(CATALOGUE_DIRECTORY.glob("*.yml")), strict=True):
        if spec.id in seen:
            raise CatalogueInvalid(path, f"{spec.id} is already defined by {seen[spec.id].name}")
        seen[spec.id] = path

    return tuple(specs)


def list_builtin_datasets() -> tuple[DatasetSpec, ...]:
    return load_catalogue()


#: **Eager, and that is the point.** ``load_catalogue`` is cached, so leaving it
#: lazy would mean a shipped regex that does not compile surfaces as a 500 on
#: whichever request happened to open the dataset tree first — a container that
#: starts, reports healthy, and is broken for one person. Importing this module
#: is enough to prove every shipped set parses and every assertion compiles.
load_catalogue()


def resolve_builtin(dataset_id: str) -> DatasetSpec | None:
    """The shipped dataset with this id, or ``None``.

    ``None`` rather than a raise: an attachment can outlive the catalogue entry
    it points at, because bumping a set's ``version`` retires the old id and a
    prompt attached to it keeps its row. The eval workspace renders such an
    attachment as unresolved rather than 500-ing on it, and unticking is how it
    is cleared.
    """
    if not dataset_id.startswith(BUILTIN_PREFIX):
        return None
    for spec in load_catalogue():
        if spec.id == dataset_id:
            return spec
    return None
