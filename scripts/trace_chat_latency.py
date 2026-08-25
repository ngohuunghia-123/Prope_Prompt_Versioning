#!/usr/bin/env python
"""Where a chat turn's seconds actually go.

`chat_orchestrator` spends a turn in a serial chain of model calls — router,
then whatever the plan's workers need, then the responder — and every one of
them is a full non-streaming generation. Langfuse records each call, but it
records them as separate observations under separate trace names, so the one
number nobody has is *the split*: how much of a 40 s import turn is the router,
how much is the 12k-token conversion, how much is the reply.

This script measures that split directly, without the database, the broker, or
a browser. It reads the same environment the app reads — every setting through
`os.getenv()`, exactly as `client.py` and `dspy_program.py` do — reports what it
found, then times each stage against the live gateway.

    python scripts/trace_chat_latency.py                 # config only, no calls
    python scripts/trace_chat_latency.py --trace         # one pass over every stage
    python scripts/trace_chat_latency.py --trace -n 5    # five passes, for variance
    python scripts/trace_chat_latency.py --trace --only router,responder

**Import order is load-bearing.** `prope.app_agent.client` and
`prope.chat_orchestrator.dspy_program` read `os.getenv()` into module-level
`Final` constants *at import time*: `APP_AGENT_MODEL`, `ROUTER_MODEL`,
`MAX_ROUTER_TOKENS` and the rest are resolved once and never re-read. So the
`.env` file is parsed and pushed into `os.environ` before the first `prope`
import, and `_env()` below is the only reader either side of that line.

**Nothing customer-written goes in or out.** Every fixture is synthetic
Vietnamese written for this file, secrets are reported as set/unset and never
printed, and no stage prints a model's output — only counts, tokens and
seconds. A-020 applies to a diagnostic as much as to a trace.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# The development host is Windows, where the console defaults to cp1252 and
# turns every em-dash in this file's output into a replacement glyph. The
# product is Vietnamese; a diagnostic that cannot print its own notes is a
# diagnostic somebody stops reading.
for _stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(_stream, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # pragma: no cover - a stream that will not retune
            pass


# ---------------------------------------------------------------------------
# The environment, read before anything imports it
# ---------------------------------------------------------------------------


def load_env_file(path: Path, *, override: bool = False) -> int:
    """Push a `.env` into `os.environ`. Returns how many keys it set.

    Deliberately minimal — no `python-dotenv`, which is not in the dependency
    set and would be a new install for a diagnostic. `KEY=VALUE`, `#` comments,
    optional surrounding quotes, `export` prefix tolerated. An already-exported
    shell variable wins unless `--override-env` says otherwise, because that is
    how you point this at staging without editing a file.
    """
    if not path.is_file():
        return 0

    applied = 0
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, separator, value = line.partition("=")
        if not separator:
            continue
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if not key:
            continue
        if key in os.environ and not override:
            continue
        os.environ[key] = value
        applied += 1
    return applied


def _env(name: str, default: str = "") -> str:
    """One reader for every setting, so the report cannot drift from the app."""
    return os.getenv(name, default)


@dataclass(frozen=True, slots=True)
class Setting:
    name: str
    value: str
    secret: bool = False
    note: str = ""

    def rendered(self) -> str:
        if self.secret:
            return f"set ({len(self.value)} chars)" if self.value else "UNSET"
        return self.value if self.value else "UNSET"


#: Every environment variable the chat path actually reads, grouped the way the
#: latency question is asked. The `note` column is what the value *means* for a
#: turn's wall clock — a config dump nobody can act on is a config dump.
SETTING_GROUPS: tuple[tuple[str, tuple[tuple[str, bool, str], ...]], ...] = (
    (
        "gateway",
        (
            ("APP_OPENAI_BASE_URL", False, "where every chat completion goes"),
            ("APP_OPENAI_API_KEY", True, ""),
            ("APP_AGENT_MODEL", False, "the default behind all three programs"),
            ("LANGFUSE_BASE_URL", False, "managed prompts + traces"),
            ("LANGFUSE_HOST", False, "fallback for LANGFUSE_BASE_URL"),
            ("LANGFUSE_PUBLIC_KEY", True, ""),
            ("LANGFUSE_SECRET_KEY", True, ""),
        ),
    ),
    (
        "per-program model overrides",
        (
            ("CHAT_ROUTER_MODEL", False, "unset = APP_AGENT_MODEL; a classification"),
            ("CHAT_REPLY_MODEL", False, "unset = APP_AGENT_MODEL; prose in Vietnamese"),
            ("CHAT_DRAFT_MODEL", False, "unset = APP_AGENT_MODEL; rewrites a whole body"),
        ),
    ),
    (
        "output budgets",
        (
            ("CHAT_ROUTER_MAX_OUTPUT_TOKENS", False, "default 2048 — a thinking tier spends most of it unseen"),
            ("CHAT_REPLY_MAX_OUTPUT_TOKENS", False, "default 3000"),
            ("CHAT_DRAFT_MAX_OUTPUT_TOKENS", False, "default 4000"),
            ("APP_AGENT_MAX_OUTPUT_TOKENS", False, "default 12000 — prompt-conversion, longest call in a turn"),
        ),
    ),
    (
        "input budgets",
        (
            ("CHAT_EVIDENCE_CHAR_LIMIT", False, "default 6000 — responder prefill"),
            ("CHAT_HISTORY_CHAR_LIMIT", False, "default 1200 — router prefill"),
            ("CHAT_THREAD_ENTITY_LIMIT", False, "default 4"),
        ),
    ),
    (
        "reliability",
        (
            ("CHAT_ROUTER_EXTRA_BODY", False, "vendor JSON merged into the router call; empty sends nothing"),
            ("CHAT_ROUTER_NUM_RETRIES", False, "default 1; the orchestrator adds one visible retry on top"),
            ("CHAT_ROUTER_TIMEOUT_SECONDS", False, "default 30 — the router's own ceiling"),
            ("CHAT_WARMUP_PING", False, "default 1 — pays TLS setup at boot, not at first message"),
        ),
    ),
    (
        "embeddings",
        (
            ("EMBEDDING_BASE_URL", False, "unset = APP_OPENAI_BASE_URL"),
            ("EMBEDDING_API_KEY", True, ""),
            ("EMBEDDING_MODEL", False, "unset = APP_EMBEDDING_MODEL"),
            ("APP_EMBEDDING_MODEL", False, ""),
            ("EMBEDDING_DIMENSIONS", False, "default 1536; empty omits the parameter"),
            ("EMBEDDING_TIMEOUT_SECONDS", False, "default 30 — a cold docs corpus can use most of it"),
        ),
    ),
    (
        "research leg",
        (
            ("CHAT_RESEARCH_API_URL", False, "unset = research_topic always answers unavailable"),
            ("CHAT_RESEARCH_API_KEY", True, ""),
            ("CHAT_RESEARCH_ALLOWED_DOMAINS", False, ""),
        ),
    ),
    (
        "cost accounting",
        (
            ("APP_AGENT_PRICE_INPUT_PER_MTOK", False, "default 0.15 (gpt-4o-mini)"),
            ("APP_AGENT_PRICE_OUTPUT_PER_MTOK", False, "default 0.60 (gpt-4o-mini)"),
        ),
    ),
)


#: Model families that think before they answer. Matched loosely and on purpose:
#: the point is to raise the question, not to be an authority on model naming.
#: A reasoning tier behind a routing call spends most of its latency and most of
#: `max_tokens` on tokens nobody reads.
_THINKING_MARKERS: tuple[str, ...] = (
    "gemini-2.5",
    "gemini-3",
    "o1",
    "o3",
    "o4",
    "deepseek-r",
    "qwen3",
    "thinking",
    "reasoner",
)


def _thinking_tier(model: str) -> bool:
    name = model.lower()
    return any(marker in name for marker in _THINKING_MARKERS)


def report_config() -> list[str]:
    """Print every setting through `os.getenv()`. Returns warnings worth acting on."""
    warnings: list[str] = []

    for group, entries in SETTING_GROUPS:
        print(f"\n  {group}")
        for name, secret, note in entries:
            setting = Setting(name=name, value=_env(name), secret=secret, note=note)
            suffix = f"   # {note}" if note else ""
            print(f"    {name:<34} {setting.rendered()}{suffix}")

    agent_model = _env("APP_AGENT_MODEL", "gpt-4o-mini")
    router_model = _env("CHAT_ROUTER_MODEL") or agent_model
    reply_model = _env("CHAT_REPLY_MODEL") or agent_model
    draft_model = _env("CHAT_DRAFT_MODEL") or agent_model

    print("\n  effective models")
    print(f"    router                             {router_model}")
    print(f"    responder                          {reply_model}")
    print(f"    drafter                            {draft_model}")
    print(f"    prompt-conversion                  {agent_model}")

    if not _env("APP_OPENAI_API_KEY"):
        warnings.append("APP_OPENAI_API_KEY is unset — --trace cannot reach the gateway.")
    if router_model == reply_model == draft_model == agent_model:
        warnings.append(
            "All four programs share one model. The router is a six-way classification "
            "and does not need the answering tier — CHAT_ROUTER_MODEL is the lever."
        )
    if _thinking_tier(router_model) and not _env("CHAT_ROUTER_EXTRA_BODY"):
        warnings.append(
            f"The router runs on '{router_model}', a reasoning tier, and "
            "CHAT_ROUTER_EXTRA_BODY is unset — so it is thinking at full budget before "
            "every four-field classification, which is what the 'router burning 5-57s "
            "for 60-90 tokens' comment in dspy_program.py is watching. Find the "
            "spelling your gateway accepts and set it; `--trace --only thinking` "
            "measures whether it actually bites."
        )
    if agent_model != "gpt-4o-mini" and not (
        _env("APP_AGENT_PRICE_INPUT_PER_MTOK") and _env("APP_AGENT_PRICE_OUTPUT_PER_MTOK")
    ):
        warnings.append(
            f"APP_AGENT_MODEL is '{agent_model}' but the price constants are still "
            "gpt-4o-mini's defaults, so prope_*_cost_usd_total is a wrong number that "
            "looks maintained — dspy_runtime.py's own docstring names this failure."
        )
    if _thinking_tier(router_model) and _env("CHAT_ROUTER_EXTRA_BODY"):
        warnings.append(
            "CHAT_ROUTER_EXTRA_BODY is set against a reasoning tier. Confirm it is not "
            "a no-op — providers accept and silently ignore each other's spellings. "
            "`--trace --only thinking` A/Bs it against no parameter at all."
        )
    if not _env("CHAT_RESEARCH_API_URL"):
        warnings.append("CHAT_RESEARCH_API_URL is unset — research_topic is a no-op in this deployment.")
    if _env("CHAT_WARMUP_PING", "1") != "1":
        warnings.append("CHAT_WARMUP_PING is off — the first message after a deploy pays TLS setup.")

    return warnings


# ---------------------------------------------------------------------------
# Fixtures. Synthetic, written for this file, never a customer's text.
# ---------------------------------------------------------------------------

FIXTURE_MESSAGE = "Đổi tên prompt hỗ trợ khách hàng thành 'Trợ lý hoàn tiền' rồi chuyển nó vào thư mục Marketing"
FIXTURE_HISTORY = "Cho tôi xem các prompt về hoàn tiền\nPrompt nào đang được phát hành?"
FIXTURE_QUESTION = "Quy trình phê duyệt trước khi phát hành hoạt động như thế nào?"
FIXTURE_INSTRUCTION = "Bổ sung phần chống prompt injection và nói rõ định dạng đầu ra"

FIXTURE_BODY = (
    "<system>Bạn là trợ lý chăm sóc khách hàng của một cửa hàng trực tuyến.</system>\n"
    "<instructions>Trả lời ngắn gọn, lịch sự, bằng tiếng Việt. "
    "Khi khách hỏi về hoàn tiền, hãy hỏi mã đơn hàng trước.</instructions>\n"
    "<constraints>Không hứa hẹn thời gian hoàn tiền cụ thể.</constraints>"
)

FIXTURE_SOURCE = (
    "You are a customer support assistant for an online store.\n"
    "Always answer in Vietnamese, politely and briefly.\n"
    "When the customer asks about a refund, ask for the order number first.\n"
    "Never promise a specific refund date.\n"
    "Output: a short paragraph, then a bulleted list of next steps."
)

FIXTURE_EVIDENCE = "\n\n".join(
    f"[E{n}] (prompt) Prompt mẫu số {n} — mô tả ngắn gọn cho mục đích đo thời gian." for n in range(1, 5)
)

FIXTURE_SITUATION = "search_prompts: ok (4 kết quả). Không có đề xuất nào đang chờ xác nhận."


# ---------------------------------------------------------------------------
# Samples
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Sample:
    stage: str
    seconds: float
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    error: str = ""
    extra: str = ""

    @property
    def ok(self) -> bool:
        return not self.error

    @property
    def output_per_second(self) -> float:
        return self.output_tokens / self.seconds if self.seconds > 0 and self.output_tokens else 0.0


@dataclass(slots=True)
class Recorder:
    samples: list[Sample] = field(default_factory=list)

    def add(self, sample: Sample) -> Sample:
        self.samples.append(sample)
        marker = "ok " if sample.ok else "ERR"
        detail = ""
        if sample.ok and (sample.input_tokens or sample.output_tokens):
            detail = (
                f"  in={sample.input_tokens:<6} out={sample.output_tokens:<5} out/s={sample.output_per_second:6.1f}"
            )
        if sample.extra:
            detail += f"  {sample.extra}"
        if sample.error:
            detail = f"  {sample.error}"
        print(f"    {marker} {sample.stage:<22} {sample.seconds:7.2f}s{detail}")
        return sample

    def for_stage(self, stage: str) -> list[Sample]:
        return [s for s in self.samples if s.stage == stage and s.ok]

    def median(self, stage: str) -> float | None:
        values = [s.seconds for s in self.for_stage(stage)]
        return statistics.median(values) if values else None


async def timed(stage: str, coro_factory, *, model: str = "") -> Sample:
    """One stage, wall-clocked, never raising past this frame."""
    started = time.perf_counter()
    try:
        prediction = await coro_factory()
    except Exception as exc:  # noqa: BLE001 - a broken stage must not end the run
        return Sample(
            stage=stage,
            seconds=time.perf_counter() - started,
            model=model,
            error=f"{type(exc).__name__}: {str(exc)[:160]}",
        )
    elapsed = time.perf_counter() - started

    from prope.app_agent.dspy_runtime import usage_of

    usage = usage_of(prediction) if prediction is not None else {}
    return Sample(
        stage=stage,
        seconds=elapsed,
        model=model,
        input_tokens=int(usage.get("input", 0)),
        output_tokens=int(usage.get("output", 0)),
    )


# ---------------------------------------------------------------------------
# The stages
# ---------------------------------------------------------------------------


async def stage_warm(recorder: Recorder) -> None:
    """The gateway handshake, paid once. `warm_chat_agent`'s ping, measured."""
    from prope.chat_orchestrator import dspy_program
    from prope.chat_orchestrator.prompting import load_router_prompt

    started = time.perf_counter()
    try:
        prompt = await asyncio.to_thread(load_router_prompt)
        program = dspy_program.build_router_program(prompt.text)
        lm = program.route.lm
        if lm is None:
            raise RuntimeError("router program has no LM")
        await asyncio.to_thread(lm, "ping", max_tokens=512)
    except Exception as exc:  # noqa: BLE001
        recorder.add(
            Sample(
                stage="warm (ping)",
                seconds=time.perf_counter() - started,
                error=f"{type(exc).__name__}: {str(exc)[:160]}",
            )
        )
        return
    recorder.add(Sample(stage="warm (ping)", seconds=time.perf_counter() - started))


