"""The eval advisor: what to measure, and what the results said.

Two services behind the evaluation tab's agent buttons:

**Dataset suggestion** asks the app agent — the same app-owned model the
drafter uses — to select which library sets genuinely measure this prompt, and
gates the answer before a person sees it. It replaced a keyword scorer whose
six "universal" sets were proposed for every body, which read as advice while
recommending suites a prompt would fail for doing its job (a JSON-format set
on a prose prompt is the exact trap ``applicability`` exists to prevent). The
model judges fit; the gate keeps the promises that made the old scorer safe:
an id that is not in the catalogue it was shown is dropped, so the answer can
never propose a set that does not exist, and an empty list is a valid answer,
so "nothing truly applies" stays sayable. Availability lands on the same
circuit breaker as drafting, and an unavailable model is a 503 the person can
retry — never a silent fall back to the scorer that produced the noise.

**Run analysis** groups a finished run set's failing case results by suite and
assertion type, and turns each group into one finding with fixed advice text per
assertion type. The advice is a table, not a generation: "thêm giới hạn độ dài"
is what a ``max_length`` failure means, whether or not a model is available to
say it more politely. Severity reuses the improvement vocabulary (``advice`` /
``warning``, ADR-0067) — an analysis never blocks anything.
"""

import asyncio
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Final

import structlog

from prope.app_agent.cache import Cache, CacheMeta, NoOpCache, compute_key
from prope.app_agent.circuit import CircuitBreaker, CircuitOpenError
from prope.app_agent.client import APP_AGENT_MODEL
from prope.app_agent.dspy_runtime import cost_usd
from prope.evaluation.domain import AssertionType
from prope.evaluation.observability import (
    advisor_circuit_open,
    advisor_cost_usd_total,
    advisor_suggestions_dropped_total,
    advisor_total,
    llm_cache_cost_saved_usd_total,
    llm_cache_errors_total,
    llm_cache_put_total,
    llm_cache_total,
)

__all__ = [
    "AdviceFinding",
    "AdvisorUnavailableError",
    "DatasetSuggestion",
    "SUGGESTION_CAP",
    "analyze_runs",
    "suggest_datasets",
]

log = structlog.get_logger(__name__)

#: The tree refuses more than this per prompt; suggesting more is noise.
SUGGESTION_CAP: Final = 8

#: A reason is one sentence in the popover; longer means the model started
#: writing a paragraph, and the person reading ten of them did not ask for it.
_REASON_LIMIT: Final = 240


@dataclass(frozen=True, slots=True)
class DatasetSuggestion:
    dataset_id: str
    name: str
    reason: str
    confidence: float


class AdvisorUnavailableError(RuntimeError):
    """The agent could not be called. Distinct from "it answered, oddly" — the
    caller refuses with 503 for this one and never for the other."""


#: `import dspy` costs eleven seconds — `generation.py` documents the ledger.
#: Suggesting is a button somebody presses occasionally, so the same lazy
#: worker-thread import applies: the first suggest pays it without blocking the
#: event loop, every later one pays nothing.
_agent: ModuleType | None = None


def _import_agent() -> ModuleType:
    global _agent

    if _agent is None:
        from prope.evaluation import suggest_program

        _agent = suggest_program

    return _agent


async def _load_agent() -> ModuleType:
    if _agent is not None:
        return _agent
    return await asyncio.to_thread(_import_agent)


def _set_circuit_metric(is_open: bool) -> None:
    advisor_circuit_open.set(1 if is_open else 0)


_breaker = CircuitBreaker(on_state_change=_set_circuit_metric)


def _catalogue_block(catalogue: list[tuple[str, str, str | None, str]]) -> str:
    """The library as the model sees it — the same fields a person reads.

    ``applicability`` is the load-bearing line: it is the dataset author's own
    statement of when the set must *not* be attached, and the whole relevance
    improvement lives in the model honouring it.
    """
    rows = []
    for dataset_id, name, applicability, description in catalogue:
        rows.append(
            f"- id: {dataset_id}\n"
            f"  name: {name}\n"
            f"  applicability: {applicability or 'áp dụng cho mọi prompt'}\n"
            f"  description: {description}"
        )
    return "\n".join(rows)


