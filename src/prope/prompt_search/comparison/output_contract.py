"""Stage 2b — the declared output contract, as a descriptor compared in code.

The output contract lives in ``<output_format>`` as prose. Comparing two prose
blocks by embedding is the whole-document mistake one level down, so instead:
**extract a normalized descriptor from each block independently, then compare the
descriptors in code.** Three quotable findings — *confidence is missing*,
*`escalate` was dropped*, *B never says "only JSON"* — instead of "these look
fairly similar".

Two properties the extractor must keep, and both are load-bearing:

**It must be able to answer ``unspecified``.** That is what feeds the
undeclared-means-breaking rule, exactly as `UsageProfile` carries ``undeclared``
as a real value on every axis. An extractor that always fills in a plausible
value quietly destroys the rule, and nothing downstream can tell that it has.

**It runs per revision, never per pair.** The descriptor is a property of one
revision, so it is cached by ``version_id`` and a comparison costs one call for
the incoming body rather than one per candidate. Per-pair extraction would also
bias the answer: an extractor shown both blocks at once is drawn toward finding
them alike — the same anchoring problem as judging N pairs holistically.

**Why this exists at all, given stage 2c arrives free**: it is a cheap prediction
that can cancel an expensive confirmation. If A returns bare JSON and B returns
markdown prose, that is known before a differential run spends 2N dispatches
discovering it. 2b's value is its position in the pipeline, not its findings.

The direction rule here is the **mirror** of 2a's, and reversing it would be a
silent bug: for *inputs* B must require a subset of A's variables; for *output
keys and enum values* B must produce a **superset** of A's — a consumer reads the
keys it expects and ignores extras, and dropping one makes it throw.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from prope.canonical_prompt import blocks_of
from prope.prompt_search.comparison.domain import Finding, Severity

__all__ = [
    "AXIS",
    "CARDINALITIES",
    "MODALITIES",
    "OutputDescriptor",
    "UNSPECIFIED",
    "WHOLE_TEXT",
    "compare_output_contracts",
    "declared_output_text",
    "produces_superset_of",
]

AXIS = "output_contract"

#: The value that means *the prompt does not say*. A string rather than ``None``
#: so it survives JSONB round-tripping unchanged and so a missing key and a
#: declared-nothing are never the same thing on the wire.
UNSPECIFIED = "unspecified"

#: The ``source_block`` for a contract read out of an unstructured body.
#:
#: The import screen holds text nobody has converted yet, so *"there are no
#: canonical blocks"* is the normal case there rather than the broken one, and
#: refusing to read it means the whole output-contract rung sits idle for every
#: paste — which is what it did. Reading it is worth doing and worth labelling:
#: a contract inferred from prose is weaker evidence than one lifted out of
#: ``<output_format>``, and :func:`compare_output_contracts` says so on the
#: sheet rather than letting the two look alike.
WHOLE_TEXT = "whole_text"

#: What a machine consumer has to parse differently. Deliberately coarse: the
#: question is "does the caller's parser still work", and a parser cares about
#: JSON-vs-prose, not about whether the prose is friendly.
MODALITIES = frozenset({"json", "xml", "markdown", "csv", "code", "text", UNSPECIFIED})

#: One object, or many. A consumer that indexes ``[0]`` breaks on a single
#: object and a consumer reading ``.decision`` breaks on a list.
CARDINALITIES = frozenset({"single", "list", UNSPECIFIED})

#: How long the answer is meant to be. Never a hard finding — length changes the
#: output without breaking the flow — but it is the axis that moves cost, so it
#: is worth carrying.
LENGTHS = frozenset({"brief", "detailed", UNSPECIFIED})


def produces_superset_of(candidate: frozenset[str], released: frozenset[str]) -> bool:
    """Does ``candidate`` still emit everything a consumer of ``released`` reads?

    The mirror of ``input_contract.requires_subset_of``, named for the same
    reason: these two rules point in opposite directions and the only defence
    against writing one where the other belongs is that neither is ever spelled
    inline.
    """
    return candidate >= released


@dataclass(frozen=True, slots=True)
class OutputDescriptor:
    """A normalized statement of what one revision promises to emit.

    **Only what a machine consumer trips on.** Tone, ordering, verbosity and
    style are deliberately absent: they change the output without breaking the
    flow, which makes them the differential run's business and not this one's.
    """

    modality: str = UNSPECIFIED
    #: Top-level keys the output carries, when the modality is structured.
    keys: tuple[str, ...] = ()
    #: Closed value sets, per key. ``{"decision": ("approve", "reject")}``.
    enums: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: Does the prompt forbid preamble and code fences — "chỉ JSON", "only the
    #: JSON object". Its own field because it is the most common real-world
    #: break, and because "return JSON" and "return only JSON" are different
    #: contracts that every summary flattens together.
    bare: str = UNSPECIFIED
    cardinality: str = UNSPECIFIED
    #: ``vi``, ``en``, ``input`` (mirror the caller), or unspecified.
    language: str = UNSPECIFIED
    length: str = UNSPECIFIED
    #: Which canonical block the contract was read from — ``output_format``, or
    #: ``instructions`` when the author stated it there instead (OQ-f). A
    #: contract stated only in ``instructions`` is weaker evidence and this is
    #: what lets a reader see that.
    source_block: str = UNSPECIFIED

    @property
    def is_empty(self) -> bool:
        """True when the revision declared nothing this stage can compare.

        Not the same as *not extracted*: this descriptor exists and says the
        prompt is silent, which is a finding. A revision with no descriptor at
        all is `None` at the call site and produces a coverage finding instead.
        """
        return (
            self.modality == UNSPECIFIED
            and not self.keys
            and self.bare == UNSPECIFIED
            and self.cardinality == UNSPECIFIED
        )

    def to_dict(self) -> dict:
        return {
            "modality": self.modality,
            "keys": list(self.keys),
            "enums": {key: list(values) for key, values in self.enums.items()},
            "bare": self.bare,
            "cardinality": self.cardinality,
            "language": self.language,
            "length": self.length,
            "source_block": self.source_block,
        }

    @classmethod
    def from_dict(cls, data: Any) -> OutputDescriptor | None:
        """A stored descriptor, or ``None`` for anything unreadable.

        Tolerant on purpose. This reads a JSONB column written by an earlier
        version of this code, and a shape change must degrade to *not
        established* rather than to a 500 on the import screen.
        """
        if not isinstance(data, dict):
            return None
        enums_raw = data.get("enums") or {}
        enums = {
            str(key): tuple(str(value) for value in values)
            for key, values in enums_raw.items()
            if isinstance(values, (list, tuple))
        }
        return cls(
            modality=_one_of(data.get("modality"), MODALITIES),
            keys=tuple(str(key) for key in (data.get("keys") or []) if str(key).strip()),
            enums=enums,
            bare=_tristate(data.get("bare")),
            cardinality=_one_of(data.get("cardinality"), CARDINALITIES),
            language=str(data.get("language") or UNSPECIFIED),
            length=_one_of(data.get("length"), LENGTHS),
            source_block=str(data.get("source_block") or UNSPECIFIED),
        )


def _one_of(value: Any, allowed: frozenset[str]) -> str:
    text = str(value or "").strip().lower()
    return text if text in allowed else UNSPECIFIED


def _tristate(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in {"yes", "no", UNSPECIFIED} else UNSPECIFIED


def declared_output_text(body: str, *, allow_prose: bool = False) -> tuple[str, str]:
    """The text the descriptor is extracted from, and which block it came from.

    ``<output_format>`` when there is one. Otherwise ``<instructions>``, because
    real prompts state the output contract there and refusing to read it would
    mean reporting *unspecified* for prompts that specify perfectly well — an
    answer that is wrong in the direction of the hard findings (OQ-f).

    **``allow_prose`` is what the import screen passes, and it is a deliberate
    reversal.** Without it a body that is not canonical XML yields
    ``("", UNSPECIFIED)``, and the reasoning was that guessing an output
    contract out of unstructured prose is the fuzzy step this stage exists to
    avoid. Measured against the running system that reasoning cost more than it
    saved: the duplicate check runs *before* conversion, so every pasted prompt
    took that branch, the incoming descriptor was always ``None``, and stage 2b
    reported *not established* on every import it has ever run — a rung that
    cannot fire is not a strict rung, it is an absent one. With the flag the
    whole body is handed to the extractor under :data:`WHOLE_TEXT`, which is
    labelled as the weaker evidence it is rather than passed off as a declared
    block. The extractor keeps its own guard: it may still answer *unspecified*,
    and on a prompt that genuinely says nothing about its output it should.
    """
    blocks = blocks_of(body)
    declared = blocks.get("output_format", "").strip() if blocks else ""
    if declared:
        return declared, "output_format"
    instructions = blocks.get("instructions", "").strip() if blocks else ""
    if instructions:
        return instructions, "instructions"
    prose = body.strip()
    if allow_prose and prose:
        return prose, WHOLE_TEXT
    return "", UNSPECIFIED


def _keys_findings(candidate: OutputDescriptor, released: OutputDescriptor) -> list[Finding]:
    if not released.keys:
        return []
    missing = tuple(sorted(frozenset(released.keys) - frozenset(candidate.keys)))
    extra = tuple(sorted(frozenset(candidate.keys) - frozenset(released.keys)))
    found: list[Finding] = []
    if missing and not produces_superset_of(frozenset(candidate.keys), frozenset(released.keys)):
        found.append(
            Finding(
                code="similar.output_contract.keys_missing",
                severity=Severity.HARD,
                axis=AXIS,
                params={"keys": list(missing)},
            )
        )
    if extra:
        found.append(
            Finding(
                code="similar.output_contract.keys_added",
                severity=Severity.SOFT,
                axis=AXIS,
                params={"keys": list(extra)},
            )
        )
    return found


def _enum_findings(candidate: OutputDescriptor, released: OutputDescriptor) -> list[Finding]:
    found: list[Finding] = []
    for key, released_values in sorted(released.enums.items()):
        candidate_values = frozenset(candidate.enums.get(key, ()))
        if not candidate_values:
            # The key exists but its value set is no longer declared. Undeclared
            # is not compatible — see the module docstring.
            found.append(
                Finding(
                    code="similar.output_contract.enum_undeclared",
                    severity=Severity.HARD,
                    axis=AXIS,
                    params={"key": key, "values": list(released_values)},
                )
            )
            continue
        dropped = tuple(sorted(frozenset(released_values) - candidate_values))
        added = tuple(sorted(candidate_values - frozenset(released_values)))
        if dropped:
            found.append(
                Finding(
                    code="similar.output_contract.enum_dropped",
                    severity=Severity.HARD,
                    axis=AXIS,
                    params={"key": key, "values": list(dropped)},
                )
            )
        if added:
            # Soft rather than hard, and it is a close call: a consumer with an
            # exhaustive switch breaks on a value it has never seen. It stays
            # soft because a consumer with a default branch does not, and the
            # reviewer is the one who knows which they wrote.
            found.append(
                Finding(
                    code="similar.output_contract.enum_added",
                    severity=Severity.SOFT,
                    axis=AXIS,
                    params={"key": key, "values": list(added)},
                )
            )
    return found


def compare_output_contracts(
    *,
    candidate: OutputDescriptor | None,
    released: OutputDescriptor | None,
) -> tuple[Finding, ...]:
    """Two descriptors, related. Hard findings first, then soft, then info.

    ``candidate`` is the incoming prompt's descriptor (B), ``released`` the
    stored one's (A). ``None`` on either side means *never extracted*, which
    produces a coverage finding and no verdict: not established is not
    compatible, but it is not a caller break either, and reporting it as one
    would make every unindexed candidate look dangerous.
    """
    if candidate is None or released is None:
        return (
            Finding(
                code="similar.output_contract.not_established",
                severity=Severity.SOFT,
                axis=AXIS,
                params={
                    "candidate_known": candidate is not None,
                    "released_known": released is not None,
                },
            ),
        )

    found: list[Finding] = []

    if released.modality != UNSPECIFIED:
        if candidate.modality == UNSPECIFIED:
            found.append(
                Finding(
                    code="similar.output_contract.modality_undeclared",
                    severity=Severity.HARD,
                    axis=AXIS,
                    params={"released": released.modality},
                )
            )
        elif candidate.modality != released.modality:
            found.append(
                Finding(
                    code="similar.output_contract.modality_changed",
                    severity=Severity.HARD,
                    axis=AXIS,
                    params={"released": released.modality, "candidate": candidate.modality},
                )
            )

    found.extend(_keys_findings(candidate, released))
    found.extend(_enum_findings(candidate, released))

    if released.bare == "yes" and candidate.bare != "yes":
        # "Trả về JSON" and "chỉ trả về JSON" are different contracts. A
        # candidate that stopped saying *only* may wrap its answer in a fence,
        # and the consumer's `json.loads` is what finds out.
        found.append(
            Finding(
                code="similar.output_contract.bare_relaxed",
                severity=Severity.HARD,
                axis=AXIS,
                params={"candidate": candidate.bare},
            )
        )

    if (
        released.cardinality != UNSPECIFIED
        and candidate.cardinality != UNSPECIFIED
        and candidate.cardinality != released.cardinality
    ):
        found.append(
            Finding(
                code="similar.output_contract.cardinality_changed",
                severity=Severity.HARD,
                axis=AXIS,
                params={"released": released.cardinality, "candidate": candidate.cardinality},
            )
        )

    if (
        released.language != UNSPECIFIED
        and candidate.language != UNSPECIFIED
        and candidate.language != released.language
    ):
        # Soft, and it is what `variant` is made of: the job is the same and the
        # published interface is not. ADR-0053 may yet argue for a firmer rule
        # (OQ-a case 3); until it does, a human weighs it.
        found.append(
            Finding(
                code="similar.output_contract.language_changed",
                severity=Severity.SOFT,
                axis=AXIS,
                params={"released": released.language, "candidate": candidate.language},
            )
        )

    if (
        released.length != UNSPECIFIED
        and candidate.length != UNSPECIFIED
        and candidate.length != released.length
    ):
        found.append(
            Finding(
                code="similar.output_contract.length_changed",
                severity=Severity.SOFT,
                axis=AXIS,
                params={"released": released.length, "candidate": candidate.length},
            )
        )

    if not found:
        found.append(
            Finding(
                code="similar.output_contract.compatible",
                severity=Severity.INFO,
                axis=AXIS,
                params={"modality": released.modality},
            )
        )

    sources = (released.source_block, candidate.source_block)
    if UNSPECIFIED not in sources and WHOLE_TEXT in sources:
        # Weakest of the three, and the one the import screen produces every
        # time: nobody wrote this contract in a block, a model read it out of
        # the running text. Recorded and not penalised, for the same reason as
        # the line below — but under its own code, because *"stated in the task
        # text"* and *"inferred from unstructured prose"* are different claims
        # and a reader weighing a hard finding needs to know which one they have.
        found.append(
            Finding(
                code="similar.output_contract.inferred_from_prose",
                severity=Severity.INFO,
                axis=AXIS,
                params={"released": released.source_block, "candidate": candidate.source_block},
            )
        )
    elif UNSPECIFIED not in sources and "instructions" in sources:
        # Recorded, not penalised. A contract stated only in `<instructions>` is
        # weaker evidence than one in `<output_format>`, and a reader comparing
        # two descriptors deserves to know that one of them was inferred from
        # the task text.
        found.append(
            Finding(
                code="similar.output_contract.declared_in_instructions",
                severity=Severity.INFO,
                axis=AXIS,
                params={
                    "released": released.source_block,
                    "candidate": candidate.source_block,
                },
            )
        )

    return tuple(found)