async def stage_prompts(recorder: Recorder) -> None:
    """Resolving the three managed instructions — on the critical path, every turn.

    Not a warm-up cost, which is the trap. `_run_turn` calls `load_router_prompt`
    before routing and `load_responder_prompt` before answering, on **every**
    turn; `drafter.draft_revision` calls the third. `_load` passes
    `cache_ttl_seconds=300`, so the intended cost is one fetch per five minutes.

    That holds only while the prompt EXISTS. On a 404 the Langfuse SDK evicts the
    entry rather than caching the negative — "not found during refresh, evicting
    from cache" — so a project that was never seeded refetches, 404s and evicts
    on every single call, forever. Two blocking round-trips to Langfuse per turn,
    before a token is generated. That is what these numbers are for: read them as
    per-turn, not per-process, whenever the source column says FALLBACK.
    """
    from prope.chat_orchestrator.prompting import (
        load_drafter_prompt,
        load_responder_prompt,
        load_router_prompt,
    )

    for label, loader in (
        ("prompt: router", load_router_prompt),
        ("prompt: responder", load_responder_prompt),
        ("prompt: drafter", load_drafter_prompt),
    ):
        started = time.perf_counter()
        try:
            managed = await asyncio.to_thread(loader)
        except Exception as exc:  # noqa: BLE001
            recorder.add(
                Sample(
                    stage=label,
                    seconds=time.perf_counter() - started,
                    error=f"{type(exc).__name__}: {str(exc)[:160]}",
                )
            )
            continue
        source = "FALLBACK (compiled in)" if managed.is_fallback else f"langfuse v{managed.version or '?'}"
        recorder.add(Sample(stage=label, seconds=time.perf_counter() - started, extra=source))


