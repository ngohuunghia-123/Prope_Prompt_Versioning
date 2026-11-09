"""Evaluation executors: suites, runs and their results behind the catalogue.

Starting a run spends the workspace's own provider credit, which is why it
proposes and waits for a person (`run.start` exists as a permission for exactly
that reason). Reading suites and results does not, so they answer directly.
"""

from datetime import UTC, datetime
from typing import Any

from prope.chat_orchestrator import tools
from prope.chat_orchestrator.domain import ToolName
from prope.chat_orchestrator.tools_registry import _not_found, resolve_prompt

__all__ = [
    "execute_start_eval_run",
    "propose_start_eval_run",
    "run_get_eval_results",
    "run_list_suites",
]

RUNS_LIMIT = 5


async def run_list_suites(context: tools.ToolContext, *, prompt_id: str) -> tools.ToolResult:
    """The evaluation suites attached to one visible prompt."""
    if not prompt_id.strip():
        return _not_found(ToolName.LIST_SUITES)

    try:
        row = await resolve_prompt(context, prompt_id)
        if row is None:
            return _not_found(ToolName.LIST_SUITES)
        from prope.access_control.actions import Action
        from prope.access_control.seams import AccessLevel, Actor, ActorType, Subject, SubjectType, may
        from prope.evaluation import repository as eval_repository

        actor = Actor(type=ActorType.USER, id=context.actor_id, workspace_id=context.workspace_id)
        subject = Subject(
            type=SubjectType.PROMPT,
            id=row.id,
            workspace_id=row.workspace_id,
            owner_id=row.owner_id,
            access_level=AccessLevel(row.access_level),
            namespace=row.namespace,
        )
        if not await may(context.db, actor, Action.SUITE_READ, subject):
            return _not_found(ToolName.LIST_SUITES)
        suites = await eval_repository.list_current_suites(context.db, prompt_id)
    except Exception:
        return _not_found(ToolName.LIST_SUITES)

    evidence = tuple(
        tools.Evidence(
            tag=context.tag(),
            kind="suite",
            reference=suite.id,
            label=suite.name,
            text=f"{suite.name} v{suite.suite_version} · {suite.case_count} case",
        )
        for suite in suites
    )
    return tools.ToolResult(
        tool=ToolName.LIST_SUITES,
        outcome="ok",
        evidence=evidence,
        detail={"result_count": len(evidence)},
        payload={"prompt_id": prompt_id, "suite_names": [suite.name for suite in suites]},
    )


async def run_get_eval_results(context: tools.ToolContext, *, prompt_id: str) -> tools.ToolResult:
    """Recent runs of one prompt, newest first, with pass/fail counts."""
    if not prompt_id.strip():
        return _not_found(ToolName.GET_EVAL_RESULTS)

    try:
        row = await resolve_prompt(context, prompt_id)
        if row is None:
            return _not_found(ToolName.GET_EVAL_RESULTS)
        from prope.access_control.actions import Action
        from prope.access_control.seams import AccessLevel, Actor, ActorType, Subject, SubjectType, may
        from prope.evaluation import repository as eval_repository

        actor = Actor(type=ActorType.USER, id=context.actor_id, workspace_id=context.workspace_id)
        subject = Subject(
            type=SubjectType.PROMPT,
            id=row.id,
            workspace_id=row.workspace_id,
            owner_id=row.owner_id,
            access_level=AccessLevel(row.access_level),
            namespace=row.namespace,
        )
        if not await may(context.db, actor, Action.RUN_READ, subject):
            return _not_found(ToolName.GET_EVAL_RESULTS)
        listings = await eval_repository.list_runs_for_prompt(context.db, prompt_id, limit=RUNS_LIMIT)
    except Exception:
        return _not_found(ToolName.GET_EVAL_RESULTS)

    evidence = tuple(
        tools.Evidence(
            tag=context.tag(),
            kind="eval_run",
            reference=item.run.id,
            label=item.suite_name or item.run.suite_id,
            text=(
                f"{item.suite_name or item.run.suite_id} · {str(item.run.role)} · "
                f"{str(item.run.status)} · pass {item.run.pass_count} / "
                f"fail {item.run.fail_count} / error {item.run.error_count}"
            ),
        )
        for item in listings
    )
    return tools.ToolResult(
        tool=ToolName.GET_EVAL_RESULTS,
        outcome="ok",
        evidence=evidence,
        detail={"result_count": len(evidence)},
        payload={
            "prompt_id": prompt_id,
            "run_ids": [item.run.id for item in listings],
            "latest_status": str(listings[0].run.status) if listings else "",
        },
    )


