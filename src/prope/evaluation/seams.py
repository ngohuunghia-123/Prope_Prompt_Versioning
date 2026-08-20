"""This module's public in-process surface.

**Two shapes, and the second arrived with ADR-0068.** ``get_review_summary`` is
what release-control reads before a decision. ``score_body_against_suite`` is the
machine-side gate prompt-improvement runs before a person is shown a candidate
edit — and it lives here rather than there because compiling assertions and
deciding whether an output passed is this module's job. A second implementation
next door would be a second definition of *"passes the suite"*, and the one that
drifted would be the one nobody was reading.

``suites_for_prompt`` exists for one question and answers only it: **does this
prompt have a suite at all?** ADR-0068 §2 makes that precondition absolute — no
suite, no edit proposal, for every family and every anomaly — so the caller needs
the answer before it spends anything, and it needs it without reaching past this
file into ``evaluation.repository``.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from prope.evaluation.domain import (
    CostDelta,
    ReviewSummary,
    RunStatus,
    SuiteRow,
    SuiteSummary,
    WithheldReason,
)
from prope.evaluation.gate import (
    CandidateRevision,
    CaseVerdict,
    GateResult,
    SpendCeilingReached,
    score_body_against_suite,
)
from prope.evaluation.repository import list_current_suites
from prope.evaluation.summary import get_review_summary


async def suites_for_prompt(db: AsyncSession, prompt_id: str) -> tuple[SuiteRow, ...]:
    """Every current suite for one prompt, on the caller's transaction.

    **No permission check, and it must never grow one.** The caller has already
    read the prompt row and authorised against it (ADR-0020); a second check here
    is a second answer that can disagree with the first.

    A suite with ``case_count == 0`` is still a suite as far as the ROW is
    concerned and is not one as far as the gate is concerned. The caller filters,
    because *"has a suite"* and *"has something to run"* are different questions
    and this seam should not decide which one was asked.
    """
    return await list_current_suites(db, prompt_id)


__all__ = [
    "CandidateRevision",
    "CaseVerdict",
    "CostDelta",
    "GateResult",
    "ReviewSummary",
    "RunStatus",
    "SpendCeilingReached",
    "SuiteRow",
    "SuiteSummary",
    "WithheldReason",
    "get_review_summary",
    "score_body_against_suite",
    "suites_for_prompt",
]
