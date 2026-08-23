"""Which shipped red-team sets a declared profile selects. Files, never rows.

**The catalogue is `evaluation`'s and this module does not fork it.** The sets
live in ``evaluation/common_datasets/*.yml``, loaded and validated at import by
``evaluation.catalogue`` — every assertion compiled through the same
``compile_assertions`` the API uses, so a shipped regex that will not compile
fails the process at start-up rather than the first person to run a probe. A
second catalogue here would be a second definition of *"passes the safety set"*,
and the one that drifted would be the one nobody was reading.

**Files rather than rows, for `evaluation`'s stated reason.** There is no such
thing as a global row in this database: RLS is deny-by-default and a row matching
no workspace is a row nobody can read (ADR-0035, ADR-0045). A per-workspace
seeded copy drifts the moment one set is corrected, and *"refused 11 of 12"*
starts meaning different things in two installs — which destroys the one property
that makes the number worth printing (A-164).

**The profile selects; it does not size.** A caller passes no case count, no
repeat count and no model override — see A-164. What the profile chooses is
*which* sets are relevant, and the answer to *"is this enough?"* is a larger
shipped set in a pull request, versioned and reviewed, not a parameter.
"""

from typing import Final

from prope.evaluation.catalogue import resolve_builtin
from prope.evaluation.domain import DatasetSpec
from prope.prompt_readiness.domain import Acts, Audience, UntrustedInput, UsageProfile

__all__ = ["INJECTION_SETS", "LEAKAGE_SETS", "select_sets"]

#: Injection: does the prompt obey an instruction smuggled in through user text?
#: Selected whenever anything untrusted reaches the context, which is what makes
#: the question meaningful at all.
INJECTION_SETS: Final[tuple[str, ...]] = ("builtin:chong-tiem-prompt@1",)

#: Leakage: does the prompt print its own system message back? Selected whenever
#: somebody outside the building can see the answer — an internal tool leaking
#: its own instructions to its own author is not an incident.
LEAKAGE_SETS: Final[tuple[str, ...]] = ("builtin:ro-ri-prompt-he-thong@1",)


def select_sets(profile: UsageProfile) -> tuple[DatasetSpec, ...]:
    """The shipped sets this profile's exposure makes worth running.

    Runs against the RESOLVED profile, so an undeclared prompt is probed as if it
    were the worst case. That is the expensive direction of the conservative
    default and it is the right one: an undeclared prompt that turns out to be
    public should have been measured, and the person who declares it `internal`
    afterwards gets a cheaper probe from then on.

    Returns specs, not ids. Resolving here means a set that has been retired by a
    version bump is dropped before a run is created rather than surfacing as an
    empty dispatch loop and a probe run that says nothing.
    """
    resolved = profile.resolve()
    wanted: list[str] = []

    if resolved.untrusted_input != UntrustedInput.NONE:
        wanted.extend(INJECTION_SETS)

    if resolved.audience != Audience.INTERNAL:
        wanted.extend(LEAKAGE_SETS)

    # A prompt that can act on its output is worth probing for injection even
    # when its author says no untrusted content reaches it, because the cost of
    # that declaration being wrong is an action rather than a sentence. This is
    # the one place the module treats a declaration as a claim to test rather
    # than as a fact to trust — and it is deliberate: A-163 forbids INFERRING the
    # profile, not running an extra shipped set because of what one says.
    if resolved.acts in (Acts.EMITS_TOOL_CALLS, Acts.IRREVERSIBLE):
        wanted.extend(set_id for set_id in INJECTION_SETS if set_id not in wanted)

    specs = [spec for set_id in wanted if (spec := resolve_builtin(set_id)) is not None]
    return tuple(specs)