async def stage_router_with_drop_check(recorder: Recorder) -> None:
    """The router, plus what `routing_of` deleted from its answer.

    This is the measurement the Langfuse trace cannot give you: the router's
    raw `tools` list beside the plan that survived the intent gate and the
    one-write truncation. A turn that asked for three tools and ran one looks
    identical to a turn that asked for one, because only the survivor is traced.
    """
    from prope.app_agent.dspy_runtime import usage_of, usage_tracking
    from prope.chat_orchestrator import dspy_program
    from prope.chat_orchestrator.prompting import load_router_prompt

    prompt = await asyncio.to_thread(load_router_prompt)
    program = dspy_program.build_router_program(prompt.text)

    started = time.perf_counter()
    try:
        with usage_tracking():
            prediction = await program.acall(
                catalogue=dspy_program.catalogue_text(),
                history=dspy_program.truncate_history(FIXTURE_HISTORY.splitlines()),
                message=FIXTURE_MESSAGE,
                has_attachment=False,
                recent_actions="",
                thread_state="",
            )
    except Exception as exc:  # noqa: BLE001
        recorder.add(
            Sample(
                stage="router",
                seconds=time.perf_counter() - started,
                model=dspy_program.ROUTER_MODEL,
                error=f"{type(exc).__name__}: {str(exc)[:160]}",
            )
        )
        return

    elapsed = time.perf_counter() - started
    usage = usage_of(prediction)

    asked = [str(item) for item in (getattr(prediction, "tools", None) or []) if isinstance(item, str)]
    decision = dspy_program.routing_of(prediction)
    kept = [str(name) for name in decision.tools]
    # Deferred is not dropped: the one-write rule moves the remaining writes
    # onto `deferred`, and `_remaining_plan` queues them behind the first card.
    # Counting them as losses would have this diagnostic reporting a bug that
    # was fixed, which is the same failure it exists to catch.
    deferred = [str(name) for name in decision.deferred]
    dropped = [name for name in asked if name not in kept and name not in deferred]

    extra = f"intent={decision.intent} asked={len(asked)} kept={len(kept)}"
    if deferred:
        extra += f" queued={','.join(deferred)}"
    if dropped:
        extra += f" DROPPED={','.join(dropped)}"

    recorder.add(
        Sample(
            stage="router",
            seconds=elapsed,
            model=dspy_program.ROUTER_MODEL,
            input_tokens=int(usage.get("input", 0)),
            output_tokens=int(usage.get("output", 0)),
            extra=extra,
        )
    )


