"""Consumer-key and provider-configuration executors behind the catalogue.

Two boundaries this module keeps, both inherited rather than invented:

* **A key's plaintext exists once.** `execute_create_api_key` returns it in
  `secret_once`, which rides the confirmation result and never the model's
  reply — the output rails redact credential-shaped text, so a secret that went
  through the reply would arrive as `[đã ẩn]` and be unrecoverable.
* **No provider act here touches a credential.** `create_provider` and
  `rotate_credential` refuse any secret they have not verified with a live
  probe of the upstream; giving this agent those would mean giving it outbound
  network access. They stay manual, and the assistant navigates instead.
"""

from datetime import UTC, datetime
from typing import Any, Final

from prope.access_control.api import LIST_KEYS
from prope.chat_orchestrator import tools
from prope.chat_orchestrator.domain import ToolName
from prope.chat_orchestrator.tools_registry import _gate_workspace

__all__ = [
    "execute_create_api_key",
    "execute_delete_provider",
    "execute_revoke_api_key",
    "execute_set_api_key_scope",
    "execute_update_provider",
    "propose_create_api_key",
    "propose_delete_provider",
    "propose_revoke_api_key",
    "propose_set_api_key_scope",
    "propose_update_provider",
    "run_list_api_keys",
    "run_list_providers",
]

#: The key-list projection lives in `access_control.api` and is imported rather
#: than re-typed: two copies of one SQL string is two chances to disagree about
#: what a key list contains — and this module owns no schema, so writing its own
#: read against `access.*` would be cross-schema SQL. Under the tenant policy
#: like every read here, so a key id from another workspace selects zero rows.
_KEY_LIST: Final = LIST_KEYS

KEYS_LIMIT: Final = 5
PROVIDERS_LIMIT: Final = 5

#: Scope entries are bounded here rather than at the database: a proposal a
#: person approves should not be able to carry a megabyte of model names.
_MAX_SCOPE_ITEMS: Final = 20
_MAX_ITEM_CHARACTERS: Final = 120


def _scope(raw: Any) -> list[str]:
    """A cleaned scope list, or an empty one."""
    if not isinstance(raw, (list, tuple)):
        return []
    seen: dict[str, None] = {}
    for item in raw:
        if not isinstance(item, str):
            continue
        value = item.strip()[:_MAX_ITEM_CHARACTERS]
        if value:
            seen.setdefault(value)
        if len(seen) >= _MAX_SCOPE_ITEMS:
            break
    return list(seen)


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


async def run_list_api_keys(context: tools.ToolContext) -> tools.ToolResult:
    """The workspace's consumer keys by name and last four. Never any secret."""
    from prope.access_control.actions import Action
    from prope.access_control.seams import Actor, ActorType, Subject, SubjectType, may

    actor = Actor(type=ActorType.USER, id=context.actor_id, workspace_id=context.workspace_id)
    subject = Subject(
        type=SubjectType.WORKSPACE,
        id=context.workspace_id,
        workspace_id=context.workspace_id,
    )
    try:
        if not await may(context.db, actor, Action.WORKSPACE_MANAGE_KEYS, subject):
            return tools.ToolResult(
                tool=ToolName.LIST_API_KEYS, outcome="error", reason="permission_denied"
            )
        rows = (await context.db.execute(_KEY_LIST)).mappings().all()
    except Exception:
        return tools.ToolResult(
            tool=ToolName.LIST_API_KEYS, outcome="error", reason="chat_tool_crashed"
        )

    top = rows[:KEYS_LIMIT]
    evidence = tuple(
        tools.Evidence(
            tag=context.tag(),
            kind="api_key",
            reference=str(row["id"]),
            label=str(row["name"]),
            text=(
                f"{row['name']} ····{row['last_four']} · "
                + ("revoked" if row["revoked_at"] else "active")
            ),
        )
        for row in top
    )
    return tools.ToolResult(
        tool=ToolName.LIST_API_KEYS,
        outcome="ok",
        evidence=evidence,
        detail={"result_count": len(evidence), "total_count": len(rows)},
        payload={"key_ids": [str(row["id"]) for row in top]},
    )


