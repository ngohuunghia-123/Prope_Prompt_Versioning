"""The service half of triage: what the model returned, and what survives contact with it.

**Nothing the model returns is trusted.** A ``detector_id`` that was not in the
list it was handed is dropped. A ``remedy_family`` that the anomaly does not make
reachable is dropped — not corrected, dropped, because a "nearest valid family"
is a body transform nobody sanctioned. Every evidence sentence passes
``redact_evidence`` **before storage** (SR-9), not before render, because a rail
applied at render is a rail somebody bypasses with a different client.

**Triage is optional and the sweep survives without it.** If the circuit is open
or the call fails, :func:`triage_anomalies` returns the anomalies ranked by the
detector order in ``detectors.DETECTORS`` with no evidence line and no family —
and the findings still open. **That degradation is the design, not a fallback**:
the detectors carry the facts, and a module that could not report a doubled
fallback rate because a model was down would have its priorities inverted.

**Cost lands on Prope's own meter, never the workspace's.** Triage calls
``APP_OPENAI_*``, the app-owned model, exactly as conversion, search, evaluation's
drafter and readiness's Lane B do. It is not a ``ledger.call_record`` and must
never appear in a cost delta.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from dataclasses import dataclass
from types import ModuleType
from typing import Any

import structlog

from prope.app_agent.circuit import CircuitBreaker, CircuitOpenError
from prope.prompt_improvement.domain import (
    Anomaly,
    DetectorId,
    RemedyFamily,
    bounded_evidence,
)
from prope.prompt_improvement.observability import (
    triage_circuit_open,
    triage_cost_usd_total,
)

log = structlog.get_logger(__name__)

__all__ = ["Triaged", "triage_anomalies"]


@dataclass(frozen=True, slots=True)
class Triaged:
    """One anomaly, ranked, with whatever survived the rails.

    ``evidence`` and ``family`` are both optional because both are the model's and
    the model may be absent. ``anomaly`` is not, because it is the arithmetic's.
    """

    anomaly: Anomaly
    rank: int
    family: RemedyFamily | None = None
    evidence: str | None = None


def _untriaged(anomalies: Sequence[Anomaly]) -> tuple[Triaged, ...]:
    """The model-free answer: detector order, no sentence, no family.

    ``detectors.DETECTORS`` is ordered so that ``fallback_rising`` leads, which
    makes this a real ranking rather than an arbitrary one. A finding with no
    evidence line still stands — the ``vi`` catalogue carries the sentence and the
    evidence is the specificity on top of it (ADR-0053).
    """
    return tuple(
        Triaged(anomaly=anomaly, rank=index + 1) for index, anomaly in enumerate(anomalies)
    )


#: ``import dspy`` costs eleven seconds — litellm, tokenizers, the OTel SDK — and
#: ``worker`` imports this module's sweep at startup. Deferred to a worker thread
#: on first use, as evaluation's drafter and readiness's Lane B do, and for a
#: sharper reason here: a workspace with no anomalies never calls triage at all,
#: so on a healthy install this import never happens.
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
    triage_circuit_open.set(1 if is_open else 0)


_breaker = CircuitBreaker(on_state_change=_set_circuit_metric)


def _anomaly_payload(anomalies: Sequence[Anomaly]) -> str:
    return json.dumps(
        [
            {"detector_id": str(anomaly.detector_id), "figures": anomaly.params}
            for anomaly in anomalies
        ],
        ensure_ascii=False,
        default=str,
    )


def _reachable_payload(anomalies: Sequence[Anomaly]) -> str:
    """What the model may choose from, per detector. **The bound, handed over.**

    Sent as an input field rather than left implicit in the instruction, because
    an instruction is advice and a field is data the model can read back. The
    enforcement is still :func:`_coerce` below — this only makes the correct
    answer available.
    """
    return json.dumps(
        {
            str(anomaly.detector_id): [str(family) for family in anomaly.reachable_families]
            for anomaly in anomalies
        },
        ensure_ascii=False,
    )


def _coerce(
    raw: Any, by_id: dict[DetectorId, Anomaly], index: int
) -> Triaged | None:
    """One returned entry, or ``None`` if it is not one this module admits.

    Three refusals, and each closes a different hole:

    * an unknown ``detector_id`` — a model naming an anomaly nobody detected
      would open a finding about something that did not happen;
    * a ``remedy_family`` the anomaly does not make reachable — this is the one
      that matters, because a family is what selects a body transform;
    * a family on an anomaly whose remedy kind is not ``edit`` — the map already
      said so, and honouring it here would let the model promote a note.
    """
    code = getattr(raw, "detector_id", None) or (
        raw.get("detector_id") if isinstance(raw, dict) else None
    )
    try:
        detector_id = DetectorId(str(code))
    except ValueError:
        return None

    anomaly = by_id.get(detector_id)
    if anomaly is None:
        return None

    family_code = getattr(raw, "remedy_family", None) or (
        raw.get("remedy_family") if isinstance(raw, dict) else None
    )
    family: RemedyFamily | None = None
    if family_code:
        try:
            candidate = RemedyFamily(str(family_code))
        except ValueError:
            candidate = None
        if candidate is not None and candidate in anomaly.reachable_families:
            family = candidate

    rank_value = getattr(raw, "rank", None) or (
        raw.get("rank") if isinstance(raw, dict) else None
    )
    try:
        rank = max(1, int(rank_value))
    except (TypeError, ValueError):
        rank = index + 1

    evidence = getattr(raw, "evidence", None) or (
        raw.get("evidence") if isinstance(raw, dict) else None
    )
    return Triaged(
        anomaly=anomaly,
        rank=rank,
        family=family,
        # Before storage. See the module docstring and SR-9.
        evidence=bounded_evidence(str(evidence)) if evidence else None,
    )


async def triage_anomalies(
    anomalies: Sequence[Anomaly], *, prompt_title: str, prompt_body: str
) -> tuple[Triaged, ...]:
    """Rank and annotate. **Never raises** — the sweep must survive a bad model.

    Returns the untriaged ranking on every failure path, including a circuit that
    is open, a transport error, a model that returned nothing, and a model whose
    every entry was refused by the rails. A caller therefore has one shape to
    handle and no branch for *"triage did not happen"*, which is what keeps the
    degradation from quietly becoming a special case somebody forgets.
    """
    if not anomalies:
        return ()

    by_id = {anomaly.detector_id: anomaly for anomaly in anomalies}

    try:
        agent = await _load_agent()
        program = agent.build_program()

        async def invoke() -> Any:
            with agent.usage_tracking():
                return await program.aforward(
                    prompt_title=prompt_title,
                    prompt_body=prompt_body,
                    anomalies=_anomaly_payload(anomalies),
                    reachable_families=_reachable_payload(anomalies),
                )

        prediction = await _breaker.call(invoke)
    except CircuitOpenError:
        log.info("improvement.triage.circuit_open", anomalies=len(anomalies))
        return _untriaged(anomalies)
    except Exception:
        log.warning("improvement.triage.unavailable", anomalies=len(anomalies))
        return _untriaged(anomalies)

    triage_cost_usd_total.inc(agent.cost_usd(agent.usage_of(prediction)))

    returned = getattr(prediction, "triaged", None) or []
    survived = [
        entry
        for index, raw in enumerate(returned)
        if (entry := _coerce(raw, by_id, index)) is not None
    ]

    # A model that returned nothing usable is a model that was not there. Falling
    # back rather than returning an empty tuple is what stops a bad response from
    # silently suppressing findings the arithmetic already established.
    if not survived:
        return _untriaged(anomalies)

    # Deduplicated on the detector, because a model that named one twice must not
    # produce two findings for one fact — the dedupe index would refuse the second
    # anyway, and doing it here means the count the sweep reports is the truth.
    seen: set[DetectorId] = set()
    ranked: list[Triaged] = []
    for entry in sorted(survived, key=lambda item: item.rank):
        if entry.anomaly.detector_id in seen:
            continue
        seen.add(entry.anomaly.detector_id)
        ranked.append(entry)

    # Anything the model dropped is appended rather than lost. An anomaly the
    # arithmetic found does not stop existing because a model did not mention it.
    ranked.extend(
        Triaged(anomaly=anomaly, rank=len(ranked) + offset + 1)
        for offset, anomaly in enumerate(a for a in anomalies if a.detector_id not in seen)
    )

    # No prompt body, no evidence text. Counts and ids are the whole record —
    # A-046's rule, and the reason
    # `test_no_content_reaches_a_log_line_by_construction.py` can walk this file.
    log.info(
        "improvement.triage.completed",
        anomalies=len(anomalies),
        triaged=len(ranked),
        families=sum(1 for entry in ranked if entry.family is not None),
    )
    return tuple(ranked)
