"""ADR-0058 — a chain breaks at a prompt you may not see, and never bridges over it.

The graph is assembled from three prompts' call records, and the reader is
authorised against exactly one of them. Two things have to hold at once, and they
pull in opposite directions:

* a node whose prompt the reader may not see must not appear, in any form — a
  *restricted step* placeholder would confirm that a private prompt exists and is
  running in production, which is the disclosure BR-01 closes as not-found;
* the surviving nodes must not be joined up over the gap, because an edge from
  the first step straight to the third describes an application that never ran.

The result is a fragmented graph, and the last test here is the one that says
fragmenting is safe: a hidden parent and an expired parent produce byte-identical
shapes, so the picture cannot be used to ask whether a private prompt is there.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.access_control import (
    MEMBER_ID,
    seed_member,
    seed_role,
    seed_session,
    seed_user,
    seed_workspace,
)
from tests.integration._asgi import call
from tests.prompt_registry import PROMPT_ID, registry_api, seed_prompt, seed_revision
from tests.unit import WORKSPACE_A

OWNER_SESSION = "ses_convchain_owner0000000001"
COLLEAGUE_SESSION = "ses_convchain_colleague000001"

#: The chain's three steps. `OPEN` is the entry point a colleague may read — the
#: application's system prompt, opened to the workspace. `SHUT` is the guardrail
#: its author kept private, and it is the middle of the chain.
OPEN_PROMPT = "prm_01J00000000000000000OPEN"
OPEN_VERSION = "rev_01J0000000000000000OPEN1"
SHUT_PROMPT = "prm_01J00000000000000000SHUT"
SHUT_VERSION = "rev_01J0000000000000000SHUT1"

CALL_ONE = "cal_01J00000000000000000STEP1"
CALL_TWO = "cal_01J00000000000000000STEP2"
CALL_THREE = "cal_01J0000000000000000STEP3"

CONVERSATION = "conv-9f2a"
OTHER_CONVERSATION = "conv-someone-elses"

NONEXISTENT_CONVERSATION = "conv-never-existed"

INSERT_CALL_RECORD = text(
    """
    INSERT INTO ledger.call_record (
        call_id, workspace_id, source, prompt_id, version_id, revision_number,
        conversation_id, parent_call_id,
        outcome, pinned, fallback, streaming,
        input_tokens, output_tokens, usage_status,
        cost, currency, price_row_id, cost_status, created_at
    ) VALUES (
        :call_id, :workspace_id, 'gateway', :prompt_id, :version_id, 1,
        :conversation_id, :parent_call_id,
        'ok', false, false, false,
        120, 340, 'reported',
        NULL, NULL, NULL, 'unpriced', :created_at
    )
    """
)


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with registry_api(app_sessionmaker) as application:
        yield application


def _owner() -> dict[str, str]:
    return {"cookie": f"prope_session={OWNER_SESSION}"}


def _colleague() -> dict[str, str]:
    return {"cookie": f"prope_session={COLLEAGUE_SESSION}"}


async def _record(connection, call_id, prompt, version, parent, minute, conversation=CONVERSATION):  # noqa: ANN001, ANN202
    await connection.execute(
        INSERT_CALL_RECORD,
        {
            "call_id": call_id,
            "workspace_id": WORKSPACE_A,
            "prompt_id": prompt,
            "version_id": version,
            "conversation_id": conversation,
            "parent_call_id": parent,
            "created_at": datetime(2026, 8, 5, 12, minute, tzinfo=UTC),
        },
    )


async def _a_chatbot_whose_middle_step_is_private(migrate_engine) -> None:  # noqa: ANN001
    """One conversation, three calls, two prompts, and a colleague with no role.

    The colleague's shape is BR-01's: legitimately in the workspace,
    authenticated, entitled to nothing in particular. They can read `OPEN_PROMPT`
    because its owner opened it to the workspace, and that is their whole claim on
    this conversation.
    """
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, "Owner")
    await seed_session(migrate_engine, OWNER_SESSION)

    await seed_user(migrate_engine, MEMBER_ID)
    await seed_member(migrate_engine, user_id=MEMBER_ID)
    await seed_session(migrate_engine, COLLEAGUE_SESSION, user_id=MEMBER_ID)

    await seed_prompt(
        migrate_engine,
        prompt_id=OPEN_PROMPT,
        name="system-prompt",
        title="System prompt",
        access_level="workspace",
    )
    await seed_revision(migrate_engine, version_id=OPEN_VERSION, prompt_id=OPEN_PROMPT)
    await seed_prompt(
        migrate_engine,
        prompt_id=SHUT_PROMPT,
        name="guardrail",
        title="Guardrail",
        access_level="private",
    )
    await seed_revision(migrate_engine, version_id=SHUT_VERSION, prompt_id=SHUT_PROMPT)

    async with migrate_engine.begin() as connection:
        await _record(connection, CALL_ONE, OPEN_PROMPT, OPEN_VERSION, None, 0)
        await _record(connection, CALL_TWO, SHUT_PROMPT, SHUT_VERSION, CALL_ONE, 1)
        await _record(connection, CALL_THREE, OPEN_PROMPT, OPEN_VERSION, CALL_TWO, 2)


def _graph(response) -> dict:  # noqa: ANN001
    return response.json()


def _edges(graph: dict) -> list[tuple[str, str | None]]:
    return [(node["call_id"], node["parent_call_id"]) for node in graph["nodes"]]


async def test_the_owner_sees_the_whole_chain_with_its_edges_intact(api, migrate_engine) -> None:
    """The positive control. Every refusal below is vacuous without it."""
    await _a_chatbot_whose_middle_step_is_private(migrate_engine)

    response = await call(
        api,
        "GET",
        f"/api/v1/prompts/{OPEN_PROMPT}/conversations/{CONVERSATION}",
        headers=_owner(),
    )

    assert response.status_code == 200, response.body
    graph = _graph(response)
    assert _edges(graph) == [
        (CALL_ONE, None),
        (CALL_TWO, CALL_ONE),
        (CALL_THREE, CALL_TWO),
    ]
    assert graph["hidden_count"] == 0
    assert [node["prompt_title"] for node in graph["nodes"]] == [
        "System prompt",
        "Guardrail",
        "System prompt",
    ]


async def test_a_colleague_gets_a_fragment_and_never_a_bridge(api, migrate_engine) -> None:
    """The load-bearing one.

    The guardrail is gone and the third step is a **root** — not a child of the
    first. Bridging would draw the system prompt calling itself directly, which
    is a different application from the one that ran, and a graph that is
    confidently wrong about shape is worse than one that is visibly incomplete.
    """
    await _a_chatbot_whose_middle_step_is_private(migrate_engine)

    response = await call(
        api,
        "GET",
        f"/api/v1/prompts/{OPEN_PROMPT}/conversations/{CONVERSATION}",
        headers=_colleague(),
    )

    assert response.status_code == 200, response.body
    graph = _graph(response)
    assert _edges(graph) == [(CALL_ONE, None), (CALL_THREE, None)]
    assert graph["hidden_count"] == 1


async def test_nothing_about_the_hidden_step_survives_into_the_response(
    api, migrate_engine
) -> None:
    """A count, and not an identity.

    `hidden_count` is reported so a reader can tell a permissions gap from an
    application bug. Everything that would make it an *oracle* — the id, the
    title, the revision, the position in the chain — must be absent from the
    bytes, not merely absent from the fields somebody remembered to check.
    """
    await _a_chatbot_whose_middle_step_is_private(migrate_engine)

    response = await call(
        api,
        "GET",
        f"/api/v1/prompts/{OPEN_PROMPT}/conversations/{CONVERSATION}",
        headers=_colleague(),
    )

    body = response.body.decode()
    assert SHUT_PROMPT not in body
    assert SHUT_VERSION not in body
    assert CALL_TWO not in body
    assert "Guardrail" not in body


async def test_a_hidden_parent_and_an_expired_parent_are_byte_identical(
    api, migrate_engine
) -> None:
    """What makes fragmenting safe rather than merely quiet.

    The second conversation is the same chain with its middle step never written
    at all — the shape a retention sweep leaves behind. If the two responses
    differed, the difference would answer *is there a private prompt in the gap?*
    and the placeholder node this design rejected would have been reintroduced by
    accident.
    """
    await _a_chatbot_whose_middle_step_is_private(migrate_engine)
    async with migrate_engine.begin() as connection:
        await _record(
            connection, "cal_01J000000000000000EXPIR1", OPEN_PROMPT, OPEN_VERSION, None, 0,
            conversation="conv-expired",
        )
        await _record(
            connection, "cal_01J000000000000000EXPIR3", OPEN_PROMPT, OPEN_VERSION,
            "cal_01J000000000000000EXPIR2", 2, conversation="conv-expired",
        )

    hidden = await call(
        api, "GET", f"/api/v1/prompts/{OPEN_PROMPT}/conversations/{CONVERSATION}",
        headers=_colleague(),
    )
    expired = await call(
        api, "GET", f"/api/v1/prompts/{OPEN_PROMPT}/conversations/conv-expired",
        headers=_colleague(),
    )

    assert [parent for _, parent in _edges(_graph(hidden))] == [None, None]
    assert [parent for _, parent in _edges(_graph(expired))] == [None, None]


async def test_a_conversation_the_named_prompt_never_touched_comes_back_empty(
    api, migrate_engine
) -> None:
    """The second gate, and the one whose absence would be a privilege escalation.

    `prompt.read` is checked against `OPEN_PROMPT`. Without the requirement that
    the conversation actually involve it, naming any readable prompt beside any
    guessable `conversation_id` would return that conversation entire. Empty
    rather than refused: that is not-found's shape, and it says nothing about
    whether the id exists.
    """
    await _a_chatbot_whose_middle_step_is_private(migrate_engine)
    async with migrate_engine.begin() as connection:
        await _record(
            connection, "cal_01J00000000000000OTHER1", SHUT_PROMPT, SHUT_VERSION, None, 5,
            conversation=OTHER_CONVERSATION,
        )

    theirs = await call(
        api, "GET", f"/api/v1/prompts/{OPEN_PROMPT}/conversations/{OTHER_CONVERSATION}",
        headers=_owner(),
    )
    invented = await call(
        api, "GET", f"/api/v1/prompts/{OPEN_PROMPT}/conversations/{NONEXISTENT_CONVERSATION}",
        headers=_owner(),
    )

    assert theirs.status_code == 200, theirs.body
    assert theirs.json()["nodes"] == []

    # Everything but the echoed id, which differs because the caller chose it and
    # therefore tells them nothing they did not already type into the URL. What
    # must match is the rest: a conversation that exists but is none of this
    # prompt's business is indistinguishable from one that was never created.
    def _without_the_echo(response) -> dict:  # noqa: ANN001
        return {key: value for key, value in response.json().items() if key != "conversation_id"}

    assert _without_the_echo(theirs) == _without_the_echo(invented)
    assert theirs.status_code == invented.status_code


async def test_a_private_prompt_refuses_the_conversation_list_as_not_found(
    api, migrate_engine
) -> None:
    """BR-01 on the entry point, in `_visible_prompt`'s two shapes and not a third."""
    await _a_chatbot_whose_middle_step_is_private(migrate_engine)

    refused = await call(
        api, "GET", f"/api/v1/prompts/{SHUT_PROMPT}/conversations", headers=_colleague()
    )
    control = await call(
        api, "GET", f"/api/v1/prompts/{PROMPT_ID}/conversations", headers=_colleague()
    )

    assert refused.status_code == 404
    # Everything but `request_id`, which is per-request by design. The helper is
    # `test_call_metadata_read_is_private_by_default`'s, restated rather than
    # imported so this file stands on its own.
    assert _without_request_id(refused) == _without_request_id(control)