def _gated(
    raw: object,
    known_ids: dict[str, str],
) -> tuple[list[DatasetSuggestion], int]:
    """What the model answered that a person may see, and what was dropped.

    The model proposes; this gate disposes. An id absent from the catalogue it
    was shown is a hallucination and is dropped — that is what keeps "cannot
    invent a set that does not exist" true one model call later. Order is the
    model's ranking, first occurrence wins on duplicates, and the cap is
    applied last so eight is the ceiling on what is shown, not on what counts
    as a duplicate.
    """
    suggestions: list[DatasetSuggestion] = []
    dropped = 0
    seen: set[str] = set()

    for entry in raw or []:
        dataset_id = str(getattr(entry, "dataset_id", "") or "").strip()
        if dataset_id not in known_ids:
            if dataset_id:
                advisor_suggestions_dropped_total.labels(reason="unknown_dataset_id").inc()
            else:
                advisor_suggestions_dropped_total.labels(reason="entry_without_id").inc()
            dropped += 1
            continue
        if dataset_id in seen:
            advisor_suggestions_dropped_total.labels(reason="duplicate").inc()
            dropped += 1
            continue

        try:
            confidence = min(1.0, max(0.0, float(getattr(entry, "confidence", 0.0))))
        except (TypeError, ValueError):
            advisor_suggestions_dropped_total.labels(reason="confidence_not_a_number").inc()
            dropped += 1
            continue

        reason = str(getattr(entry, "reason", "") or "").strip()
        if not reason:
            advisor_suggestions_dropped_total.labels(reason="empty_reason").inc()
            dropped += 1
            continue

        seen.add(dataset_id)
        suggestions.append(
            DatasetSuggestion(
                dataset_id=dataset_id,
                name=known_ids[dataset_id],
                reason=reason[:_REASON_LIMIT],
                confidence=round(confidence, 2),
            )
        )

    return suggestions[:SUGGESTION_CAP], dropped


