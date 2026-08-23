"""Lane B's service half: the gate between what a model returned and what a person sees.

**Nothing the model writes is trusted to be a finding.** Every returned code is
looked up in this module's own catalogue and dropped if it is not one of the
three Lane B may produce; every evidence sentence goes through
``redact_evidence`` **before storage** (SR-7), not before render, because a rail
applied at render is a rail somebody bypasses with a different client. A finding
left with no evidence still stands — the ``vi`` catalogue carries the sentence
and the evidence line is the specificity on top of it.

**Cost lands on Prope's own meter, never the workspace's.** Lane B calls
``APP_OPENAI_*``, the app-owned model, exactly as conversion, search and
evaluation's drafter do. It is not a ``ledger.call_record`` and must never appear
in a cost delta: the delta compares what two revisions cost to *serve*, and a
convenience feature's bill inside that number would make a revision look more
expensive because somebody pressed a button.

**On request only** (D-08). Lane A is free and runs on every card; Lane B spends
money, and a forty-prompt import that auto-drafted would be forty unrequested
calls on a meter with no ceiling concept. The cache is what makes asking twice
free.

**The fingerprint covers the body and the profile and nothing else.** An edit
changes it and the next request does the work again; a report already rendered
cannot be disturbed by either. It is evaluation's dataset-fingerprint pattern for
evaluation's reason.
"""

import asyncio
import hashlib
from dataclasses import dataclass
from types import ModuleType
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from prope.app_agent.circuit import CircuitBreaker, CircuitOpenError
from prope.app_agent.client import APP_AGENT_MODEL
from prope.prompt_readiness import repository
from prope.prompt_readiness.domain import (
    CATALOGUE_VERSION,
    Finding,
    RuleId,
    Severity,
    UsageProfile,
    redact_evidence,
)
from prope.prompt_readiness.observability import (
    drafter_circuit_open,
    drafter_cost_usd_total,
    lane_b_cache_hits_total,
)

log = structlog.get_logger(__name__)

__all__ = ["LaneBUnavailableError", "fingerprint", "lane_b_findings"]

#: The three codes Lane B may produce, as ``RuleId``. The model's own enum is
#: ``dspy_program.NonRunnableRule``; this is the map that refuses everything
#: else. A model returning ``probe_injection_leaked`` — a measurement — would be
#: returning an opinion where a number belongs, and it is dropped here.
_ALLOWED: dict[str, RuleId] = {
    "contradictory_instructions": RuleId.CONTRADICTORY_INSTRUCTIONS,
    "redundant_body": RuleId.REDUNDANT_BODY,
    "no_refusal_path": RuleId.NO_REFUSAL_PATH,
}

#: All three are advice. None of them is a security property — those are measured
#: by Lane C — and a model-chosen finding rated `warning` would outrank a
#: probe's measured leak on the same card, which inverts the whole design.
_SEVERITY = Severity.ADVICE


class LaneBUnavailableError(Exception):
    """The lane could not run. The card renders without it and says so."""


#: ``import dspy`` costs eleven seconds — litellm, tokenizers, the OTel SDK — and
#: ``app.py`` imports this module's router at startup. Deferred to a worker
#: thread on first use, as evaluation's drafter does and for the same reason:
#: Lane B is a button somebody presses occasionally, not a registration path.
_agent: ModuleType | None = None


def _import_agent() -> ModuleType:
    global _agent

    if _agent is None:
        from prope.prompt_readiness import dspy_program

        _agent = dspy_program

    return _agent


async def _load_agent() -> ModuleType:
    if _agent is not None:
        return _agent
    return await asyncio.to_thread(_import_agent)


def _set_circuit_metric(is_open: bool) -> None:
    drafter_circuit_open.set(1 if is_open else 0)


_breaker = CircuitBreaker(on_state_change=_set_circuit_metric)


