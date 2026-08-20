"""The wire shapes. snake_case as the API sends it, and no field that could carry a body.

**`FindingRead` has no prompt body and `ProposalRead` has no rationale.** Both
absences are the type doing what a rule would otherwise have to: the card
carries *what changed, in consequence language*, the eval delta per case, the
cost delta and which keys call this — and explicitly not the model's story about
why its own edit works (ADR-0068 §4). A field for one would be filled.

**`candidate_body` appears on exactly one shape and only after a decision.**
`ProposalRead` — the inbox row — does not carry it; `ProposalAccepted`, returned
from the accept route, does. The reviewer sees the candidate on the detail screen
they opened deliberately, and the inbox stays a list of decisions rather than a
page of bodies.

**Every code crossing the wire is a machine code** (ADR-0053): `detector_id`,
`severity`, `remedy_kind`, `remedy_family`, `status`. The client owns every
sentence, CI asserts the `vi` catalogue is total over the first two (AC-11), and
`evidence_line` is the single exemption — generated directly in Vietnamese,
through the output rail, before storage.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from prope.prompt_improvement.domain import (
    DetectorId,
    RemedyFamily,
    RemedyKind,
    Severity,
)

__all__ = [
    "DismissalCreate",
    "FindingRead",
    "InboxRead",
    "ProposalAccepted",
    "ProposalRead",
    "ScheduleRead",
    "ScheduleWrite",
]


class ProposalRead(BaseModel):
    """A proposal as the inbox renders it. **No candidate body here.**

    ``gate_delta`` is the per-case eval result, stored on the row rather than
    recomputed, so a card written a year ago still reads the numbers the decision
    was offered against (ADR-0019's rule).
    """

    model_config = ConfigDict(from_attributes=True)

    proposal_id: str
    remedy_kind: RemedyKind
    remedy_family: RemedyFamily | None = None
    gate_delta: dict[str, Any] | None = None
    expires_at: datetime


class FindingRead(BaseModel):
    """One open finding. The arithmetic, the count, and one sentence."""

    model_config = ConfigDict(from_attributes=True)

    finding_id: str
    prompt_id: str
    detector_id: DetectorId
    severity: Severity
    #: The detector's own figures — both windows, the ratio, the percentile. The
    #: client renders them into the `vi` sentence for this `detector_id`.
    params: dict[str, Any] = Field(default_factory=dict)
    #: The triage model's one sentence, or absent. A finding with no evidence
    #: line still stands: the catalogue carries the sentence and this is the
    #: specificity on top of it.
    evidence_line: str | None = None
    first_seen: datetime
    last_seen: datetime
    #: **Fourteen occurrences, not fourteen rows.** The dedupe index is what makes
    #: this number exist at all.
    occurrence_count: int
    status: str
    proposal: ProposalRead | None = None


class InboxRead(BaseModel):
    """The inbox. **A prompt the reader cannot see contributes nothing** (SR-7).

    Not a redacted row, not a count, not a total that differs — the two shapes
    BR-01 admits and never a third. ``total`` is the length of ``findings`` and is
    computed after authorisation for exactly that reason.
    """

    findings: list[FindingRead]
    total: int
    warning_count: int
    advice_count: int


class DismissalCreate(BaseModel):
    """Why. Required, and non-empty by constraint as well as by this bound.

    The dismissal rate per ``detector_id`` is this module's honest metric, and a
    rate without reasons cannot tell *the detector is wrong* from *the remedy is
    wrong* — which argue for opposite fixes (OQ-157).
    """

    reason: str = Field(min_length=1, max_length=500)


class ProposalAccepted(BaseModel):
    """What the accept route hands back. **It wrote no revision** (SR-6).

    ``candidate_body`` is returned so the client can open the revision editor
    prefilled; the write is prompt-registry's ``create_revision`` on a separate,
    explicit request under ``revision.create``. chat-orchestrator's
    ``pending_action`` shape, and its reason — the act a person takes must be the
    act they can see themselves taking.
    """

    proposal_id: str
    prompt_id: str
    remedy_family: RemedyFamily | None = None
    candidate_body: str | None = None
    gate_delta: dict[str, Any] | None = None


class ScheduleWrite(BaseModel):
    """The re-probe schedule. ``spend_ceiling.manage``, because it is a charge.

    Empty ``namespaces`` and empty ``prompt_ids`` with ``enabled`` true means
    every released prompt — a deliberate choice on a screen showing the estimated
    weekly cost, not an accident of two empty arrays.
    """

    enabled: bool = False
    #: Bounded here and by ``ck_improvement_schedule_cadence_is_bounded``. Daily
    #: is the floor because a cadence shorter than the sweep that feeds it
    #: measures nothing new; ninety days is the ceiling because a guardrail
    #: checked less often than a quarter is a guardrail nobody is checking.
    cadence_days: int = Field(default=7, ge=1, le=90)
    namespaces: list[str] = Field(default_factory=list, max_length=200)
    prompt_ids: list[str] = Field(default_factory=list, max_length=500)


class ScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    enabled: bool
    cadence_days: int
    namespaces: list[str]
    prompt_ids: list[str]
    last_run_at: datetime | None = None
    updated_at: datetime
