import inspect

import prope.worker
from prope.db.session import workspace_transaction
from prope.property_history.append import append
from prope.property_history.domain import ActorType, HistoryEventDraft, PromptScope
from prope.property_history.read import read
from tests.property_history import ACTOR_ID, SCOPE_PROMPT_ID, TARGET_ID, WORKSPACE_A, day

WORKER_SOURCE = inspect.getsource(prope.worker)


def test_no_expiry_job_exists_for_history_event() -> None:
    assert "history_event" not in WORKER_SOURCE


def test_the_worker_composes_exactly_three_jobs_and_none_is_history_shaped() -> None:
    jobs = {
        prope.worker.JOB_CALL_RECORD_DRAIN,
        prope.worker.JOB_EXPIRED_BODY_DELETION,
        prope.worker.JOB_QUEUE_DEPTH_GAUGES,
    }
    assert len(jobs) == 3
    for job in jobs:
        assert "history" not in job


async def test_a_retired_property_leaves_its_events_intact(app_sessionmaker) -> None:
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        await append(
            session,
            HistoryEventDraft(
                workspace_id=WORKSPACE_A,
                actor_type=ActorType.USER,
                actor_id=ACTOR_ID,
                action="property_created",
                target_type="property",
                target_id=TARGET_ID,
                scope_prompt_id=SCOPE_PROMPT_ID,
                occurred_at=day(1),
            ),
        )
        await append(
            session,
            HistoryEventDraft(
                workspace_id=WORKSPACE_A,
                actor_type=ActorType.USER,
                actor_id=ACTOR_ID,
                action="retired",
                target_type="property",
                target_id=TARGET_ID,
                scope_prompt_id=SCOPE_PROMPT_ID,
                occurred_at=day(2),
            ),
        )

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        events = await read(session, PromptScope(WORKSPACE_A, SCOPE_PROMPT_ID))

    assert [event.action for event in events] == ["retired", "property_created"]