async def run_list_providers(context: tools.ToolContext) -> tools.ToolResult:
    """Provider configurations with verification status. No credential material."""
    from prope.access_control.actions import Action
    from prope.access_control.seams import Actor, ActorType, Subject, SubjectType, may
    from prope.provider_access import commands as provider_commands

    actor = Actor(type=ActorType.USER, id=context.actor_id, workspace_id=context.workspace_id)
    subject = Subject(
        type=SubjectType.WORKSPACE,
        id=context.workspace_id,
        workspace_id=context.workspace_id,
    )
    try:
        if not await may(context.db, actor, Action.CATALOGUE_READ, subject):
            return tools.ToolResult(
                tool=ToolName.LIST_PROVIDERS, outcome="error", reason="permission_denied"
            )
        rows = await provider_commands.list_rows(context.db)
    except Exception:
        return tools.ToolResult(
            tool=ToolName.LIST_PROVIDERS, outcome="error", reason="chat_tool_crashed"
        )

    top = rows[:PROVIDERS_LIMIT]
    evidence = tuple(
        tools.Evidence(
            tag=context.tag(),
            kind="provider",
            reference=row.id,
            label=row.display_name,
            text=f"{row.display_name} · {str(row.status)} · verified {str(row.verification_status)}",
        )
        for row in top
    )
    return tools.ToolResult(
        tool=ToolName.LIST_PROVIDERS,
        outcome="ok",
        evidence=evidence,
        detail={"result_count": len(evidence), "total_count": len(rows)},
        payload={"provider_config_ids": [row.id for row in top]},
    )


# ---------------------------------------------------------------------------
# Write proposals — describe the act, perform nothing
# ---------------------------------------------------------------------------


def _preview_scope(arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "models": arguments["scope_model_names"],
        "namespaces": arguments["scope_namespaces"],
    }


def propose_create_api_key(
    context: tools.ToolContext,
    *,
    name: str,
    scope_model_names: list[str] | None = None,
    scope_namespaces: list[str] | None = None,
) -> tools.ToolResult:
    """Describe the key that would be minted. Writes nothing."""
    if not name or not name.strip():
        return tools.ToolResult(
            tool=ToolName.CREATE_API_KEY, outcome="error", reason="chat_tool_missing_query"
        )
    arguments = {
        "name": name.strip()[:100],
        "scope_model_names": _scope(scope_model_names),
        "scope_namespaces": _scope(scope_namespaces),
    }
    return tools.ToolResult(
        tool=ToolName.CREATE_API_KEY,
        outcome="ok",
        detail={"steps": 1},
        proposal=tools.Proposal(
            tool=ToolName.CREATE_API_KEY,
            summary=arguments["name"],
            preview={"name": arguments["name"], **_preview_scope(arguments)},
            arguments=arguments,
        ),
    )


def propose_revoke_api_key(context: tools.ToolContext, *, key_id: str) -> tools.ToolResult:
    """Describe revoking one key. Writes nothing."""
    return tools.ToolResult(
        tool=ToolName.REVOKE_API_KEY,
        outcome="ok",
        detail={"key_id": key_id, "steps": 1},
        proposal=tools.Proposal(
            tool=ToolName.REVOKE_API_KEY,
            summary=key_id,
            preview={"key_id": key_id},
            arguments={"key_id": key_id},
        ),
    )


def propose_set_api_key_scope(
    context: tools.ToolContext,
    *,
    key_id: str,
    scope_model_names: list[str] | None = None,
    scope_namespaces: list[str] | None = None,
) -> tools.ToolResult:
    """Describe replacing a key's whole scope. Wholesale, never a delta."""
    arguments = {
        "key_id": key_id,
        "scope_model_names": _scope(scope_model_names),
        "scope_namespaces": _scope(scope_namespaces),
    }
    return tools.ToolResult(
        tool=ToolName.SET_API_KEY_SCOPE,
        outcome="ok",
        detail={"key_id": key_id, "steps": 1},
        proposal=tools.Proposal(
            tool=ToolName.SET_API_KEY_SCOPE,
            summary=key_id,
            preview={"key_id": key_id, **_preview_scope(arguments)},
            arguments=arguments,
        ),
    )


def propose_update_provider(
    context: tools.ToolContext,
    *,
    provider_config_id: str,
    display_name: str | None = None,
    status: str | None = None,
) -> tools.ToolResult:
    """Describe the configuration change. Credential acts are not proposed here."""
    clean_name = display_name.strip()[:100] if display_name and display_name.strip() else None
    clean_status = status.strip().lower() if status and status.strip() else None
    if clean_status not in (None, "active", "disabled"):
        return tools.ToolResult(
            tool=ToolName.UPDATE_PROVIDER, outcome="error", reason="chat_tool_invalid_status"
        )
    if clean_name is None and clean_status is None:
        return tools.ToolResult(
            tool=ToolName.UPDATE_PROVIDER, outcome="error", reason="chat_tool_nothing_to_change"
        )

    arguments: dict[str, Any] = {"provider_config_id": provider_config_id}
    if clean_name is not None:
        arguments["display_name"] = clean_name
    if clean_status is not None:
        arguments["status"] = clean_status
    return tools.ToolResult(
        tool=ToolName.UPDATE_PROVIDER,
        outcome="ok",
        detail={"provider_config_id": provider_config_id, "steps": 1},
        proposal=tools.Proposal(
            tool=ToolName.UPDATE_PROVIDER,
            summary=provider_config_id,
            preview=arguments.copy(),
            arguments=arguments,
        ),
    )


