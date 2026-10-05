"""Small, redacted failure samples for the revision-improvement consumer.

Inputs, assertion values and outputs remain untrusted data after redaction.
They describe a failed case; they never become instructions to the drafter.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from prope.evaluation.domain import CaseResultRow, CaseRow

IMPROVEMENT_SAMPLE_CAP: Final = 3
MAX_FAILURE_EVIDENCE_CHARACTERS: Final = 400


@dataclass(frozen=True, slots=True)
class RevisionAssertionEvidence:
    type: str
    value: str
    passed: bool | None
    detail: str | None


@dataclass(frozen=True, slots=True)
class RevisionFailureSample:
    case_id: str
    case_name: str
    input_messages: str
    input_variables: str
    assertions: tuple[RevisionAssertionEvidence, ...]
    output_content: str


def _bounded(text: str, redact_sample: Callable[[str], str]) -> str:
    return redact_sample(text)[:MAX_FAILURE_EVIDENCE_CHARACTERS]


def _bounded_json(value: Any, redact_sample: Callable[[str], str]) -> str:
    return _bounded(json.dumps(value, ensure_ascii=False), redact_sample)


def failure_sample(case: CaseRow, result: CaseResultRow, redact_sample: Callable[[str], str]) -> RevisionFailureSample:
    """Redact before handing case content to another module or persisting it."""
    assertions = []
    for ordinal, spec in enumerate(case.assertions):
        outcome = result.assertion_results[ordinal] if ordinal < len(result.assertion_results) else None
        # The executor preserves assertion order. An incomplete or inconsistent
        # result must not manufacture an outcome for a different assertion.
        if outcome is not None and outcome.type is not spec.type:
            outcome = None
        assertions.append(
            RevisionAssertionEvidence(
                type=spec.type.value,
                value=_bounded_json(spec.value, redact_sample),
                passed=outcome.passed if outcome is not None else None,
                detail=(
                    _bounded(outcome.detail, redact_sample)
                    if outcome is not None and outcome.detail is not None
                    else None
                ),
            )
        )
    return RevisionFailureSample(
        case_id=case.id,
        case_name=_bounded(case.name, redact_sample),
        input_messages=_bounded_json(case.input_messages, redact_sample),
        input_variables=_bounded_json(case.input_variables, redact_sample),
        assertions=tuple(assertions),
        output_content=_bounded(result.output_content or "", redact_sample),
    )