async def stage_responder(recorder: Recorder) -> None:
    """One real reply call, on synthetic evidence at a realistic size."""
    from prope.app_agent.dspy_runtime import usage_tracking
    from prope.chat_orchestrator import dspy_program
    from prope.chat_orchestrator.prompting import load_responder_prompt

    prompt = await asyncio.to_thread(load_responder_prompt)
    program = dspy_program.build_reply_program(prompt.text)

    async def call():
        with usage_tracking():
            return await program.acall(
                question=FIXTURE_QUESTION,
                evidence=FIXTURE_EVIDENCE,
                situation=FIXTURE_SITUATION,
            )

    sample = await timed("responder", call, model=dspy_program.REPLY_MODEL)
    sample.extra = f"budget={dspy_program.MAX_REPLY_TOKENS}"
    recorder.add(sample)


async def stage_drafter(recorder: Recorder) -> None:
    """One real drafting call — the `create_revision` proposal path."""
    from prope.chat_orchestrator import drafter, dspy_program

    async def call():
        return await drafter.draft_revision(
            current_body=FIXTURE_BODY,
            current_version_id="ver_trace_fixture",
            instruction=FIXTURE_INSTRUCTION,
            research_notes="",
        )

    sample = await timed("drafter", call, model=dspy_program.DRAFT_MODEL)
    # `draft_revision` returns a DraftedRevision, not a Prediction, so usage is
    # not recoverable here — the seconds are the point.
    sample.extra = f"budget={dspy_program.MAX_DRAFT_TOKENS}"
    recorder.add(sample)


