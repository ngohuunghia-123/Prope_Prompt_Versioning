"""Import identity collisions: unique proposals, editable cards, honest refusals.

The session that motivated this: an import staged `imported/prompt-da-nhap`
while that exact model name already existed, so its approval could only answer
409 — three times, each rendered as "try again later". These tests pin the
three halves of the fix: proposals walk to a free name before staging, a
person's card edits land in the stored arguments before execution, and
anything outside the whitelist refuses with a named code.
"""

from types import SimpleNamespace
from typing import Any

import pytest

from prope.chat_orchestrator import orchestrator, tools
from prope.chat_orchestrator.domain import ToolName


def _proposal_result(slug: str = "prompt-da-nhap", title: str = "Prompt đã nhập") -> tools.ToolResult:
    proposal = tools.Proposal(
        tool=ToolName.CREATE_PROMPT,
        summary=f"imported/{slug}",
        preview={"title": title, "name": slug, "namespace": "imported", "body_characters": 10},
        arguments={
            "namespace": "imported",
            "name": slug,
            "title": title,
            "access_level": "private",
            "body": "<prompt/>",
        },
    )
    return tools.ToolResult(tool=ToolName.CREATE_PROMPT, outcome="ok", proposal=proposal)


# ---------------------------------------------------------------------------
# F1: proposals stage a free identity
# ---------------------------------------------------------------------------


async def test_a_free_name_stages_unchanged(monkeypatch) -> None:
    from prope.prompt_registry import repository as registry_repository

    async def load(db, namespace, name):  # noqa: ANN001, ARG001
        return None

    monkeypatch.setattr(registry_repository, "load_prompt_by_model_name", load)

    context = tools.ToolContext(
        db=None, workspace_id="wsp_1", actor_id="usr_1", visible=None,
        converted_xml="<prompt><system>x</system></prompt>",
    )
    result = await orchestrator._step_create_prompt(context, SimpleNamespace(query="Prompt đã nhập", arguments={}), [])

    assert result.proposal is not None
    assert result.proposal.arguments["name"] == "prompt-da-nhap"


async def test_a_taken_name_walks_to_the_next_free_suffix(monkeypatch) -> None:
    from prope.prompt_registry import repository as registry_repository

    seen: list[str] = []

    async def load(db, namespace, name):  # noqa: ANN001, ARG001
        seen.append(name)
        return SimpleNamespace(id="prm_0") if name == "prompt-da-nhap" else None

    monkeypatch.setattr(registry_repository, "load_prompt_by_model_name", load)

    context = tools.ToolContext(
        db=None, workspace_id="wsp_1", actor_id="usr_1", visible=None,
        converted_xml="<prompt><system>x</system></prompt>",
    )
    result = await orchestrator._step_create_prompt(context, SimpleNamespace(query="Prompt đã nhập", arguments={}), [])

    proposal = result.proposal
    assert proposal is not None
    assert proposal.arguments["name"] == "prompt-da-nhap-2"
    assert proposal.arguments["title"] == "Prompt đã nhập 2"
    assert proposal.summary == "imported/prompt-da-nhap-2"
    # The card shows what will run: preview and arguments agree.
    assert proposal.preview["name"] == "prompt-da-nhap-2"
    assert seen == ["prompt-da-nhap", "prompt-da-nhap-2"]


async def test_every_suffix_taken_is_an_error_not_a_card(monkeypatch) -> None:
    from prope.prompt_registry import repository as registry_repository

    async def load(db, namespace, name):  # noqa: ANN001, ARG001
        return SimpleNamespace(id="prm_0")

    monkeypatch.setattr(registry_repository, "load_prompt_by_model_name", load)

    context = tools.ToolContext(
        db=None, workspace_id="wsp_1", actor_id="usr_1", visible=None,
        converted_xml="<prompt><system>x</system></prompt>",
    )
    result = await orchestrator._step_create_prompt(context, SimpleNamespace(query="X", arguments={}), [])

    assert result.proposal is None
    assert result.reason == "chat_tool_name_exhausted"


async def test_an_identity_check_failure_still_stages_the_original(monkeypatch) -> None:
    """The uniqueness check improves the odds; it must not become a new way for
    an import to die before the person ever sees a card."""
    from prope.prompt_registry import repository as registry_repository

    async def load(db, namespace, name):  # noqa: ANN001, ARG001
        raise RuntimeError("db down")

    monkeypatch.setattr(registry_repository, "load_prompt_by_model_name", load)

    context = tools.ToolContext(
        db=None, workspace_id="wsp_1", actor_id="usr_1", visible=None,
        converted_xml="<prompt><system>x</system></prompt>",
    )
    result = await orchestrator._step_create_prompt(context, SimpleNamespace(query="Prompt đã nhập", arguments={}), [])

    assert result.proposal is not None
    assert result.proposal.arguments["name"] == "prompt-da-nhap"


