from collections.abc import Sequence

from ddl import assume_migrate_role, enable_tenant_rls, grant_table, reset_role

from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CREATE_EVAL_SUITE = """
CREATE TABLE evaluation.eval_suite (
    id               text         NOT NULL,
    workspace_id     text         NOT NULL,
    prompt_id        text         NOT NULL,
    name             text         NOT NULL,
    suite_version    integer      NOT NULL,
    output_modality  text         NOT NULL,
    case_count       integer      NOT NULL DEFAULT 0,
    created_by       text         NOT NULL,
    created_at       timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_eval_suite PRIMARY KEY (id),
    CONSTRAINT uq_eval_suite_prompt_id UNIQUE (prompt_id, name, suite_version),
    CONSTRAINT ck_eval_suite_id_prefix CHECK (id LIKE 'evs\\_%'),
    CONSTRAINT ck_eval_suite_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT ck_eval_suite_name_length CHECK (char_length(name) <= 100),
    CONSTRAINT ck_eval_suite_version_positive CHECK (suite_version > 0),
    CONSTRAINT ck_eval_suite_output_modality_values
        CHECK (output_modality IN ('text', 'structured')),
    CONSTRAINT ck_eval_suite_case_count_not_negative CHECK (case_count >= 0)
);
"""

CREATE_EVAL_CASE = """
CREATE TABLE evaluation.eval_case (
    id               text         NOT NULL,
    workspace_id     text         NOT NULL,
    suite_id         text         NOT NULL,
    ordinal          integer      NOT NULL,
    name             text         NOT NULL,
    input_messages   jsonb        NOT NULL,
    input_variables  jsonb        NOT NULL DEFAULT '{}'::jsonb,
    assertions       jsonb        NOT NULL DEFAULT '[]'::jsonb,
    created_at       timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_eval_case PRIMARY KEY (id),
    CONSTRAINT uq_eval_case_suite_id UNIQUE (suite_id, ordinal),
    CONSTRAINT ck_eval_case_id_prefix CHECK (id LIKE 'evc\\_%'),
    CONSTRAINT ck_eval_case_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT ck_eval_case_name_length CHECK (char_length(name) <= 200),
    CONSTRAINT ck_eval_case_ordinal_positive CHECK (ordinal > 0),
    CONSTRAINT ck_eval_case_input_messages_is_a_list
        CHECK (jsonb_typeof(input_messages) = 'array'),
    CONSTRAINT ck_eval_case_assertions_is_a_list
        CHECK (jsonb_typeof(assertions) = 'array'),

    CONSTRAINT fk_eval_case_suite_id
        FOREIGN KEY (suite_id)
        REFERENCES evaluation.eval_suite (id)
);
"""

CREATE_EVAL_RUN = """
CREATE TABLE evaluation.eval_run (
    id             text            NOT NULL,
    workspace_id   text            NOT NULL,
    prompt_id      text            NOT NULL,
    version_id     text            NOT NULL,
    suite_id       text            NOT NULL,
    role           text            NOT NULL,
    status         text            NOT NULL DEFAULT 'queued',
    refused_reason text,
    started_at     timestamptz,
    finished_at    timestamptz,
    pass_count     integer         NOT NULL DEFAULT 0,
    fail_count     integer         NOT NULL DEFAULT 0,
    error_count    integer         NOT NULL DEFAULT 0,
    input_tokens   integer,
    output_tokens  integer,
    cost_amount    numeric(20,10),
    cost_currency  text,
    priced_at      timestamptz,
    started_by     text            NOT NULL,

    CONSTRAINT pk_eval_run PRIMARY KEY (id),
    CONSTRAINT ck_eval_run_id_prefix CHECK (id LIKE 'evr\\_%'),
    CONSTRAINT ck_eval_run_role_values CHECK (role IN ('candidate', 'baseline')),
    CONSTRAINT ck_eval_run_status_values
        CHECK (status IN ('queued', 'running', 'completed', 'interrupted', 'refused')),
    CONSTRAINT ck_eval_run_counts_are_not_negative
        CHECK (pass_count >= 0 AND fail_count >= 0 AND error_count >= 0),
    CONSTRAINT ck_eval_run_cost_carries_currency
        CHECK ((cost_amount IS NULL) = (cost_currency IS NULL)),
    CONSTRAINT ck_eval_run_priced_carries_cost
        CHECK (priced_at IS NULL OR cost_amount IS NOT NULL),
    CONSTRAINT ck_eval_run_refused_reason_belongs_to_refused
        CHECK (refused_reason IS NULL OR status = 'refused'),

    CONSTRAINT fk_eval_run_suite_id
        FOREIGN KEY (suite_id)
        REFERENCES evaluation.eval_suite (id)
);
"""