async def stage_convert(recorder: Recorder) -> None:
    """One real conversion — the longest model call a turn can make."""
    from prope.app_agent.client import APP_AGENT_MODEL
    from prope.prompt_conversion.dspy_program import MAX_OUTPUT_TOKENS
    from prope.prompt_conversion.service import ConversionContext, convert_source

    async def call():
        return await convert_source(
            FIXTURE_SOURCE,
            "txt",
            context=ConversionContext(
                workspace_id="ws_trace_fixture",
                actor_id="usr_trace_fixture",
                prompt_id=None,
            ),
        )

    sample = await timed("convert_prompt", call, model=APP_AGENT_MODEL)
    sample.extra = f"budget={MAX_OUTPUT_TOKENS}"
    recorder.add(sample)


async def stage_embedding(recorder: Recorder) -> None:
    """One query embedding. What `search_prompts` pays per call once warm."""
    from prope.app_agent.client import EMBEDDING_MODEL, embedding_request, get_embedding_client

    started = time.perf_counter()
    try:
        client = await get_embedding_client()
        request = embedding_request(FIXTURE_QUESTION)
        await client.embeddings.create(**request)
    except Exception as exc:  # noqa: BLE001
        recorder.add(
            Sample(
                stage="embed (query)",
                seconds=time.perf_counter() - started,
                model=EMBEDDING_MODEL,
                error=f"{type(exc).__name__}: {str(exc)[:160]}",
            )
        )
        return
    recorder.add(Sample(stage="embed (query)", seconds=time.perf_counter() - started, model=EMBEDDING_MODEL))


async def stage_docs(recorder: Recorder) -> None:
    """`answer_from_docs`, cold then warm.

    `warm_chat_agent` warms the three managed prompts and pings the router LM,
    but leaves `knowledge._vectors` empty — so the first documentation question
    after every deploy embeds the whole corpus *and* the query, serially, at a
    30 s timeout. Both numbers below are real; the gap between them is what one
    line in the warm-up would save, once per deploy, for whoever asks first.
    """
    from prope.chat_orchestrator import knowledge

    knowledge._vectors.clear()  # noqa: SLF001 - measuring the cold path is the point

    started = time.perf_counter()
    try:
        outcome = await knowledge.retrieve(FIXTURE_QUESTION, limit=4)
    except Exception as exc:  # noqa: BLE001
        recorder.add(
            Sample(
                stage="docs (cold corpus)",
                seconds=time.perf_counter() - started,
                error=f"{type(exc).__name__}: {str(exc)[:160]}",
            )
        )
        return
    recorder.add(
        Sample(
            stage="docs (cold corpus)",
            seconds=time.perf_counter() - started,
            extra=f"chunks={len(outcome.chunks)} dense={'yes' if outcome.dense_ran else 'NO (lexical only)'}",
        )
    )

    started = time.perf_counter()
    outcome = await knowledge.retrieve(FIXTURE_QUESTION, limit=4)
    recorder.add(
        Sample(
            stage="docs (warm corpus)",
            seconds=time.perf_counter() - started,
            extra=f"chunks={len(outcome.chunks)} dense={'yes' if outcome.dense_ran else 'NO (lexical only)'}",
        )
    )


