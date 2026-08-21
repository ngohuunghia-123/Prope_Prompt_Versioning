"""The wire shapes. Codes, never sentences — ADR-0053.

**There is no `message` field anywhere below, and there must not be one.** The
client renders the ``code``, keyed by ``rule_id``, with ``params`` interpolated:
*"{leaked} of {total} injection cases were not refused"* is a Vietnamese string
in the SPA's catalogue and the two integers come from here. A ``message`` field
would be a second, untranslated rendering path, and the one that got used would
be whichever a developer reached for first.

**The single exception is ``evidence``** (D-09), and it is generated directly in
Vietnamese with no English intermediate. It has already passed
``redact_evidence`` before it was stored, so nothing here has to sanitise it —
SR-7 puts the rail at the write and not at the read on purpose.

``severity`` is a two-member enum on the wire as well as in the database. A
client that received a third value would have nowhere to put it, which is the
same argument as the ``CHECK``, one layer out.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from prope.prompt_readiness.domain import RuleId, Severity

__all__ = [
    "DismissalCreate",
    "FindingRead",
    "ProbeRunRead",
    "ProbeStartRead",
    "ReadinessCardRead",
    "RuleRead",
    "UsageProfileRead",
]


class UsageProfileRead(BaseModel):
    """The four axes as declared, plus what they resolved to.

    Both, never one. ``declared`` is what somebody answered and ``assumed`` is
    what the rules actually ran against; showing only the second would quietly
    assert that a person called this prompt public, and showing only the first
    would leave the card unable to explain a finding nobody's declaration
    admits.
    """

    model_config = ConfigDict(extra="forbid")

    audience: str
    untrusted_input: str
    acts: str
    sensitivity: str
    is_declared: bool
    #: The resolved profile. Equal to the four fields above once everything is
    #: declared, which is when the *undeclared — assuming worst case* badge goes.
    assumed: dict[str, str] = Field(default_factory=dict)


class FindingRead(BaseModel):
    """One row on the card."""

    model_config = ConfigDict(extra="forbid")

    rule_id: RuleId
    severity: Severity
    params: dict[str, object] = Field(default_factory=dict)
    #: The profile clause that let this finding through, as a key stem the client
    #: translates. ``"always"`` when the rule does not depend on the profile.
    admitted_by: str = "always"
    evidence: str = ""
    #: Whether a parser-derived edit is available for this finding. The body
    #: itself is NOT here: an edit is fetched when somebody asks to see it, so a
    #: card read never carries a proposed rewrite of every prompt on the screen.
    has_proposed_body: bool = False
    #: True when this rule is dismissed for this prompt. Dismissed findings are
    #: returned rather than hidden, so the card can show *"3 dismissed"* and let
    #: somebody undo — a filter that dropped them server-side would make undoing
    #: require knowing what to look for.
    dismissed: bool = False
    dismissal_reason: str | None = None


class ProbeRunRead(BaseModel):
    """The last probe against this revision, if there was one."""

    model_config = ConfigDict(extra="forbid")

    probe_run_id: str
    catalogue_ref: list[str]
    status: str
    refused_count: int
    leaked_count: int
    error_count: int
    started_at: datetime
    completed_at: datetime | None = None


class ReadinessCardRead(BaseModel):
    """INT-038's response.

    ``frozen`` says whether these bytes are the reviewer's stored copy or a live
    computation. It matters to a reader: a live card can change under them and a
    frozen one cannot, and the screen says which they are looking at rather than
    leaving them to guess from the revision's status.
    """

    model_config = ConfigDict(extra="forbid")

    prompt_id: str
    version_id: str
    profile: UsageProfileRead
    findings: list[FindingRead]
    #: Counts first, rows second — the card's whole layout argument, computed
    #: server-side so two clients cannot disagree about the headline.
    warning_count: int
    advice_count: int
    dismissed_count: int
    catalogue_version: str
    frozen: bool
    probe: ProbeRunRead | None = None
    #: The set ids a probe WOULD run for this profile, so the offer can say what
    #: it is about to spend money on before somebody presses it.
    probe_offers: list[str] = Field(default_factory=list)
    #: True when Lane B could not run. The card renders without it and says so,
    #: rather than silently returning three fewer findings.
    lane_b_unavailable: bool = False


class DismissalCreate(BaseModel):
    """INT-041's body. A reason is required and it may not be blank.

    ``min_length`` on a stripped value rather than on the raw one, because a
    reason of three spaces is not a reason — and the dismissal rate per rule
    (OQ-157) cannot tell *the rule is wrong* from *the filter is wrong* without
    them.
    """

    model_config = ConfigDict(extra="forbid")

    rule_id: RuleId
    reason: str = Field(min_length=1, max_length=500)


class ProbeStartRead(BaseModel):
    """INT-039's response: what ran, and what it found."""

    model_config = ConfigDict(extra="forbid")

    probe_run_id: str
    status: str
    refused_count: int
    leaked_count: int
    error_count: int
    catalogue_ref: list[str]


class RuleRead(BaseModel):
    """INT-042. One entry in the catalogue a client must be able to render.

    This endpoint is what makes AC-4 assertable: the `vi` catalogue is total over
    the set returned here, checked in CI, so a rule added without a translation
    fails the build rather than rendering as an empty row for a Vietnamese user.
    """

    model_config = ConfigDict(extra="forbid")

    rule_id: RuleId
    lane: str
    default_severity: Severity
    admitted_by: str
    can_propose_edit: bool