async def suggest_datasets(
    prompt_body: str,
    catalogue: list[tuple[str, str, str | None, str]],
    *,
    prompt_title: str = "",
    workspace_id: str = "",
    cache: Cache | None = None,
) -> tuple[DatasetSuggestion, ...]:
    """Ask the app agent which catalogue sets this body should be measured with.

    ``catalogue`` rows are ``(dataset_id, name, applicability, description)`` —
    the same metadata a person reads in the tree. Advice, never a write: the
    answer is a ranked list of proposals and attaching one is the person's own
    tick. Raises :class:`AdvisorUnavailableError` when the call cannot run; an
    empty return is a *successful* call that judged nothing truly relevant,
    which is the answer the old scorer was structurally unable to give.

    ``cache`` is the App-Agent LLM cache seam (design pack
    ``docs/agent-design/cache/``). ``None`` (the default) is a no-op cache, so
    callers that do not pass one are byte-identical to before. When a cache is
    passed, the same body + catalogue + program version produce the same key,
    and a hit is served after re-running the gate — a cached answer is
    byte-identical to a fresh one (05-D1). A cache failure is never a failed
    suggestion: a read failure is a miss, a write failure returns the fresh
    answer (07-D3).
    """
    agent = await _load_agent()
    program = agent.build_program()
    known_ids = {dataset_id: name for dataset_id, name, _, _ in catalogue}
    catalogue_block = _catalogue_block(catalogue)
    feature = "suggest_datasets"
    cache = cache or NoOpCache()

    key = compute_key(
        prompt_body=prompt_body,
        prompt_title=prompt_title,
        catalogue=catalogue_block,
    )

    try:
        cached = await cache.get(key)
    except Exception:
        # A read failure is a miss, never a failed suggestion (07-D3). The
        # error is counted so a broken cache is visible, then the call runs.
        llm_cache_errors_total.labels(feature=feature, op="read").inc()
        llm_cache_total.labels(feature=feature, result="miss_degraded").inc()
        cached = None

    if cached is not None:
        raw_findings, meta = cached
        gated, dropped = _gated(raw_findings, known_ids)
        if gated or not dropped:
            # A row whose stored prediction survives the same gate a fresh
            # answer goes through (05-D1). The gate is the only judge; the
            # cache never widens it.
            llm_cache_total.labels(feature=feature, result="hit").inc()
            llm_cache_cost_saved_usd_total.labels(feature=feature).inc(
                cost_usd({"input": meta.input_tokens, "output": meta.output_tokens})
            )
            log.info(
                "evaluation.datasets_suggested",
                workspace_id=workspace_id,
                model_name=meta.model,
                suggestion_count=len(gated),
                dropped=dropped,
                cached=True,
                input_tokens=0,
                output_tokens=0,
            )
            return tuple(gated)
        # A poisoned row: stored content that no longer survives the gate. It is
        # dropped and counted, never served (03-D5, 01-D6).
        llm_cache_total.labels(feature=feature, result="miss_stale").inc()

    async def invoke() -> Any:
        with agent.usage_tracking():
            return await program.aforward(
                prompt_title=prompt_title,
                prompt_body=prompt_body,
                catalogue=catalogue_block,
            )

    try:
        prediction = await _breaker.call(invoke)
    except CircuitOpenError as error:
        advisor_total.labels(outcome="refused").inc()
        raise AdvisorUnavailableError("the advising agent is in a failing state") from error
    except Exception as error:
        advisor_total.labels(outcome="error").inc()
        raise AdvisorUnavailableError(str(error)) from error

    usage = agent.usage_of(prediction)
    advisor_cost_usd_total.inc(agent.cost_usd(usage))

    gated, dropped = _gated(
        getattr(prediction, "suggestions", None),
        known_ids,
    )
    advisor_total.labels(outcome="ok" if gated else "empty").inc()

    if cached is None:
        llm_cache_total.labels(feature=feature, result="miss").inc()

    try:
        await cache.put(
            key,
            [
                {
                    "dataset_id": item.dataset_id,
                    "name": item.name,
                    "reason": item.reason,
                    "confidence": item.confidence,
                }
                for item in gated
            ],
            CacheMeta(
                program=feature,
                model=APP_AGENT_MODEL,
                input_tokens=usage.get("input", 0),
                output_tokens=usage.get("output", 0),
            ),
        )
        llm_cache_put_total.labels(feature=feature, result="stored").inc()
    except Exception:
        # The fresh answer is in hand; a failed write must not lose it (07-D3).
        llm_cache_errors_total.labels(feature=feature, op="write").inc()
        llm_cache_put_total.labels(feature=feature, result="write_failed").inc()

    log.info(
        "evaluation.datasets_suggested",
        workspace_id=workspace_id,
        model_name=APP_AGENT_MODEL,
        suggestion_count=len(gated),
        dropped=dropped,
        input_tokens=usage.get("input", 0),
        output_tokens=usage.get("output", 0),
    )

    return tuple(gated)


@dataclass(frozen=True, slots=True)
class AdviceFinding:
    suite_name: str
    assertion_type: str
    failed: int
    total: int
    issue: str
    advice: str
    severity: str


_ADVICE: Final[dict[str, tuple[str, str]]] = {
    AssertionType.REGEX.value: (
        "Câu trả lời vi phạm mẫu kiểm tra (regex).",
        "Rà lại phần chỉ thị chi phối hình thức câu trả lời: nêu rõ điều không được làm và cách từ chối tường minh khi case thuộc bộ red-team.",
    ),
    AssertionType.FORBIDDEN_PHRASE.value: (
        "Câu trả lời chứa cụm bị cấm.",
        "Liệt kê tường minh trong prompt những cụm/ký hiệu không được xuất hiện và hướng dẫn cách xử lý thay thế.",
    ),
    AssertionType.REQUIRED_PHRASE.value: (
        "Câu trả lời thiếu thành phần bắt buộc.",
        "Yêu cầu tường minh trong prompt về thông tin hoặc thành phần phải có trong mọi câu trả lời.",
    ),
    AssertionType.JSON_SCHEMA.value: (
        "Đầu ra lệch schema.",
        "Siết phần <output_format>: liệt kê các trường bắt buộc, kiểu dữ liệu và cấm văn xuôi bọc ngoài JSON.",
    ),
    AssertionType.MAX_LENGTH.value: (
        "Câu trả lời vượt độ dài cho phép.",
        "Thêm giới hạn độ dài hoặc số câu tường minh, và yêu cầu bỏ phần lan man không cần thiết.",
    ),
    AssertionType.MAX_LATENCY.value: (
        "Vượt trần độ trễ.",
        "Xem lại cấu hình provider/model và độ dài đầu vào thay vì nội dung prompt — độ trễ hiếm khi do văn bản.",
    ),
    AssertionType.MAX_COST.value: (
        "Vượt trần chi phí.",
        "Rà lại model được gắn và số token đầu vào; cân nhắc rút gọn ngữ cảnh tĩnh trong prompt.",
    ),
}
_GENERIC_ADVICE: Final = (
    "Case không đạt.",
    "Đọc chi tiết case trong lần chạy để xác định đúng điều kiện bị trượt, rồi siết chỉ thị tương ứng trong prompt.",
)
_ERROR_ADVICE: Final = (
    "Case lỗi thực thi thay vì trượt điều kiện.",
    "Kiểm tra provider binding và dạng đầu ra (modality) của prompt với bộ dữ liệu trước khi đọc tiếp kết quả.",
)


