"""Private, immutable inputs for explicit comparisons of editable Drafts."""

from dataclasses import replace
from typing import Any

from pydantic import BaseModel, ConfigDict

from prope.prompt_registry.domain import RevisionRead


class ComparisonSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pair_id: str
    original_version_id: str
    candidate_version_id: str
    version_id: str
    body: str
    provider_config_id: str
    upstream_model: str
    parameters: dict[str, Any]
    fallback_answer: str | None

    def apply(self, revision: RevisionRead) -> RevisionRead:
        if self.version_id != revision.version_id:
            raise ValueError("snapshot does not belong to this revision")
        return replace(
            revision,
            body=self.body,
            provider_config_id=self.provider_config_id,
            upstream_model=self.upstream_model,
            parameters=self.parameters,
            fallback_answer=self.fallback_answer,
            route_combo_id=None,
            route_combo_name=None,
            route=(),
        )


def capture_snapshot(
    revision: RevisionRead, pair_id: str, original_version_id: str, candidate_version_id: str
) -> dict[str, Any]:
    return ComparisonSnapshot(
        pair_id=pair_id,
        original_version_id=original_version_id,
        candidate_version_id=candidate_version_id,
        version_id=revision.version_id,
        body=revision.body,
        provider_config_id=revision.provider_config_id,
        upstream_model=revision.upstream_model,
        parameters=revision.parameters,
        fallback_answer=revision.fallback_answer,
    ).model_dump()