CREATE_CASE_RESULT = """
CREATE TABLE evaluation.case_result (
    id                 text         NOT NULL,
    workspace_id       text         NOT NULL,
    run_id             text         NOT NULL,
    case_id            text         NOT NULL,
    outcome            text         NOT NULL,
    assertion_results  jsonb        NOT NULL DEFAULT '[]'::jsonb,
    output_content     text,
    latency_ms         integer,
    input_tokens       integer,
    output_tokens      integer,
    error_code         text,
    attempt_count      integer      NOT NULL DEFAULT 1,
    created_at         timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_case_result PRIMARY KEY (id),
    CONSTRAINT uq_case_result_run_id UNIQUE (run_id, case_id),
    CONSTRAINT ck_case_result_id_prefix CHECK (id LIKE 'evcr\\_%'),
    CONSTRAINT ck_case_result_outcome_values
        CHECK (outcome IN ('pass', 'fail', 'error')),
    CONSTRAINT ck_case_result_error_carries_a_code
        CHECK ((outcome = 'error') = (error_code IS NOT NULL)),
    CONSTRAINT ck_case_result_attempt_count_positive CHECK (attempt_count >= 1),
    CONSTRAINT ck_case_result_usage_is_whole
        CHECK ((input_tokens IS NULL) = (output_tokens IS NULL)),

    CONSTRAINT fk_case_result_run_id
        FOREIGN KEY (run_id)
        REFERENCES evaluation.eval_run (id),

    CONSTRAINT fk_case_result_case_id
        FOREIGN KEY (case_id)
        REFERENCES evaluation.eval_case (id)
);
"""

CREATE_CLAIM_NEXT_RUN = """
CREATE FUNCTION evaluation.claim_next_run(p_max_concurrent_runs integer)
RETURNS TABLE (
    run_id       text,
    workspace_id text,
    prompt_id    text,
    version_id   text,
    suite_id     text
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
    claimed evaluation.eval_run%ROWTYPE;
BEGIN
    SELECT r.* INTO claimed
    FROM   evaluation.eval_run AS r
    WHERE  r.status = 'queued'
      AND  (SELECT count(*)
              FROM evaluation.eval_run AS r2
             WHERE r2.workspace_id = r.workspace_id
               AND r2.status = 'running') < p_max_concurrent_runs
    ORDER  BY r.id
    FOR UPDATE SKIP LOCKED
    LIMIT  1;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    UPDATE evaluation.eval_run AS r
       SET status = 'running', started_at = now()
     WHERE r.id = claimed.id;

    run_id       := claimed.id;
    workspace_id := claimed.workspace_id;
    prompt_id    := claimed.prompt_id;
    version_id   := claimed.version_id;
    suite_id     := claimed.suite_id;
    RETURN NEXT;
END;
$function$;
"""

FUNCTION_PRIVILEGES = ("evaluation.claim_next_run(integer)",)

CREATE_INDEXES = (
    """
    CREATE INDEX ix_eval_run_workspace_id_status
        ON evaluation.eval_run (workspace_id, status)
    """,
    """
    CREATE INDEX ix_eval_run_workspace_id_prompt_id
        ON evaluation.eval_run (workspace_id, prompt_id, id DESC)
    """,
    """
    CREATE INDEX ix_eval_run_suite_id_version_id
        ON evaluation.eval_run (suite_id, version_id, status)
    """,
    """
    CREATE INDEX ix_eval_suite_workspace_id_prompt_id
        ON evaluation.eval_suite (workspace_id, prompt_id, name, suite_version DESC)
    """,
    """
    CREATE INDEX ix_eval_case_suite_id_ordinal
        ON evaluation.eval_case (suite_id, ordinal)
    """,
    """
    CREATE INDEX ix_case_result_run_id_created_at
        ON evaluation.case_result (run_id, created_at DESC)
    """,
)


def upgrade() -> None:
    op.execute("CREATE SCHEMA evaluation AUTHORIZATION prope_migrate")
    op.execute("GRANT USAGE ON SCHEMA evaluation TO prope_app, prope_report")

    assume_migrate_role()

    op.execute(CREATE_EVAL_SUITE)
    op.execute(CREATE_EVAL_CASE)
    op.execute(CREATE_EVAL_RUN)
    op.execute(CREATE_CASE_RESULT)

    op.execute(CREATE_CLAIM_NEXT_RUN)

    for statement in CREATE_INDEXES:
        op.execute(statement)

    enable_tenant_rls("evaluation", "eval_suite")
    enable_tenant_rls("evaluation", "eval_case")
    enable_tenant_rls("evaluation", "eval_run")
    enable_tenant_rls("evaluation", "case_result")

    grant_table("evaluation", "eval_suite", app_privileges=["SELECT", "INSERT"])
    grant_table("evaluation", "eval_case", app_privileges=["SELECT", "INSERT"])
    op.execute("GRANT UPDATE (case_count) ON evaluation.eval_suite TO prope_app")

    grant_table("evaluation", "eval_run", app_privileges=["SELECT", "INSERT", "UPDATE"])
    grant_table("evaluation", "case_result", app_privileges=["SELECT", "INSERT"])

    for signature in FUNCTION_PRIVILEGES:
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO prope_app")

    reset_role()


def downgrade() -> None:
    assume_migrate_role()

    op.execute("DROP FUNCTION IF EXISTS evaluation.claim_next_run(integer)")
    op.execute("DROP TABLE IF EXISTS evaluation.case_result")
    op.execute("DROP TABLE IF EXISTS evaluation.eval_run")
    op.execute("DROP TABLE IF EXISTS evaluation.eval_case")
    op.execute("DROP TABLE IF EXISTS evaluation.eval_suite")

    reset_role()

    op.execute("DROP SCHEMA IF EXISTS evaluation CASCADE")