async def stage_ttft(recorder: Recorder) -> None:
    """Time to first token vs total, on the responder's model.

    The one number that decides whether streaming the reply is worth building.
    DSPy's `Predict` is not a streaming call, so the whole reply lands at once
    and the person waits the full generation staring at a spinner. This probe
    asks the same model the same shape of question with `stream=True` and
    records both halves: TTFT is what the person *would* wait, total is what
    they wait today.
    """
    from openai import AsyncOpenAI

    from prope.app_agent.client import APP_OPENAI_API_KEY, APP_OPENAI_BASE_URL
    from prope.chat_orchestrator import dspy_program

    client = AsyncOpenAI(
        base_url=APP_OPENAI_BASE_URL,
        api_key=APP_OPENAI_API_KEY,
        max_retries=0,
        timeout=120.0,
    )

    started = time.perf_counter()
    first_token_at: float | None = None
    chunks = 0
    try:
        stream = await client.chat.completions.create(
            model=dspy_program.REPLY_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Trả lời bằng tiếng Việt trong khoảng 200 từ: "
                        "quy trình phê duyệt trước khi phát hành một prompt gồm những bước nào?"
                    ),
                }
            ],
            max_tokens=dspy_program.MAX_REPLY_TOKENS,
            temperature=0.0,
            stream=True,
        )
        async for event in stream:
            choices = getattr(event, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            content = getattr(delta, "content", None) if delta is not None else None
            if content:
                chunks += 1
                if first_token_at is None:
                    first_token_at = time.perf_counter()
    except Exception as exc:  # noqa: BLE001
        recorder.add(
            Sample(
                stage="stream probe",
                seconds=time.perf_counter() - started,
                model=dspy_program.REPLY_MODEL,
                error=f"{type(exc).__name__}: {str(exc)[:160]}",
            )
        )
        return
    finally:
        await client.close()

    total = time.perf_counter() - started
    ttft = (first_token_at - started) if first_token_at is not None else total
    recorder.add(
        Sample(
            stage="stream probe",
            seconds=total,
            model=dspy_program.REPLY_MODEL,
            extra=f"TTFT={ttft:.2f}s  deltas={chunks}  hidden_wait={total - ttft:.2f}s",
        )
    )


#: Rounds per arm for the extra-body A/B. Small because the effect worth finding
#: usually lives in the tail rather than the median: on one gateway the two arms
#: had identical medians and differed only in whether any call took sixty
#: seconds. Small also because a blocked run of this is worthless — see below.
EXTRA_BODY_AB_ROUNDS = 8


async def stage_thinking(recorder: Recorder) -> None:
    """A/B the router with and without `CHAT_ROUTER_EXTRA_BODY`. Interleaved.

    Answers the only question that setting raises: **is it doing anything on
    this gateway?** It reads whatever is configured rather than a spelling
    compiled in here, because the shape is the provider's and providers
    disagree — one gateway took its tail from 63.8s to 3.6s on Gemini's
    `thinking_config` while the next silently ignored the identical JSON.
    A knob that quietly does nothing is the failure this stage exists to catch.

    Interleaving is the whole design. Run blocked — all of arm A, then all of
    arm B — a single bad minute at the gateway lands entirely in one arm and the
    result inverts. Two blocked runs of this disagreed with each other before
    the arms were alternated.

    Watch the output token counts as much as the seconds. Where a provider
    reports reasoning inside `completion_tokens`, a working knob shows up as a
    smaller completion for the same routing decision, and that is the cleaner
    signal: latency is noisy, token counts are not.
    """
    import dspy

    from prope.app_agent.client import APP_OPENAI_API_KEY, APP_OPENAI_BASE_URL
    from prope.app_agent.dspy_runtime import usage_of
    from prope.chat_orchestrator import dspy_program
    from prope.chat_orchestrator.prompting import load_router_prompt

    def build(extra_body: dict | None) -> dspy.LM:
        return dspy.LM(
            model=f"openai/{dspy_program.ROUTER_MODEL}",
            api_key=APP_OPENAI_API_KEY,
            api_base=APP_OPENAI_BASE_URL,
            temperature=0.0,
            max_tokens=dspy_program.MAX_ROUTER_TOKENS,
            cache=False,
            num_retries=0,
            timeout=90.0,
            **({"extra_body": extra_body} if extra_body else {}),
        )

    configured = dspy_program.router_extra_body()
    if configured is None:
        recorder.add(
            Sample(
                stage="extra_body A/B",
                seconds=0.0,
                error="CHAT_ROUTER_EXTRA_BODY is unset — nothing to compare against baseline",
            )
        )
        return

    prompt = await asyncio.to_thread(load_router_prompt)
    program = dspy_program.build_router_program(prompt.text)
    arms = {
        "router (no extra_body)": build(None),
        "router (configured)": build(configured),
    }
    print(f"      comparing against: {json.dumps(configured, separators=(',', ':'))}")

    for index in range(EXTRA_BODY_AB_ROUNDS):
        order = list(arms) if index % 2 == 0 else list(reversed(list(arms)))
        for name in order:
            program.set_lm(arms[name])
            started = time.perf_counter()
            try:
                prediction = await program.acall(
                    catalogue=dspy_program.catalogue_text(),
                    history=dspy_program.truncate_history(FIXTURE_HISTORY.splitlines()),
                    message=FIXTURE_MESSAGE,
                    has_attachment=False,
                    recent_actions="",
                    thread_state="",
                )
            except Exception as exc:  # noqa: BLE001
                recorder.add(
                    Sample(
                        stage=name,
                        seconds=time.perf_counter() - started,
                        error=f"{type(exc).__name__}: {str(exc)[:120]}",
                    )
                )
                continue
            elapsed = time.perf_counter() - started
            decision = dspy_program.routing_of(prediction)
            usage = usage_of(prediction)
            recorder.add(
                Sample(
                    stage=name,
                    seconds=elapsed,
                    model=dspy_program.ROUTER_MODEL,
                    input_tokens=int(usage.get("input", 0)),
                    output_tokens=int(usage.get("output", 0)),
                    extra=f"intent={decision.intent} kept={len(decision.tools)}",
                )
            )


STAGES: dict[str, tuple[str, object]] = {
    "warm": ("gateway handshake (once per process)", stage_warm),
    "prompts": ("managed instruction resolution", stage_prompts),
    "router": ("supervisor route + what routing_of dropped", stage_router_with_drop_check),
    "responder": ("grounded reply", stage_responder),
    "drafter": ("create_revision body draft", stage_drafter),
    "convert": ("prompt-conversion (longest call)", stage_convert),
    "embed": ("one query embedding", stage_embedding),
    "docs": ("answer_from_docs, cold then warm", stage_docs),
    "ttft": ("streaming probe: TTFT vs total", stage_ttft),
    "thinking": ("A/B: does CHAT_ROUTER_EXTRA_BODY change anything?", stage_thinking),
}

#: `thinking` is not in the default set: it is 16 calls and it answers a
#: question you ask once per gateway, not once per deploy.
DEFAULT_STAGES = ("warm", "prompts", "router", "responder", "drafter", "convert", "embed", "docs", "ttft")


# ---------------------------------------------------------------------------
# The model of a turn
# ---------------------------------------------------------------------------

#: What each turn shape actually costs, expressed in stages. Straight from
#: `orchestrator._run_turn`: rails, route, the plan's workers in order, then the
#: responder — unless `proposal_only` skips it, which is why two of these rows
#: have no responder in them.
TURN_SHAPES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("smalltalk / decision / refusal", (), "lexicon or fast path — no model call at all"),
    (
        "write proposal, no evidence",
        ("prompt_router", "router"),
        "proposal_only skips the responder",
    ),
    (
        "search or docs read",
        ("prompt_router", "router", "embed", "prompt_responder", "responder"),
        "the common answered turn",
    ),
    (
        "revision by instruction",
        ("prompt_router", "router", "prompt_drafter", "drafter"),
        "proposal_only, but the drafter is a full generation",
    ),
    (
        "import, duplicates found",
        ("prompt_router", "router", "convert", "embed", "prompt_responder", "responder"),
        "the worst turn in the product",
    ),
)


