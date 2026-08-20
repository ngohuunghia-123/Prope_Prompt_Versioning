"""The comparison funnel: what "the same job" means, and how it is decided.

The duplicate check behind the import screen used to compute *which vectors are
nearest* and render that as *these are duplicates*. This package is the answer to
the question that was never asked: **two prompts do the same job when swapping
one for the other would not break the caller.**

    domain            the vocabulary — verdicts, actions, findings, severities
    structural        the free rung: canonical blocks, pool-relative IDF, 20 -> 5
    input_contract    stage 2a — `required_variables` set math. Free and exact
    output_contract   stage 2b — the declared output contract as a descriptor
    verdict           aggregation: task relation + findings -> verdict + action
    trace             the rung vocabulary the funnel narrates itself with
    pipeline          the funnel end to end

Everything here is pure except `pipeline.compare`, which is async only because
the one paid rung — the adjudicator — is injected into it. No module in this
package imports DSPy, opens a database session, or reads a clock.

The decisions and their reasons live in `docs/brainstorm/prompt-similarity.draft.md`.
Read it before changing a threshold or a severity: several tempting fixes
(averaging scores, prose summaries between stages, defaulting to "use the
existing prompt instead") were considered and rejected there, with reasons.
"""

from prope.prompt_search.comparison.domain import (
    FINDING_CODES,
    REASON_CODES,
    TASK_RELATIONS,
    Action,
    BlockOverlapRead,
    CandidateEvidence,
    CandidateOverlap,
    EvidenceSheet,
    Finding,
    InputContractRelation,
    Severity,
    Verdict,
)
from prope.prompt_search.comparison.input_contract import (
    InputContractComparison,
    compare_input_contracts,
    requires_subset_of,
)
from prope.prompt_search.comparison.output_contract import (
    UNSPECIFIED,
    OutputDescriptor,
    compare_output_contracts,
    declared_output_text,
    produces_superset_of,
)
from prope.prompt_search.comparison.pipeline import (
    ADJUDICATION_LIMIT,
    RETRIEVAL_LIMIT,
    CandidateInput,
    compare,
    present,
)
from prope.prompt_search.comparison.structural import (
    BlockOverlap,
    PromptFacts,
    ScoredCandidate,
    facts_of,
    rank_candidates,
)
from prope.prompt_search.comparison.trace import (
    STEP_CODES,
    Step,
    StepState,
    TraceEvent,
)
from prope.prompt_search.comparison.verdict import (
    MATCH_FLOOR,
    USE_EXISTING_REQUIRES_MEASUREMENT,
    recommend,
    resolve_action,
    resolve_verdict,
    summarise,
)

__all__ = [
    "ADJUDICATION_LIMIT",
    "FINDING_CODES",
    "MATCH_FLOOR",
    "REASON_CODES",
    "RETRIEVAL_LIMIT",
    "STEP_CODES",
    "TASK_RELATIONS",
    "UNSPECIFIED",
    "USE_EXISTING_REQUIRES_MEASUREMENT",
    "Action",
    "BlockOverlap",
    "BlockOverlapRead",
    "CandidateEvidence",
    "CandidateOverlap",
    "CandidateInput",
    "EvidenceSheet",
    "Finding",
    "InputContractComparison",
    "InputContractRelation",
    "OutputDescriptor",
    "PromptFacts",
    "ScoredCandidate",
    "Severity",
    "Step",
    "StepState",
    "TraceEvent",
    "Verdict",
    "compare",
    "compare_input_contracts",
    "compare_output_contracts",
    "declared_output_text",
    "facts_of",
    "present",
    "produces_superset_of",
    "rank_candidates",
    "recommend",
    "requires_subset_of",
    "resolve_action",
    "resolve_verdict",
    "summarise",
]
