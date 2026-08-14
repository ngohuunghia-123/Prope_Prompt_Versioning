"""Public-seam tests for prompt-search's agent and worker boundaries."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from prope.access_control.domain import FilterMode, VisibleFilter
from prope.prompt_search.agent import search
from prope.prompt_search.domain import SearchResult
from prope.prompt_search.worker import parse_envelope


def test_index_envelope_validates_the_tenant_identifier() -> None:
    assert (
        parse_envelope(
            b'{"type":"prompt_search_index","job_id":"psj_1","prompt_id":"prm_1",'
            b'"version_id":"rev_1","workspace_id":"wsp_1","created_by":"usr_1"}'
        )
        is not None
    )
    assert (
        parse_envelope(
            b'{"type":"prompt_search_index","job_id":"psj_1","prompt_id":"prm_1",'
            b'"version_id":"rev_1","workspace_id":"bad workspace","created_by":"usr_1"}'
        )
        is None
    )


async def test_semantic_search_pushes_visibility_into_the_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    visible = VisibleFilter(FilterMode.IDS, ("prm_granted",))
    embedding_client = SimpleNamespace()
    result = SearchResult(
        prompt_id="prm_granted",
        title="Refund",
        purpose="Handle refunds",
        similarity=0.97,
        keywords=("refund",),
        topics=("support",),
        is_indexed=True,
        version_id="rev_1",
    )
    get_client = AsyncMock(return_value=embedding_client)
    get_embedding = AsyncMock(return_value=([0.1, 0.2], False))
    search_index = AsyncMock(return_value=[result])
    monkeypatch.setattr(search, "get_embedding_client", get_client)
    monkeypatch.setattr(search.repository, "get_or_create_embedding", get_embedding)
    monkeypatch.setattr(search.repository, "search_indexed_prompts", search_index)

    found = await search.semantic_search(
        db=SimpleNamespace(),
        query="customer refund",
        workspace_id="wsp_1",
        visible=visible,
        actor_id="usr_1",
    )

    assert found == [result]
    search_index.assert_awaited_once()
    assert search_index.await_args.kwargs["visible"] is visible
    assert search_index.await_args.kwargs["actor_id"] == "usr_1"


def test_app_agent_configuration_never_reads_the_user_provider_key() -> None:
    from pathlib import Path

    agent_source = Path("src/prope/app_agent/client.py").read_text(encoding="utf-8") + "\n" + "\n".join(
        path.read_text(encoding="utf-8") for path in Path("src/prope/prompt_search/agent").glob("*.py")
    )
    assert 'os.environ.get("OPENAI_API_KEY"' not in agent_source
    assert 'os.environ.get("APP_OPENAI_API_KEY"' in agent_source