def _advice_for(assertion_type: str, errored: bool) -> tuple[str, str]:
    if errored:
        return _ERROR_ADVICE
    return _ADVICE.get(assertion_type, _GENERIC_ADVICE)


def analyze_runs(
    runs: list[tuple[str, str, int, int, int]],
    case_results: list[tuple[str, list[tuple[bool, str, bool]]]],
) -> tuple[str, tuple[AdviceFinding, ...]]:
    """Turn terminal runs into a brief and per-group findings.

    ``runs`` rows are ``(suite_name, status, passed, failed, errors)``; each
    ``case_results`` row is ``(suite_name, [(passed, assertion_type, errored), ...])``
    — one entry per assertion result of the run's cases. Grouping is by suite and
    assertion type, because that is the level a prompt edit can act on.
    """
    if not runs:
        return (
            "Chưa có lần chạy hoàn thành nào cho revision này. Hãy gắn bộ dữ liệu và chạy thử trước.",
            (),
        )

    total_cases = sum(passed + failed + errors for _, _, passed, failed, errors in runs)
    total_failed = sum(failed + errors for _, _, passed, failed, errors in runs)
    worst = max(runs, key=lambda run: run[2] + run[3] + run[4])

    groups: dict[tuple[str, str], list[tuple[bool, str, bool]]] = {}
    for suite_name, results in case_results:
        for passed, assertion_type, errored in results:
            if passed:
                continue
            groups.setdefault((suite_name, assertion_type), []).append((passed, assertion_type, errored))

    findings: list[AdviceFinding] = []
    for (suite_name, assertion_type), entries in groups.items():
        issue, advice = _advice_for(assertion_type, any(errored for _, _, errored in entries))
        share = len(entries) / total_cases if total_cases else 0.0
        findings.append(
            AdviceFinding(
                suite_name=suite_name,
                assertion_type=assertion_type,
                failed=len(entries),
                total=total_cases,
                issue=issue,
                advice=advice,
                severity="warning" if share >= 0.1 else "advice",
            )
        )
    findings.sort(key=lambda item: item.failed, reverse=True)

    if len(runs) == 1 and total_failed == 0:
        brief = (
            f"Lượt chạy này đã hoàn thành với {total_cases} case, không có case nào trượt. "
            "Không có gợi ý chỉnh sửa nào cần thiết tại thời điểm này."
        )
    elif len(runs) == 1:
        brief = (
            f"{total_failed}/{total_cases} case chưa đạt trong lượt chạy này, bộ kiểm thử “{worst[0]}”. "
            f"{len(findings)} nhóm vấn đề theo điều kiện kiểm tra — xử lý nhóm nhiều case trượt nhất trước, "
            "mỗi nhóm gợi ý một sửa đổi cụ thể cho prompt."
        )
    elif total_failed == 0:
        brief = (
            f"{len(runs)} lần chạy đã hoàn thành với {total_cases} case, không có case nào trượt. "
            "Không có gợi ý chỉnh sửa nào cần thiết tại thời điểm này."
        )
    else:
        brief = (
            f"{total_failed}/{total_cases} case chưa đạt qua {len(runs)} lần chạy; bộ nặng nhất là "
            f"“{worst[0]}”. {len(findings)} nhóm vấn đề được gộp theo điều kiện kiểm tra — xử lý nhóm "
            "nhiều case trượt nhất trước, mỗi nhóm gợi ý một sửa đổi cụ thể cho prompt."
        )
    return brief, tuple(findings)