@dataclass(frozen=True, slots=True)
class LaneBOutcome:
    findings: tuple[Finding, ...]
    model: str
    cached: bool


def fingerprint(body: str, profile: UsageProfile) -> str:
    """The cache key: body, profile, catalogue version.

    The catalogue version is in it because a rule added or retired changes what
    Lane B is being asked for, and a cache that survived a catalogue bump would
    serve last release's answer to this release's question.
    """
    digest = hashlib.sha256()
    digest.update(body.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(repr(sorted(profile.as_dict().items())).encode("utf-8"))
    digest.update(b"\x00")
    digest.update(CATALOGUE_VERSION.encode("utf-8"))
    return digest.hexdigest()


def _coerce(raw: Any) -> Finding | None:
    """One returned finding, or ``None`` if it is not one this module admits."""
    code = getattr(raw, "rule_id", None) or (raw.get("rule_id") if isinstance(raw, dict) else None)
    rule_id = _ALLOWED.get(str(code))
    if rule_id is None:
        return None

    evidence = getattr(raw, "evidence", None) or (
        raw.get("evidence") if isinstance(raw, dict) else None
    )
    return Finding(
        rule_id=rule_id,
        severity=_SEVERITY,
        params={},
        # Before storage. See the module docstring and SR-7.
        evidence=redact_evidence(str(evidence or "")),
    )


async def lane_b_findings(
    db: AsyncSession,
    *,
    workspace_id: str,
    prompt_id: str,
    prompt_title: str,
    prompt_body: str,
    profile: UsageProfile,
    actor_id: str,
) -> LaneBOutcome:
    """Run Lane B, or serve the cache. Raises :class:`LaneBUnavailableError` when neither works.

    An empty finding list is a **successful** call. Lane B reporting nothing is
    the common and correct answer for a well-written body, and a caller that
    treated it as a failure would push the model toward inventing something.
    """
    key = fingerprint(prompt_body, profile)

    cached = await repository.read_cached_lane_b(db, workspace_id=workspace_id, fingerprint=key)
    if cached is not None:
        lane_b_cache_hits_total.inc()
        findings = tuple(f for entry in cached if (f := _coerce(entry)) is not None)
        return LaneBOutcome(findings=findings, model=APP_AGENT_MODEL, cached=True)

    agent = await _load_agent()
    program = agent.build_program()

    async def invoke() -> Any:
        with agent.usage_tracking():
            return await program.aforward(prompt_body=prompt_body, prompt_title=prompt_title)

    try:
        prediction = await _breaker.call(invoke)
    except CircuitOpenError as error:
        raise LaneBUnavailableError("the readiness agent is in a failing state") from error
    except Exception as error:
        raise LaneBUnavailableError(str(error)) from error

    usage = agent.usage_of(prediction)
    drafter_cost_usd_total.inc(agent.cost_usd(usage))

    returned = getattr(prediction, "findings", None) or []
    findings = tuple(f for entry in returned if (f := _coerce(entry)) is not None)

    await repository.write_cached_lane_b(
        db,
        workspace_id=workspace_id,
        fingerprint=key,
        findings=[
            {"rule_id": str(f.rule_id), "evidence": f.evidence} for f in findings
        ],
        model_name=APP_AGENT_MODEL,
    )

    # No prompt body, no evidence text. The counts and the ids are the whole
    # record — A-046's rule, and the reason
    # `test_no_content_reaches_a_log_line_by_construction.py` can walk this file.
    log.info(
        "readiness.lane_b.completed",
        workspace_id=workspace_id,
        actor_id=actor_id,
        prompt_id=prompt_id,
        model_name=APP_AGENT_MODEL,
        finding_count=len(findings),
        dropped=len(returned) - len(findings),
        input_tokens=usage.get("input", 0),
        output_tokens=usage.get("output", 0),
    )
    return LaneBOutcome(findings=findings, model=APP_AGENT_MODEL, cached=False)