def propose_start_eval_run(
    context: tools.ToolContext,
    *,
    prompt_id: str,
    version_id: str | None = None,
    suite_names: list[str] | None = None,
) -> tools.ToolResult:
    """Describe the runs that would start. Writes nothing — and bills nothing.

    An absent version resolves to the prompt's latest at proposal time so the
    card names exactly what will be measured; the executor re-reads nothing.
    """
    if not version_id:
        return tools.ToolResult(
            tool=ToolName.START_EVAL_RUN, outcome="error", reason="chat_tool_no_target_version"
        )
    names = [name.strip() for name in (suite_names or []) if name.strip()]
    arguments: dict[str, Any] = {"prompt_id": prompt_id, "version_id": version_id}
    if names:
        arguments["suite_names"] = names[:10]
    preview = {"prompt_id": prompt_id, "version_id": version_id}
    if names:
        preview["suites"] = arguments["suite_names"]
    return tools.ToolResult(
        tool=ToolName.START_EVAL_RUN,
        outcome="ok",
        detail={"prompt_id": prompt_id, "steps": 1},
        proposal=tools.Proposal(
            tool=ToolName.START_EVAL_RUN,
            summary=version_id,
            preview=preview,
            arguments=arguments,
        ),
    )


async def execute_start_eval_run(context: tools.ToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    """Create candidate runs — plus baseline runs where the release lacks one.

    The baseline rule is evaluation/api's `_run_handles`, reimplemented here in
    its minimal form because that helper is typed against an HTTP `Session`. The
    behaviour it must preserve: every named (or current) suite gets a candidate
    run against the approved version, and any suite whose released-version
    baseline is missing gets a baseline run too.
    """
    from prope.access_control.actions import Action
    from prope.access_control.seams import AccessLevel, Actor, ActorType, Subject, SubjectType, may
    from prope.evaluation import commands
    from prope.evaluation import repository as eval_repository
    from prope.evaluation.domain import RunRole
    from prope.prompt_registry import repository as registry_repository
    from prope.prompt_registry.seams import get_released_revision

    prompt_id = str(arguments["prompt_id"])
    version_id = str(arguments["version_id"])

    # `run.start` spends the workspace's provider credit against THIS revision,
    # so it is asked about the prompt subject — the same gate the eval route
    # runs — and not about the bare workspace.
    row = await registry_repository.load_prompt(context.db, prompt_id)
    if row is None:
        raise tools.WriteRefused("not_found")
    actor = Actor(type=ActorType.USER, id=context.actor_id, workspace_id=context.workspace_id)
    subject = Subject(
        type=SubjectType.PROMPT,
        id=row.id,
        workspace_id=row.workspace_id,
        owner_id=row.owner_id,
        access_level=AccessLevel(row.access_level),
        namespace=row.namespace,
    )
    if not await may(context.db, actor, Action.RUN_START, subject):
        if await may(context.db, actor, Action.PROMPT_READ, subject):
            raise tools.WriteRefused("permission_denied")
        raise tools.WriteRefused("not_found")

    wanted = arguments.get("suite_names")
    suites = await eval_repository.list_current_suites(context.db, prompt_id)
    if isinstance(wanted, list) and wanted:
        keep = {str(name) for name in wanted}
        suites = tuple(suite for suite in suites if suite.name in keep)
    if not suites:
        raise tools.WriteRefused("chat_tool_no_suite")

    now = datetime.now(UTC)
    candidate_ids = await commands.create_runs(
        context.db,
        workspace_id=context.workspace_id,
        actor_id=context.actor_id,
        prompt_id=prompt_id,
        version_id=version_id,
        suite_ids=[suite.id for suite in suites],
        role=RunRole.CANDIDATE,
        now=now,
    )

    released = await get_released_revision(context.db, prompt_id) if arguments.get("include_released_baseline", True) else None
    missing = []
    if released is not None and released.version_id != version_id:
        for suite in suites:
            if await eval_repository.find_baseline_run(context.db, released.version_id, suite.id) is None:
                missing.append(suite)
    if missing:
        await commands.create_runs(
            context.db,
            workspace_id=context.workspace_id,
            actor_id=context.actor_id,
            prompt_id=prompt_id,
            version_id=released.version_id,
            suite_ids=[suite.id for suite in missing],
            role=RunRole.BASELINE,
            now=datetime.now(UTC),
        )

    return {
        "prompt_id": prompt_id,
        "version_id": version_id,
        "run_ids": list(candidate_ids),
        "run_count": len(candidate_ids) + len(missing),
    }
