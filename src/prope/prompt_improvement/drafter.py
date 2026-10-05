"""The service half of the drafter: one authored edit, or a typed unavailability.

**Mirror of `triage.py`'s shape, one difference.** Triage degrades silently to
the untriaged ranking because the sweep must survive a bad model; the drafter
degrades *loudly* to :class:`DrafterUnavailableError` because a person clicked
"propose a fix" and the honest answer is *the drafting model could not be
reached — your findings are kept, click again later*. The never-raise property
belongs to unattended passes; this path is attended, and a silent no-proposal
would read as "nothing to fix", which is a lie (orchestration chapter's
silent-no-op rule).

**The output is not trusted here either.** This function returns what the model
said, bounded only by the output model's own fields; every guarantee about the
body lives in `rails.py`, checked by the caller BEFORE the gate spends
anything. Nothing in this file looks at the body at all, on purpose — the day
a "quick sanity check" lands here is the day two modules disagree about what
a safe candidate is.

**Cost lands on Prope's meter**, beside triage's: the app-owned model, never a
``ledger.call_record``, never a cost delta. Its own metric name, so no
dashboard can add the two meters by accident.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from types import ModuleType
from typing import Any

import structlog

from prope.app_agent.circuit import CircuitBreaker, CircuitOpenError
from prope.evaluation.seams import RevisionFailureSample, RevisionFinding
from prope.prompt_improvement.domain import bounded_evidence
from prope.prompt_improvement.observability import (
    draft_circuit_open,
    draft_cost_usd_total,
)
from prope.prompt_improvement.rails import MARKERS

log = structlog.get_logger(__name__)

__all__ = ["DrafterUnavailableError", "draft_edit"]


class DrafterUnavailableError(RuntimeError):
    """The drafting model could not be called. A typed degradation, not a failure.

    Carries nothing but the fact: the run records
    ``termination_reason="drafter_unavailable"``, findings stay open, and the
    person can click again — the same shape `evaluation`'s
    ``DrafterUnavailableError`` gives the dataset drafter, moved onto a run.
    """


#: ``import dspy`` costs eleven seconds and the worker imports this module's
#: sweep at startup — the same deferred-import reason `triage.py` carries, with
#: more force: the drafter only ever runs on a person's click.
_agent: ModuleType | None = None


def _import_agent() -> ModuleType:
    global _agent

    if _agent is None:
        from prope.prompt_improvement import dspy_program

        _agent = dspy_program

    return _agent


async def _load_agent() -> ModuleType:
    if _agent is not None:
        return _agent
    return await asyncio.to_thread(_import_agent)


def _set_circuit_metric(is_open: bool) -> None:
    draft_circuit_open.set(1 if is_open else 0)


#: Its own instance, not triage's: a downed provider should stop drafting
#: without stopping ranking, and vice versa — per feature, the rule `circuit.py`
#: itself states.
_breaker = CircuitBreaker(on_state_change=_set_circuit_metric)


def _redact_markers(text: str) -> str:
    # Evidence cannot close its DSPy input field or open another one.
    for marker in MARKERS:
        text = text.replace(marker, "[redacted delimiter]")
    return text


def _failure_excerpt(sample: RevisionFailureSample) -> str:
    # Share the evidence budget across constraints, actual output and inputs:
    # a long schema or output must not crowd every input out of the excerpt.
    assertions = json.dumps(
        [
            {"type": assertion.type, "value": assertion.value, "passed": assertion.passed}
            for assertion in sorted(sample.assertions, key=lambda assertion: assertion.passed is not False)
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    sections = (
        ("assertions", assertions, 130),
        ("output", sample.output_content, 80),
        ("input", sample.input_messages, 100),
        ("variables", sample.input_variables, 40),
    )
    return bounded_evidence(
        " | ".join(f"{label}: {bounded_evidence(_redact_markers(value))[:limit]}" for label, value, limit in sections)
    )


def groups_payload(
    groups: Sequence[Any],
    *,
    revision_findings: Sequence[RevisionFinding] = (),
) -> str:
    """The failing groups as bounded JSON, handed to the model as data.

    Match evidence by suite ID and assertion type, never by the display name.
    Case content is untrusted even after redaction: at most three distinct
    samples, each one a redacted excerpt within the existing 400-character
    evidence rail. Samples remain model input, not persisted finding params.
    """
    findings = {(finding.suite_id, finding.assertion_type): finding for finding in revision_findings}
    payload: list[dict[str, Any]] = []
    sampled: set[str] = set()
    for group in groups:
        item: dict[str, Any] = {
            "detector_id": str(group.detector_id),
            "params": dict(group.params),
        }
        finding = findings.get((group.params.get("suite_id"), group.params.get("assertion_type")))
        if finding is not None:
            item["issue"] = bounded_evidence(finding.issue)
            item["advice"] = bounded_evidence(finding.advice)
            samples = []
            for sample in finding.failing_samples:
                if len(sampled) >= 3:
                    break
                if sample.case_id in sampled:
                    continue
                samples.append(_failure_excerpt(sample))
                sampled.add(sample.case_id)
            item["failing_samples"] = samples
        payload.append(item)
    return _redact_markers(json.dumps(payload, ensure_ascii=False, default=str))


async def draft_edit(
    *,
    prompt_title: str,
    prompt_body: str,
    failing_groups: Sequence[Any],
    revision_findings: Sequence[RevisionFinding] = (),
    previous_error: str = "",
) -> tuple[str, str]:
    """``(candidate_body, rationale)`` from one model call, or raises.

    The breaker wraps the call, so a person clicking "propose a fix" during an
    outage hits an open circuit rather than the provider — and the typed error
    is what the run's termination reason is made of. Usage is priced on Prope's
    own meter the moment the call returns, before any rail runs: the tokens
    were spent whatever the rails think of the result.
    """
    try:
        agent = await _load_agent()
        program = agent.build_draft_program()

        async def invoke() -> Any:
            with agent.usage_tracking():
                return await program.aforward(
                    prompt_title=prompt_title,
                    prompt_body=prompt_body,
                    failing_groups=groups_payload(failing_groups, revision_findings=revision_findings),
                    previous_error=previous_error,
                )

        prediction = await _breaker.call(invoke)
    except CircuitOpenError as error:
        log.info("improvement.draft.circuit_open", anomalies=len(failing_groups))
        raise DrafterUnavailableError("drafting circuit is open") from error
    except Exception as error:
        log.warning("improvement.draft.unavailable", anomalies=len(failing_groups))
        raise DrafterUnavailableError("drafting model could not be called") from error

    draft_cost_usd_total.inc(agent.cost_usd(agent.usage_of(prediction)))

    edit = getattr(prediction, "edit", None)
    if edit is None or not getattr(edit, "candidate_body", ""):
        # A call that returned nothing shaped like an edit is an unavailability
        # of a different coat: the model was reached and said nothing usable.
        # Typed the same way — the person's remedy is the same click.
        log.info("improvement.draft.empty")
        raise DrafterUnavailableError("drafting model returned nothing usable")

    return str(edit.candidate_body), str(edit.rationale)
