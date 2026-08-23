"""The full write registry: `tool -> the executor that runs it once approved`.

Every write tool in the catalogue appears here exactly once, and nothing that
merely reads does. The import-time assert below is what keeps that true — a
tool added to `domain.TOOLS` with `writes=True` and no executor fails at boot
rather than at the moment a person presses Approve and nothing happens.
"""

from typing import Final

from prope.chat_orchestrator import tools, tools_access, tools_evaluation, tools_registry
from prope.chat_orchestrator.domain import TOOLS, ToolName

__all__ = ["CONFIRMED_EXECUTORS"]

CONFIRMED_EXECUTORS: Final = {
    ToolName.CREATE_PROMPT: tools.execute_create_prompt,
    ToolName.CREATE_REVISION: tools.execute_create_revision,
    ToolName.UPDATE_PROMPT: tools_registry.execute_update_prompt,
    ToolName.RETIRE_PROMPT: tools_registry.execute_retire_prompt,
    ToolName.CREATE_FOLDER: tools_registry.execute_create_folder,
    ToolName.RENAME_FOLDER: tools_registry.execute_rename_folder,
    ToolName.DELETE_FOLDER: tools_registry.execute_delete_folder,
    ToolName.CREATE_API_KEY: tools_access.execute_create_api_key,
    ToolName.REVOKE_API_KEY: tools_access.execute_revoke_api_key,
    ToolName.SET_API_KEY_SCOPE: tools_access.execute_set_api_key_scope,
    ToolName.UPDATE_PROVIDER: tools_access.execute_update_provider,
    ToolName.DELETE_PROVIDER: tools_access.execute_delete_provider,
    ToolName.START_EVAL_RUN: tools_evaluation.execute_start_eval_run,
}

assert set(CONFIRMED_EXECUTORS) == {name for name, spec in TOOLS.items() if spec.writes}, (
    "every write tool needs a confirmed executor, and nothing else may have one"
)