async def test_the_list_counts_the_whole_conversation_not_this_prompts_share(
    api, migrate_engine
) -> None:
    """`call_count` is the chain's length, which is the number a reader scans for.

    Rolling up only the rows naming this prompt would report 2 for a three-step
    conversation — and the reader would have no way to know the picture they were
    about to open had a step they had not been told about.
    """
    await _a_chatbot_whose_middle_step_is_private(migrate_engine)

    response = await call(
        api, "GET", f"/api/v1/prompts/{OPEN_PROMPT}/conversations", headers=_owner()
    )

    assert response.status_code == 200, response.body
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["conversation_id"] == CONVERSATION
    assert rows[0]["call_count"] == 3
    assert rows[0]["prompt_count"] == 2


async def test_the_graph_never_carries_a_stored_body(api, migrate_engine) -> None:
    """ADR-0018 is untouched by ADR-0058, asserted over the type rather than a response."""
    await _a_chatbot_whose_middle_step_is_private(migrate_engine)

    from prope.prompt_registry.schemas import ConversationNodeRead

    fields = set(ConversationNodeRead.model_fields)
    assert not [name for name in fields if "body" in name.lower()], fields

    response = await call(
        api, "GET", f"/api/v1/prompts/{OPEN_PROMPT}/conversations/{CONVERSATION}",
        headers=_owner(),
    )
    assert "request_body" not in response.body.decode()
    assert "response_body" not in response.body.decode()


def _without_request_id(response) -> dict:  # noqa: ANN001
    payload = response.json()
    return {"error": {k: v for k, v in payload["error"].items() if k != "request_id"}}
