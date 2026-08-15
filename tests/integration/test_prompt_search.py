"""The six acceptance criteria from prompt-search.lock.yml."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text

from prope.access_control.domain import FilterMode, VisibleFilter
from prope.db.session import workspace_transaction
from prope.prompt_search import repository, worker
from prope.prompt_search.domain import ExtractedMetadata, ExtractedVariations, IndexJobStatus
from tests.access_control import ADMIN_ID
from tests.prompt_registry import release, seed_prompt, seed_revision
from tests.unit import WORKSPACE_A


def _embedding(head: float) -> list[float]:
    return [head, 1.0 - head, *([0.0] * 1534)]


async def _seed_index(migrate_engine, prompt_id: str, version_id: str, embedding: list[float]):  # noqa: ANN001
    vector = "[" + ",".join(str(value) for value in embedding) + "]"
    async with migrate_engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO search.prompt_search_index (
                    id, prompt_id, version_id, workspace_id, keywords, topics, entities,
                    variations, language, role, content_embedding, embedding_model,
                    is_bilingual, indexed_at, indexed_by
                ) VALUES (
                    :id, :prompt_id, :version_id, :workspace_id, ARRAY['refund'],
                    ARRAY['support'], '{}', '{"en": [], "vi": []}'::jsonb,
                    ARRAY['en'], 'released', CAST(:embedding AS vector), 'text-embedding-3-small',
                    false, NOW(), :indexed_by
                )
                """
            ),
            {
                "id": f"psi_{prompt_id}",
                "prompt_id": prompt_id,
                "version_id": version_id,
                "workspace_id": WORKSPACE_A,
                "embedding": vector,
                "indexed_by": ADMIN_ID,
            },
        )


async def test_quick_search_all_prompts(app_sessionmaker, migrate_engine) -> None:
    indexed = "prm_01J0000000000000000SEARCH1"
    plain = "prm_01J0000000000000000SEARCH2"
    await seed_prompt(migrate_engine, indexed, name="refund-one", title="Refund one")
    await seed_prompt(migrate_engine, plain, name="refund-two", title="Refund two")
    await _seed_index(migrate_engine, indexed, "rev_indexed", _embedding(1.0))

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        results = await repository.list_prompts_for_quick_search(
            db,
            workspace_id=WORKSPACE_A,
            keyword="refund",
            visible=VisibleFilter(FilterMode.ALL),
            actor_id=ADMIN_ID,
        )

    assert {result.prompt_id for result in results} == {indexed, plain}


async def test_ai_search_semantic(app_sessionmaker, migrate_engine) -> None:
    close = "prm_01J0000000000000000VECTOR1"
    distant = "prm_01J0000000000000000VECTOR2"
    await seed_prompt(migrate_engine, close, name="vector-one")
    await seed_prompt(migrate_engine, distant, name="vector-two")
    await _seed_index(migrate_engine, close, "rev_close", _embedding(1.0))
    # 0.4 rather than 0.1: the far vector must stay above MIN_SEARCH_SIMILARITY,
    # or this asserts the floor rather than the ordering it is about.
    await _seed_index(migrate_engine, distant, "rev_far", _embedding(0.4))

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        results = await repository.search_prompts_hybrid(
            db,
            workspace_id=WORKSPACE_A,
            embedding=_embedding(1.0),
            keyword="unmatched",
            visible=VisibleFilter(FilterMode.ALL),
            actor_id=ADMIN_ID,
        )

    assert [result.prompt_id for result in results] == [close, distant]
    assert results[0].similarity is not None
    assert results[0].similarity > (results[1].similarity or 0)


async def test_on_demand_indexing(app_sessionmaker, migrate_engine, monkeypatch: pytest.MonkeyPatch) -> None:
    prompt_id = "prm_01J0000000000000000INDEX01"
    version_id = "rev_01J0000000000000000INDEX01"
    job_id = "psj_01J00000000000000000INDEX1"
    await seed_prompt(migrate_engine, prompt_id, name="index-flow")
    await seed_revision(migrate_engine, version_id, prompt_id, status="Approved")
    await release(migrate_engine, prompt_id=prompt_id, version_id=version_id)
    metadata = ExtractedMetadata(
        keywords=("refund",),
        topics=("support",),
        entities=(),
        variations=ExtractedVariations(en=("refund",)),
        language=("en",),
    )
    monkeypatch.setattr(worker, "extract_metadata", AsyncMock(return_value=metadata))
    monkeypatch.setattr(worker, "get_embedding_client", AsyncMock(return_value=object()))
    monkeypatch.setattr(repository, "get_or_create_embedding", AsyncMock(return_value=(_embedding(1.0), False)))

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        await repository.create_job_record(
            db,
            job_id=job_id,
            prompt_id=prompt_id,
            version_id=version_id,
            workspace_id=WORKSPACE_A,
            created_by=ADMIN_ID,
        )
        succeeded = await worker.run_indexing_job(
            db,
            worker.IndexingEnvelope(
                type="prompt_search_index",
                job_id=job_id,
                prompt_id=prompt_id,
                version_id=version_id,
                workspace_id=WORKSPACE_A,
                created_by=ADMIN_ID,
            ),
        )
        index = await repository.get_index_by_prompt(db, prompt_id)
        job = await repository.get_job_status(db, job_id)

    assert succeeded and index is not None
    assert job is not None and job.status is IndexJobStatus.COMPLETED


async def test_duplicate_warning(app_sessionmaker, migrate_engine) -> None:
    prompt_id = "prm_01J000000000000000000DUP1"
    await seed_prompt(migrate_engine, prompt_id, name="duplicate-source", title="Known duplicate")
    await _seed_index(migrate_engine, prompt_id, "rev_duplicate", _embedding(1.0))
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        neighbors = await repository.find_nearest_neighbors(
            db,
            workspace_id=WORKSPACE_A,
            embedding=_embedding(0.99),
            exclude_prompt_id="prm_other",
            threshold=0.9,
        )
    assert neighbors[0]["prompt_id"] == prompt_id
    assert neighbors[0]["similarity"] > 0.9


async def test_search_respects_permissions(app_sessionmaker, migrate_engine) -> None:
    mine = "prm_01J000000000000000000MINE"
    private = "prm_01J0000000000000000PRIVATE"
    await seed_prompt(migrate_engine, mine, name="mine", title="Secret mine")
    await seed_prompt(migrate_engine, private, name="private", title="Secret other", owner_id="usr_other")
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        results = await repository.list_prompts_for_quick_search(
            db,
            workspace_id=WORKSPACE_A,
            keyword="secret",
            visible=VisibleFilter(FilterMode.NONE),
            actor_id=ADMIN_ID,
        )
    assert [result.prompt_id for result in results] == [mine]


async def test_stale_index_detection(app_sessionmaker, migrate_engine) -> None:
    prompt_id = "prm_01J00000000000000000STALE"
    await seed_prompt(migrate_engine, prompt_id, name="stale-index")
    await seed_revision(migrate_engine, "rev_old", prompt_id, status="Approved")
    await seed_revision(migrate_engine, "rev_new", prompt_id, revision_number=2, status="Approved")
    await release(migrate_engine, prompt_id=prompt_id, version_id="rev_new")
    await _seed_index(migrate_engine, prompt_id, "rev_old", _embedding(1.0))
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        prompt = await worker.load_prompt(db, prompt_id)
        index = await repository.get_index_by_prompt(db, prompt_id)
    assert prompt is not None and index is not None
    assert index.version_id != prompt.released_version_id