def propose_delete_provider(context: tools.ToolContext, *, provider_config_id: str) -> tools.ToolResult:
    """Describe removing a configuration. Refused downstream while revisions bind."""
    return tools.ToolResult(
        tool=ToolName.DELETE_PROVIDER,
        outcome="ok",
        detail={"provider_config_id": provider_config_id, "steps": 1},
        proposal=tools.Proposal(
            tool=ToolName.DELETE_PROVIDER,
            summary=provider_config_id,
            preview={"provider_config_id": provider_config_id},
            arguments={"provider_config_id": provider_config_id},
        ),
    )


# ---------------------------------------------------------------------------
# Confirmed writes — reached only from the confirmation route
# ---------------------------------------------------------------------------


async def execute_create_api_key(context: tools.ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    """Mint the key. **The plaintext leaves here exactly once**, in `secret_once`."""
    from prope.access_control import commands

    await _gate_workspace(context, "workspace.manage_keys")
    minted = await commands.create_api_key(
        context.db,
        workspace_id=context.workspace_id,
        actor_id=context.actor_id,
        name=str(arguments["name"]),
        scope_model_names=_scope(arguments.get("scope_model_names")),
        scope_namespaces=_scope(arguments.get("scope_namespaces")),
        now=datetime.now(UTC),
    )
    return {
        "key_id": minted.key_id,
        "last_four": minted.last_four,
        "secret_once": minted.plaintext,
    }


async def execute_revoke_api_key(context: tools.ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    """Stamp `revoked_at`. The very next request presenting the key is refused."""
    from prope.access_control import commands
    from prope.session_auth import ManagementRefusal

    await _gate_workspace(context, "workspace.manage_keys")
    key_id = str(arguments["key_id"])
    try:
        await commands.revoke_api_key(
            context.db,
            workspace_id=context.workspace_id,
            actor_id=context.actor_id,
            key_id=key_id,
            now=datetime.now(UTC),
        )
    except ManagementRefusal:
        raise tools.WriteRefused("not_found") from None
    return {"key_id": key_id}


async def execute_set_api_key_scope(context: tools.ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    """Replace a live key's whole scope with what was approved."""
    from prope.access_control import commands
    from prope.session_auth import ManagementRefusal

    await _gate_workspace(context, "workspace.manage_keys")
    key_id = str(arguments["key_id"])
    try:
        await commands.set_api_key_scope(
            context.db,
            workspace_id=context.workspace_id,
            actor_id=context.actor_id,
            key_id=key_id,
            scope_model_names=_scope(arguments.get("scope_model_names")),
            scope_namespaces=_scope(arguments.get("scope_namespaces")),
            now=datetime.now(UTC),
        )
    except ManagementRefusal:
        raise tools.WriteRefused("not_found") from None
    return {"key_id": key_id}


async def execute_update_provider(context: tools.ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    """Change a configuration's name, state or nothing else. Never its credential."""
    from prope.provider_access import commands as provider_commands
    from prope.provider_access.domain import ConfigStatus
    from prope.session_auth import ManagementRefusal

    await _gate_workspace(context, "provider.configure")
    provider_config_id = str(arguments["provider_config_id"])
    raw_status = arguments.get("status")
    status = ConfigStatus(str(raw_status)) if raw_status else None

    try:
        row = await provider_commands.update_provider(
            context.db,
            workspace_id=context.workspace_id,
            actor_id=context.actor_id,
            provider_config_id=provider_config_id,
            display_name=arguments.get("display_name"),
            base_url=None,
            status=status,
            interactive_concurrency=None,
            batch_concurrency=None,
            now=datetime.now(UTC),
        )
    except ManagementRefusal:
        # A duplicate display name arrives as ALREADY_EXISTS; the card says so
        # without quoting the conflicting value.
        raise tools.WriteRefused("chat_tool_name_taken") from None
    return {"provider_config_id": row.id, "status": str(row.status)}


async def execute_delete_provider(context: tools.ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    """Remove a configuration, refused while revisions still bind to it."""
    from prope.errors import ErrorCode
    from prope.provider_access import commands as provider_commands
    from prope.session_auth import ManagementRefusal

    await _gate_workspace(context, "provider.disable")
    provider_config_id = str(arguments["provider_config_id"])
    try:
        await provider_commands.delete_provider(
            context.db,
            workspace_id=context.workspace_id,
            actor_id=context.actor_id,
            provider_config_id=provider_config_id,
            now=datetime.now(UTC),
        )
    except ManagementRefusal as refusal:
        if refusal.code == ErrorCode.PROVIDER_BOUND_BY_REVISIONS:
            raise tools.WriteRefused("chat_tool_provider_bound") from None
        raise tools.WriteRefused("not_found") from None
    return {"provider_config_id": provider_config_id}
