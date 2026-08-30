"""The App-Agent LLM call cache — one write-once, per-workspace, TTL'd row.

The design pack (`docs/agent-design/cache/`) decided the shape; this revision ships
`evaluation.llm_cache`, keyed on a content hash of everything the model was asked and
holding only the **gated** model output plus the token counts of the call that produced it.

**What may be stored is the load-bearing decision (03-D1).** The prompt body and title are
untrusted data (A-020, A-046) and are hashed into the key, never stored — a row leaks nothing
about the body that produced it. The stored `findings` JSON is the model's gated output, a
bounded array of `{dataset_id, name, reason, confidence}` entries, which is product data the
existing suggestion gate already owns.

**Write-once with the readiness freeze's arbiter (01-D2).** Two simultaneous misses of one
key race, and the arbiter is `uq_evaluation_llm_cache` plus `ON CONFLICT DO NOTHING` followed
by a re-read — not an application-level "does it exist yet" check, which is the race rather
than the fix.

**The cache is derived and disposable (04-D1).** No person acts on a row, no decision is
recorded, and the TTL is enforced at read, not at write, so an expired row simply stops being
served. DELETE is granted because an operator must be able to evict a row — the only manual
invalidation surface in v1 (00-D5).

Revision ID: 0055
Revises: 0054
Create Date: 2026-08-30
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, enable_tenant_rls, grant_table, reset_role

from alembic import op

revision: str = "0055"
down_revision: str | Sequence[str] | None = "0054"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: ``cache_key`` is the SHA-256 content hash over (body, title, catalogue, schema
#: version, model, extra_body) — the design's 02-D4/D7/D8. ``program`` names the
#: DSPy program that produced the row (``suggest_datasets`` today), so one table
#: serves every future caller without a per-module table (01-D1).
#:
#: ``findings`` is the GATED model output, bounded by the schema the suggestion
#: gate produces. The JSON-array CHECK is the storage-side rail (03-D6): the same
#: ``jsonb_typeof = 'array'`` shape `readiness.lane_b_cache` carries, so an
#: unbounded or non-array value is refused by the database.
CREATE_LLM_CACHE = """
CREATE TABLE evaluation.llm_cache (
    workspace_id   text         NOT NULL,
    cache_key      text         NOT NULL,
    program        text         NOT NULL,
    model          text         NOT NULL,

    findings       jsonb        NOT NULL,
    input_tokens   integer      NOT NULL DEFAULT 0,
    output_tokens  integer      NOT NULL DEFAULT 0,
    created_at     timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_evaluation_llm_cache PRIMARY KEY (workspace_id, cache_key),
    CONSTRAINT ck_evaluation_llm_cache_key_is_a_hex_digest
        CHECK (cache_key ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_evaluation_llm_cache_program_not_blank
        CHECK (btrim(program) <> ''),
    CONSTRAINT ck_evaluation_llm_cache_model_not_blank
        CHECK (btrim(model) <> ''),
    CONSTRAINT ck_evaluation_llm_cache_findings_is_array
        CHECK (jsonb_typeof(findings) = 'array'),
    CONSTRAINT ck_evaluation_llm_cache_tokens_not_negative
        CHECK (input_tokens >= 0 AND output_tokens >= 0)
);
"""

#: TTL is enforced at READ (the repository filters on ``created_at``), so no
#: partial index is needed for correctness. The created_at index is what a
#: future retention sweep reads by age — the same partial, age-only shape
#: `readiness.lane_b_cache` carries (00-D13).
CREATE_INDEXES: tuple[str, ...] = (
    """
    CREATE INDEX ix_evaluation_llm_cache_created_at
        ON evaluation.llm_cache (created_at)
    """,
)


def upgrade() -> None:
    assume_migrate_role()

    op.execute(CREATE_LLM_CACHE)
    for statement in CREATE_INDEXES:
        op.execute(statement)

    enable_tenant_rls("evaluation", "llm_cache")

    # Full CRUD. The cache is derived and disposable; DELETE is the only manual
    # invalidation surface in v1 (00-D5). `prope_report` gets SELECT because a
    # cache row is metrics-shaped derived data, not a decision record (03-D8).
    grant_table(
        "evaluation", "llm_cache", app_privileges=["SELECT", "INSERT", "UPDATE", "DELETE"]
    )

    reset_role()


def downgrade() -> None:
    """Drop the cache. Nothing else is affected — the cache is derived data,
    and losing an optimization is not corruption (01-D4)."""
    assume_migrate_role()
    op.execute("DROP TABLE IF EXISTS evaluation.llm_cache")
    reset_role()
