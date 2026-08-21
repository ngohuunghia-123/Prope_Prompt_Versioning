"""This module's inbound seams — and there are none.

**Nothing outside this package calls into it, and that is the design rather than
an oversight.** Every other module's `seams.py` exists because somebody upstream
needs a function: the gateway needs `record_observation`, release-control needs
`set_revision_status`, prompt-improvement itself needs `run_probe`. This module
is a leaf. It reads six modules and is read by none — the findings reach a person
through its own HTTP routes and nothing else.

**The one edge that could exist must not.** `release-control` is forbidden in
BOTH directions (ADR-0068): nothing here is an input to a release decision and
nothing here may be consulted by one. An `open_findings_for(prompt_id)` exported
from this file would be entirely reasonable code and would turn the evidence card
into a gate wearing an inbox's clothes — *nothing blocks* defeated by composition
rather than by argument. `prompt-readiness` established that shape and it costs
even less to keep here: nothing in this module wants to be at submit time, and a
post-publish finding has less standing to gate a future decision than a
pre-publish one, not more.

**A second absence, and it is the sharper one.** There is no
`apply_proposal(proposal_id)` and no `create_revision_from(candidate_body)`.
Accepting a proposal marks a disposition and returns a body; the write is
prompt-registry's, on a separate and explicit request the person makes themselves
(SR-6, ADR-0066). A seam that performed the write would be *proposed by an agent
and performed by an agent*, which is the one sentence this module's whole design
is arranged to make false.

**So this file exports types and no behaviour.** They are here so a test — or a
later module that legitimately needs to name a detector or a remedy family — can
import the vocabulary without importing the machinery that produces it.
"""

from prope.prompt_improvement.domain import (
    Anomaly,
    DetectorId,
    FindingStatus,
    ProposalStatus,
    RemedyFamily,
    RemedyKind,
    Severity,
)

__all__ = [
    "Anomaly",
    "DetectorId",
    "FindingStatus",
    "ProposalStatus",
    "RemedyFamily",
    "RemedyKind",
    "Severity",
]
