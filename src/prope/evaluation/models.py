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
    Column("attempt_count", Integer, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)
