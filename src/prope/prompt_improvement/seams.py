"""This module's inbound seams. **One, and it is a count.**

This file said *"and there are none"* until 2026-08-25 and the sentence is
corrected rather than left standing. What follows is the argument it made, which
survives the change in full — the forbidden edge is still forbidden, and by more
than absence.

**Almost nothing outside this package calls into it, and that is the design
rather than an oversight.** Every other module's `seams.py` exists because somebody upstream
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

**`open_finding_count` is not that function, and the difference is not its
return type.** The objection above is about a CONSUMER, not about a signature: a
release decision that can read this module can be composed into a gate. That
consumer remains impossible, and now by a test rather than by an empty file —
`tests/architecture/test_release_control_depends_on_four_modules.py` carries an
allow-list of nine packages and `prope.prompt_improvement` is not among them, so
the import fails CI before it can fail on merit. What takes the count is
`agent_run.lifecycle`, which renders one card and decides nothing: a non-zero
count moves a LIVE prompt to ATTENTION and points at this module's own routes,
which is the finding reaching a person exactly as the paragraph above describes.

It exists because the alternative was worse, and was there. `agent_run.lifecycle`
held `SELECT count(*) FROM improvement.finding` — an undeclared edge that imports
nothing, passes every dependency test, and reads this module's table anyway. The
choice was never *seam or no edge*; it was *a seam that says what it is, or a
string of SQL that does the same thing silently*.

**A second absence, and it is the sharper one.** There is no
`apply_proposal(proposal_id)` and no `create_revision_from(candidate_body)`.
Accepting a proposal marks a disposition and returns a body; the write is
prompt-registry's, on a separate and explicit request the person makes themselves
(SR-6, ADR-0066). A seam that performed the write would be *proposed by an agent
and performed by an agent*, which is the one sentence this module's whole design
is arranged to make false.

**Everything else here is types and no behaviour.** They are here so a test — or
a later module that legitimately needs to name a detector or a remedy family —
can import the vocabulary without importing the machinery that produces it.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from prope.prompt_improvement.domain import (
    Anomaly,
    DetectorId,
    FindingStatus,
    ProposalStatus,
    RemedyFamily,
    RemedyKind,
    Severity,
)
from prope.prompt_improvement.repository import count_open_findings


async def open_finding_count(db: AsyncSession, *, workspace_id: str, prompt_id: str) -> int:
    """How many findings are open against one prompt, on the caller's transaction.

    **No permission check, and it must never grow one.** The caller has read the
    prompt row and authorised against it before it has a ``prompt_id`` to pass
    (ADR-0020); a second check here is a second answer that can disagree with the
    first.
    """
    return await count_open_findings(db, workspace_id=workspace_id, prompt_id=prompt_id)


__all__ = [
    "Anomaly",
    "DetectorId",
    "FindingStatus",
    "ProposalStatus",
    "RemedyFamily",
    "RemedyKind",
    "Severity",
    "open_finding_count",
]
