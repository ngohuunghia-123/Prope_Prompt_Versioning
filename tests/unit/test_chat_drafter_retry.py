"""The drafter's second draw, and why it is worth paying for.

`draft_revision` is the hardest single generation the product makes — a whole
canonical prompt body, up to 32 KiB of it, against a hard token ceiling — and it
was the only model-backed step in the chat pipeline with no retry at all. The
router retries, and its job is a six-way classification.

Five models were run over the same live journey suite. The "đổi nội dung prompt"
journey failed on two of them: once because the completion never parsed
(`DraftUnavailableError`) and once because what came back was not canonical
(`DraftInvalidError`). One each of the two shapes a second draw actually
changes. Nothing here calls a model.
"""

from typing import Any

import pytest

from prope.app_agent.circuit import CircuitBreaker, CircuitOpenError
from prope.canonical_prompt import validate_canonical_xml
from prope.chat_orchestrator import drafter, dspy_program
from prope.chat_orchestrator.prompting import ManagedPrompt

BODY = "<system>Trợ lý hoàn tiền.</system><instructions>Phân loại yêu cầu hoàn tiền.</instructions>"


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    monkeypatch.setattr(drafter, "_breaker", CircuitBreaker(on_state_change=lambda _: None))
    monkeypatch.setattr(
        drafter,
        "load_drafter_prompt",
        lambda: ManagedPrompt(text="drafter", managed_prompt=None, version=1, is_fallback=False),
    )


class _Drafts:
    """A drafter program that answers each call from a scripted list."""

    def __init__(self, *answers: Any) -> None:
        self.answers = list(answers)
        self.calls = 0

    async def acall(self, **_: Any) -> Any:
        self.answers, answer = self.answers[1:], self.answers[0]
        self.calls += 1
        if isinstance(answer, Exception):
            raise answer
        return answer


def _prediction(body: str, summary: str = "Cập nhật"):
    from types import SimpleNamespace

    return SimpleNamespace(drafted_body=body, change_summary=summary)


def _wire(monkeypatch, program: _Drafts) -> None:
    monkeypatch.setattr(dspy_program, "build_draft_program", lambda _: program)


def test_the_canonical_body_the_tests_use_really_is_canonical() -> None:
    """Otherwise every assertion below passes for the wrong reason."""
    validate_canonical_xml(BODY)


async def test_a_completion_that_did_not_parse_gets_a_second_draw(monkeypatch) -> None:
    program = _Drafts(ValueError("unparseable"), _prediction(BODY))
    _wire(monkeypatch, program)

    drafted = await drafter.draft_revision(
        current_body=BODY, current_version_id="rev_1", instruction="chống prompt injection"
    )

    assert program.calls == 2
    assert drafted.body == BODY


async def test_a_body_that_came_back_short_of_canonical_gets_a_second_draw(monkeypatch) -> None:
    program = _Drafts(_prediction("<system>Trợ lý</system><role>không hợp lệ</role>"), _prediction(BODY))
    _wire(monkeypatch, program)

    drafted = await drafter.draft_revision(
        current_body=BODY, current_version_id="rev_1", instruction="chống prompt injection"
    )

    assert program.calls == 2
    assert drafted.body == BODY


async def test_two_failures_still_raise_the_shape_the_caller_handles(monkeypatch) -> None:
    """The retry adds an attempt, never a third outcome."""
    program = _Drafts(_prediction("not xml at all"), _prediction("still not xml"))
    _wire(monkeypatch, program)

    with pytest.raises(drafter.DraftInvalidError):
        await drafter.draft_revision(
            current_body=BODY, current_version_id="rev_1", instruction="chống prompt injection"
        )

    assert program.calls == 2


async def test_a_tripped_breaker_is_not_retried(monkeypatch) -> None:
    """The provider is already known to be down; a second call is pure latency."""
    calls: list[int] = []

    class _Open:
        async def call(self, _invoke: Any) -> Any:
            calls.append(1)
            raise CircuitOpenError("open")

    monkeypatch.setattr(drafter, "_breaker", _Open())
    _wire(monkeypatch, _Drafts(_prediction(BODY)))

    with pytest.raises(drafter.DraftUnavailableError):
        await drafter.draft_revision(
            current_body=BODY, current_version_id="rev_1", instruction="chống prompt injection"
        )

    assert len(calls) == 1


async def test_a_draft_that_works_first_time_costs_one_call(monkeypatch) -> None:
    program = _Drafts(_prediction(BODY))
    _wire(monkeypatch, program)

    await drafter.draft_revision(
        current_body=BODY, current_version_id="rev_1", instruction="chống prompt injection"
    )

    assert program.calls == 1