def report_model(recorder: Recorder) -> None:
    """Each turn shape's wall clock, summed from the medians actually measured.

    Rows print stacked rather than as one wide table because a six-stage turn
    does not fit a terminal in one line, and a truncated breakdown is the part
    somebody would have wanted to read.
    """
    print("\n  modelled turn cost, from the medians above")
    for label, stages, note in TURN_SHAPES:
        parts: list[str] = []
        total = 0.0
        missing = False
        for stage in stages:
            median = recorder.median(_stage_label(stage))
            if median is None:
                missing = True
                parts.append(f"{stage}=?")
                continue
            total += median
            parts.append(f"{stage}={median:.1f}")
        suffix = "   (incomplete — some stages were not traced)" if missing else ""
        print(f"\n    {label:<34} {total:>6.1f}s{suffix}")
        print(f"      {' + '.join(parts) if parts else '—'}")
        print(f"      {note}")


def _stage_label(stage: str) -> str:
    """The `Sample.stage` string a stage key records under."""
    return {
        "warm": "warm (ping)",
        "router": "router",
        "responder": "responder",
        "drafter": "drafter",
        "convert": "convert_prompt",
        "embed": "embed (query)",
        "docs": "docs (warm corpus)",
        "ttft": "stream probe",
        "prompt_router": "prompt: router",
        "prompt_responder": "prompt: responder",
        "prompt_drafter": "prompt: drafter",
    }.get(stage, stage)


