"""Explicit pairs do not inherit the released-baseline selection policy."""

from prope.errors import ErrorCode
from prope.prompt_registry.domain import RevisionRead
from prope.session_auth import ManagementRefusal


def require_equivalent_configuration(original: RevisionRead, candidate: RevisionRead) -> None:
    if (
        original.version_id == candidate.version_id
        or original.prompt_id != candidate.prompt_id
        or original.workspace_id != candidate.workspace_id
        or original.routed
        or candidate.routed
        or original.primary is None
        or candidate.primary is None
        or original.provider_config_id != candidate.provider_config_id
        or original.upstream_model != candidate.upstream_model
        or original.parameters != candidate.parameters
    ):
        raise ManagementRefusal(
            status_code=422,
            code=ErrorCode.VALIDATION_FAILED,
            message="comparison requires distinct revisions with the same single-provider configuration",
        )
