from sqlalchemy import Column, DateTime, Integer, Numeric, Table, Text
from sqlalchemy.dialects.postgresql import JSONB

from prope.db.metadata import metadata

TIMESTAMPTZ = DateTime(timezone=True)

SCHEMA = "evaluation"

eval_suite = Table(
    "eval_suite",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("prompt_id", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("suite_version", Integer, nullable=False),
    Column("output_modality", Text, nullable=False),
    Column("case_count", Integer, nullable=False),
    Column("created_by", Text, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)

eval_case = Table(
    "eval_case",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("suite_id", Text, nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("name", Text, nullable=False),
    Column("input_messages", JSONB, nullable=False),
    Column("input_variables", JSONB, nullable=False),
    Column("assertions", JSONB, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)

#: The workspace's own half of the dataset library. Migration 0019. Mutable,
#: unlike ``eval_suite`` — a dataset is the object somebody edits and a suite is
#: the immutable copy a run measured with.
dataset = Table(
    "dataset",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("folder", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("kind", Text, nullable=False),
    Column("output_modality", Text, nullable=False),
    Column("case_count", Integer, nullable=False),
    Column("created_by", Text, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    Column("updated_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)

#: Field for field the same as ``eval_case`` above, deliberately:
#: materialisation copies one into the other, and a shape that drifted would
#: turn a copy into a translation.
dataset_case = Table(
    "dataset_case",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("dataset_id", Text, nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("name", Text, nullable=False),
    Column("input_messages", JSONB, nullable=False),
    Column("input_variables", JSONB, nullable=False),
    Column("assertions", JSONB, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)

#: Which library datasets a prompt has chosen, and which immutable suite each
#: choice was last materialised into. Migration 0018. Composite primary key
#: rather than a minted id, for ``registry.folder``'s reason: nothing references
#: an attachment, and ``(workspace_id, prompt_id, dataset_id)`` is already the
#: natural key every query uses.
dataset_attachment = Table(
    "dataset_attachment",
    metadata,
    Column("workspace_id", Text, primary_key=True),
    Column("prompt_id", Text, primary_key=True),
    Column("dataset_id", Text, primary_key=True),
    Column("suite_name", Text, nullable=False),
    Column("materialised_suite_id", Text),
    Column("materialised_fingerprint", Text),
    Column("attached_by", Text, nullable=False),
    Column("attached_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)

eval_run = Table(
    "eval_run",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("prompt_id", Text, nullable=False),
    Column("version_id", Text, nullable=False),
    Column("suite_id", Text, nullable=False),
    Column("role", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("refused_reason", Text),
    Column("started_at", TIMESTAMPTZ),
    Column("finished_at", TIMESTAMPTZ),
    Column("pass_count", Integer, nullable=False),
    Column("fail_count", Integer, nullable=False),
    Column("error_count", Integer, nullable=False),
    Column("input_tokens", Integer),
    Column("output_tokens", Integer),
    Column("cost_amount", Numeric(20, 10)),
    Column("cost_currency", Text),
    Column("priced_at", TIMESTAMPTZ),
    Column("started_by", Text, nullable=False),
    schema=SCHEMA,
)

case_result = Table(
    "case_result",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("run_id", Text, nullable=False),
    Column("case_id", Text, nullable=False),
    Column("outcome", Text, nullable=False),
    Column("assertion_results", JSONB, nullable=False),
    Column("output_content", Text),
    Column("latency_ms", Integer),
    Column("input_tokens", Integer),
    Column("output_tokens", Integer),
    Column("error_code", Text),
    Column("error_detail", Text),
    Column("attempt_count", Integer, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)

#: The App-Agent LLM call cache. Migration 0055. Write-once derived data, keyed
#: on a content hash of everything the model was asked; holds only the gated
#: model output and the token counts of the call that produced it (A-020/A-046
#: keep the prompt body out of the row and out of the key's meaning).
llm_cache = Table(
    "llm_cache",
    metadata,
    Column("workspace_id", Text, primary_key=True),
    Column("cache_key", Text, primary_key=True),
    Column("program", Text, nullable=False),
    Column("model", Text, nullable=False),
    Column("findings", JSONB, nullable=False),
    Column("input_tokens", Integer, nullable=False),
    Column("output_tokens", Integer, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)