def report_summary(recorder: Recorder) -> None:
    stages: list[str] = []
    for sample in recorder.samples:
        if sample.stage not in stages:
            stages.append(sample.stage)

    print("\n  per-stage summary")
    print(f"    {'stage':<22} {'n':>3} {'min':>8} {'median':>8} {'max':>8}")
    for stage in stages:
        values = [s.seconds for s in recorder.for_stage(stage)]
        if not values:
            failures = [s for s in recorder.samples if s.stage == stage]
            print(f"    {stage:<22} {'—':>3} {'':>8} {'':>8} {'':>8}  all failed: {failures[0].error}")
            continue
        print(
            f"    {stage:<22} {len(values):>3} {min(values):>7.2f}s "
            f"{statistics.median(values):>7.2f}s {max(values):>7.2f}s"
        )

    router = recorder.for_stage("router")
    if len(router) > 1:
        spread = max(s.seconds for s in router) / max(min(s.seconds for s in router), 0.001)
        if spread >= 3:
            print(
                f"\n    NOTE: the router's slowest call was {spread:.1f}x its fastest. "
                "That variance is gateway serving, not prompt size."
            )

    dropped = [s for s in recorder.samples if "DROPPED=" in s.extra]
    if dropped:
        print(
            f"\n    NOTE: routing_of deleted tools the router asked for in "
            f"{len(dropped)}/{len(recorder.for_stage('router'))} routing calls, and are not queued either. "
            "Nothing counts or traces this in production."
        )
    queued_calls = [s for s in recorder.samples if "queued=" in s.extra]
    if queued_calls:
        print(
            f"\n    NOTE: {len(queued_calls)}/{len(recorder.for_stage('router'))} routing "
            "calls deferred a write behind the confirmation card. Not losses: "
            "_remaining_plan queues them for the next approval."
        )

    fallbacks = sorted({s.stage for s in recorder.samples if "FALLBACK" in s.extra})
    if fallbacks:
        per_turn = sum(recorder.median(stage) or 0.0 for stage in ("prompt: router", "prompt: responder"))
        print(
            f"\n    NOTE: {len(fallbacks)} managed instruction(s) are NOT in Langfuse and are "
            "running the compiled-in fallback: " + ", ".join(fallbacks) + "."
        )
        print(
            "          Two consequences. (1) Prompt edits made in Langfuse have no effect on "
            "production — the text actually sent is prompting.py's FALLBACK_*."
        )
        print(
            f"          (2) A 404 evicts rather than caches, so the 300s TTL never engages: "
            f"~{per_turn:.1f}s of blocking Langfuse round-trips on EVERY turn."
        )
        print("          Fix: uv run python -m prope.chat_orchestrator.bootstrap_prompt")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def run_trace(stage_keys: list[str], repeats: int) -> Recorder:
    recorder = Recorder()

    for index in range(1, repeats + 1):
        if repeats > 1:
            print(f"\n  pass {index}/{repeats}")
        else:
            print()
        for key in stage_keys:
            _, runner = STAGES[key]
            # `warm` measures a once-per-process cost; repeating it measures a
            # warm connection, which is a different question. `prompts` is NOT
            # in that set on purpose — it is per-turn cost whenever the fetch
            # misses, and the repeats are what prove whether the TTL holds.
            if key == "warm" and index > 1:
                continue
            await runner(recorder)  # type: ignore[operator]

    return recorder


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure where a chat turn's seconds go. Reads config through os.getenv().",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="make real calls against the configured gateway (costs tokens)",
    )
    parser.add_argument(
        "-n",
        "--repeat",
        type=int,
        default=1,
        help="passes over the stage set; >1 is how you see the router's variance",
    )
    parser.add_argument(
        "--only",
        default="",
        help=f"comma-separated subset of: {', '.join(STAGES)}",
    )
    parser.add_argument(
        "--env-file",
        default=str(REPO_ROOT / ".env"),
        help="the file to read settings from (default: repo .env)",
    )
    parser.add_argument(
        "--override-env",
        action="store_true",
        help="let the file win over variables already exported in the shell",
    )
    args = parser.parse_args()

    env_path = Path(args.env_file)
    applied = load_env_file(env_path, override=args.override_env)

    print("=" * 78)
    print("  chat_orchestrator — latency trace")
    print("=" * 78)
    print(
        f"\n  env file   {env_path}  ({applied} keys applied)"
        if applied
        else f"\n  env file   {env_path}  (not read — missing, or every key already exported)"
    )

    # Everything below this line imports `prope`, which resolves its settings at
    # import time. Nothing may touch the package before the environment is set.
    src = REPO_ROOT / "src"
    if src.is_dir() and str(src) not in sys.path:
        sys.path.insert(0, str(src))

    warnings = report_config()

    if warnings:
        print("\n  worth acting on")
        for warning in warnings:
            print(f"    - {warning}")

    if not args.trace:
        print("\n  Config only. Add --trace to time the stages against the gateway.")
        print("=" * 78)
        return 0

    if not _env("APP_OPENAI_API_KEY"):
        print("\n  Refusing to --trace with no APP_OPENAI_API_KEY.")
        print("=" * 78)
        return 2

    selected = [key.strip() for key in args.only.split(",") if key.strip()] if args.only else list(DEFAULT_STAGES)
    unknown = [key for key in selected if key not in STAGES]
    if unknown:
        print(f"\n  Unknown stage(s): {', '.join(unknown)}. Choose from: {', '.join(STAGES)}")
        return 2

    print(f"\n  tracing: {', '.join(selected)}")
    print("  (real calls, real tokens — synthetic fixtures only, nothing customer-written)")

    recorder = asyncio.run(run_trace(selected, max(1, args.repeat)))

    report_summary(recorder)
    report_model(recorder)

    print("\n" + "=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