def _action(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "pac_1",
        "tool": "create_prompt",
        "status": "pending",
        "arguments": {"namespace": "imported", "name": "prompt-da-nhap", "title": "Prompt đã nhập"},
        "preview": {"name": "prompt-da-nhap", "title": "Prompt đã nhập"},
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# F3: card edits fold into the stored proposal
# ---------------------------------------------------------------------------


async def test_edits_patch_arguments_and_persist_before_execution(monkeypatch) -> None:
    from prope.chat_orchestrator import api as chat_api
    from prope.chat_orchestrator import repository as chat_repository

    persisted: dict[str, Any] = {}

    async def update(db, action_id, *, actor_id, arguments, preview):  # noqa: ANN001, ARG001
        persisted.update({"arguments": arguments, "preview": preview})
        return True

    async def identity(db, *, namespace, slug, title):  # noqa: ANN001, ARG001
        return (slug, title)

    monkeypatch.setattr(chat_repository, "update_pending_action_payload", update)
    monkeypatch.setattr(chat_api, "unique_import_identity", identity)

    action = _action()
    await chat_api._apply_action_edits(
        None, action_id="pac_1", actor_id="usr_1", action=action,
        edits={"title": "Ponytail Architect", "name": "ponytail-architect"},
    )

    assert persisted["arguments"]["name"] == "ponytail-architect"
    assert action["arguments"]["title"] == "Ponytail Architect"
    assert action["preview"] == persisted["preview"]


async def test_edited_names_are_re_slugged_deterministically(monkeypatch) -> None:
    from prope.chat_orchestrator import api as chat_api
    from prope.chat_orchestrator import repository as chat_repository

    captured: dict[str, Any] = {}

    async def update(db, action_id, *, actor_id, arguments, preview):  # noqa: ANN001, ARG001
        captured.update(arguments)
        return True

    async def identity(db, *, namespace, slug, title):  # noqa: ANN001, ARG001
        captured["slug_in"] = slug
        return (slug, title)

    monkeypatch.setattr(chat_repository, "update_pending_action_payload", update)
    monkeypatch.setattr(chat_api, "unique_import_identity", identity)

    await chat_api._apply_action_edits(
        None, action_id="pac_1", actor_id="usr_1", action=_action(),
        edits={"name": "Ponytail Architect!"},
    )

    assert captured["slug_in"] == "ponytail-architect"


async def test_edits_outside_the_whitelist_refuse_with_a_named_code(monkeypatch) -> None:
    from prope.chat_orchestrator import api as chat_api
    from prope.errors import ErrorCode, ManagementRefusal

    with pytest.raises(ManagementRefusal) as refused:
        await chat_api._apply_action_edits(
            None, action_id="pac_1", actor_id="usr_1",
            action=_action(tool="create_folder"),
            edits={"name": "whatever"},
        )
    assert refused.value.code == ErrorCode.CHAT_ACTION_EDIT_NOT_ALLOWED


async def test_editing_protected_fields_refuses(monkeypatch) -> None:
    from prope.chat_orchestrator import api as chat_api
    from prope.errors import ErrorCode, ManagementRefusal

    with pytest.raises(ManagementRefusal) as refused:
        await chat_api._apply_action_edits(
            None, action_id="pac_1", actor_id="usr_1", action=_action(),
            edits={"body": "<evil/>"},
        )
    assert refused.value.code == ErrorCode.CHAT_ACTION_EDIT_NOT_ALLOWED


async def test_an_edit_to_everything_taken_refuses_honestly(monkeypatch) -> None:
    from prope.chat_orchestrator import api as chat_api
    from prope.errors import ErrorCode, ManagementRefusal

    async def identity(db, *, namespace, slug, title):  # noqa: ANN001, ARG001
        return None

    monkeypatch.setattr(chat_api, "unique_import_identity", identity)

    with pytest.raises(ManagementRefusal) as refused:
        await chat_api._apply_action_edits(
            None, action_id="pac_1", actor_id="usr_1", action=_action(),
            edits={"name": "x"},
        )
    assert refused.value.code == ErrorCode.REGISTRY_MODEL_NAME_TAKEN
