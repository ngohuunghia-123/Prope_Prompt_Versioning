"""The readiness schema — ADR-0067's five tables, and the one severity value that does not exist

Revision ID: 0029
Revises: 0028
Create Date: 2026-08-20

**No `blocker` severity, and the CHECK is where that decision is enforced.**
ADR-0067 §4 argues it out: `evaluation` runs real assertions against real
dispatches and is warn-only (A-016), so a module whose findings are partly
model-chosen cannot defensibly be a stronger gate; and blocking on a
SELF-DECLARED profile creates an incentive to misdeclare it, which corrupts the
input every rule in the module reads. A third enum value that did nothing would
be an argument for making it do something, filled in later by whoever is in a
hurry. `ck_readiness_report_severity_values` admits exactly two.

**`report` is written once and never updated, and the unique constraint is what
makes that safe under concurrency.** ADR-0067 moves the freeze off submit and
onto the card read, because release-control is a forbidden dependency in both
directions and a submit hook is an edge. Two concurrent reads of a
just-submitted revision therefore race, and the arbiter is
`uq_readiness_report_version` plus `ON CONFLICT DO NOTHING` — not an
application-level "does it exist yet" check, which is the race rather than the
fix.

**No foreign key leaves this schema.** `prompt_id`, `version_id`, `call_id` and
`actor_id` are values. The rule ADR-0054 established for `actor_id` and
revision 0028 restated for `call_id`: a constraint would point this module's
schema at another module's table, across an edge the module map does not draw.
`probe_case_result` is the one table with an FK, and it points at
`probe_run` — inside this schema, where a cascade is a parent-child cleanup
rather than a cross-module coupling.

**Retention differs per table and A-145 is satisfied here rather than later.**
`lane_b_cache` is derived and regenerates, so 30 days. `probe_case_result`
holds a bounded excerpt of model output about a body the workspace wrote —
smaller than `call_body`'s liability but not zero — so 180 days, and its parent
keeps the counts so a card written a year ago still reads. The other three are
somebody's judgement or a reviewer's decision record, and are kept: deleting a
frozen report breaks the same property release-control's rows have.
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, enable_tenant_rls, grant_table, reset_role

from alembic import op

revision: str = "0029"
down_revision: str | Sequence[str] | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: Per (workspace, prompt, rule) and deliberately NOT per revision. A dismissal
#: that expired on every save would be a nag with extra steps — the author would
#: re-dismiss the same six findings on every keystroke-debounced write, which is
#: the alert fatigue deck 6 slide 64 warns about, self-inflicted.
#:
#: `reason` is NOT NULL and non-empty: the dismissal rate per `rule_id` is this
#: module's honest metric (OQ-157), and a rate without reasons cannot tell "the
#: rule is wrong" from "the profile filter is wrong", which are opposite fixes.
CREATE_DISMISSAL = """
CREATE TABLE readiness.dismissal (
    workspace_id  text         NOT NULL,
    prompt_id     text         NOT NULL,
    rule_id       text         NOT NULL,

    reason        text         NOT NULL,

    -- A VALUE, never a foreign key. ADR-0054: a departing person's `access.user`
    -- row is tombstoned and their `actor_id` survives as an opaque value, and
    -- that is free precisely because nothing points at it.
    actor_id      text         NOT NULL,
    created_at    timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_readiness_dismissal PRIMARY KEY (workspace_id, prompt_id, rule_id),
    CONSTRAINT ck_readiness_dismissal_reason_not_blank
        CHECK (length(btrim(reason)) > 0)
);
"""

#: The reviewer's copy. Written ONCE, on the first card read after the revision
#: leaves `Draft`, and never updated — see the module docstring.
#:
#: `profile_snapshot` and `catalogue_version` are stored beside the findings for
#: ADR-0019's reason: the figure keeps the row that explains it. A report whose
#: admitting profile had to be re-read from `prompt_property` would silently
#: re-scope itself the moment somebody flipped `internal` to `public`, which is
#: the exact drift D-02 exists to make detectable.
CREATE_REPORT = """
CREATE TABLE readiness.report (
    id                 text         NOT NULL,
    workspace_id       text         NOT NULL,
    prompt_id          text         NOT NULL,

    -- A VALUE. `registry.revision` is another module's table.
    version_id         text         NOT NULL,

    profile_snapshot   jsonb        NOT NULL,
    rendered_findings  jsonb        NOT NULL,
    catalogue_version  text         NOT NULL,

    created_at         timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_readiness_report PRIMARY KEY (id),
    CONSTRAINT ck_readiness_report_id_prefix CHECK (id LIKE 'rdr\\_%'),

    -- The arbiter of the freeze race. See the module docstring.
    CONSTRAINT uq_readiness_report_version UNIQUE (workspace_id, version_id),

    CONSTRAINT ck_readiness_report_findings_is_array
        CHECK (jsonb_typeof(rendered_findings) = 'array')
);
"""

#: Deliberately NOT `evaluation.eval_run` (ADR-0067 §3). A probe measures
#: readiness; a suite measures a release. Nothing here is attached to a prompt,
#: no `dataset_attachment` row is written, and no cost delta sees it.
#:
#: `catalogue_ref` records `builtin:chong-tiem-prompt@1` verbatim so a result
#: stays explicable after the catalogue is bumped — the same reason
#: `ledger.call_record` stores `price_row_id` beside its cost. Bumping a set's
#: version mints a new id, so a run from before the bump keeps naming what it
#: actually ran.
CREATE_PROBE_RUN = """
CREATE TABLE readiness.probe_run (
    id              text         NOT NULL,
    workspace_id    text         NOT NULL,
    prompt_id       text         NOT NULL,
    version_id      text         NOT NULL,

    catalogue_ref   text[]       NOT NULL,

    status          text         NOT NULL,
    refused_count   integer      NOT NULL DEFAULT 0,
    leaked_count    integer      NOT NULL DEFAULT 0,
    error_count     integer      NOT NULL DEFAULT 0,

    actor_id        text         NOT NULL,
    started_at      timestamptz  NOT NULL DEFAULT now(),
    completed_at    timestamptz,

    CONSTRAINT pk_readiness_probe_run PRIMARY KEY (id),
    CONSTRAINT ck_readiness_probe_run_id_prefix CHECK (id LIKE 'prb\\_%'),

    CONSTRAINT ck_readiness_probe_run_status_values
        CHECK (status IN ('running', 'completed', 'partial', 'failed')),

    -- A run that has finished has a time; one that has not, has not. Without
    -- this a stuck row and a completed row look the same to the card.
    CONSTRAINT ck_readiness_probe_run_completion_is_whole
        CHECK ((status = 'running') = (completed_at IS NULL)),

    CONSTRAINT ck_readiness_probe_run_counts_are_not_negative
        CHECK (refused_count >= 0 AND leaked_count >= 0 AND error_count >= 0),

    CONSTRAINT ck_readiness_probe_run_names_a_catalogue
        CHECK (cardinality(catalogue_ref) > 0)
);
"""

#: `assertion_detail` is the one column in this schema holding text derived from
#: MODEL OUTPUT, and it is bounded and it expires (180 days). It exists so a
#: leaked case can be turned into a drafted case a person ticks, which is the
#: action the card offers — a score with no next step is deck 6's alert fatigue.
#:
#: `call_id` is the caller-generated `cal_` id (A-099), carried so a probe's
#: spend is attributable from the ledger side without this module ever reading
#: anything back. call-ledger is a sink and stays one.
CREATE_PROBE_CASE_RESULT = """
CREATE TABLE readiness.probe_case_result (
    id                text         NOT NULL,
    workspace_id      text         NOT NULL,
    probe_run_id      text         NOT NULL,

    case_ref          text         NOT NULL,
    outcome           text         NOT NULL,
    assertion_detail  text         NOT NULL DEFAULT '',
    latency_ms        integer,

    -- A VALUE. `ledger.call_record` is a sink this module may not read.
    call_id           text,

    created_at        timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_readiness_probe_case_result PRIMARY KEY (id),
    CONSTRAINT ck_readiness_probe_case_result_id_prefix CHECK (id LIKE 'prc\\_%'),

    -- refused = the prompt held. leaked = it complied with the injection.
    -- error  = the dispatch itself failed, which is neither and must not be
    --          counted as either — a provider timeout is not a guardrail win.
    CONSTRAINT ck_readiness_probe_case_result_outcome_values
        CHECK (outcome IN ('refused', 'leaked', 'error')),

    -- SR-7's storage-side half. The rail runs in the application before the
    -- insert; this is the backstop that makes an unbounded excerpt impossible
    -- even from a path that forgot to call it.
    CONSTRAINT ck_readiness_probe_case_result_detail_is_bounded
        CHECK (length(assertion_detail) <= 2000),

    CONSTRAINT fk_readiness_probe_case_result_run
        FOREIGN KEY (probe_run_id) REFERENCES readiness.probe_run (id) ON DELETE CASCADE
);
"""

#: Keyed on a fingerprint over (body_hash, profile, catalogue_version) —
#: evaluation's dataset-fingerprint pattern, for evaluation's reason: an edit
#: changes the fingerprint and the next read does the work again, and nothing
#: can disturb a result already rendered. Derived, bounded, and the shortest
#: retention term in the module.
CREATE_LANE_B_CACHE = """
CREATE TABLE readiness.lane_b_cache (
    workspace_id  text         NOT NULL,
    fingerprint   text         NOT NULL,

    findings      jsonb        NOT NULL,
    model         text         NOT NULL,
    created_at    timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_readiness_lane_b_cache PRIMARY KEY (workspace_id, fingerprint),
    CONSTRAINT ck_readiness_lane_b_cache_findings_is_array
        CHECK (jsonb_typeof(findings) = 'array')
);
"""

#: Every index leads with `workspace_id`, as every declared index in Prope does.
#: The RLS predicate is on that column, so an index that did not lead with it
#: would be an index the planner uses after filtering rather than before.
CREATE_INDEXES = (
    """
    CREATE INDEX ix_readiness_report_workspace_id_prompt_id
        ON readiness.report (workspace_id, prompt_id, created_at DESC)
    """,
    """
    CREATE INDEX ix_readiness_probe_run_workspace_id_version_id
        ON readiness.probe_run (workspace_id, version_id, started_at DESC)
    """,
    """
    CREATE INDEX ix_readiness_probe_case_result_run
        ON readiness.probe_case_result (workspace_id, probe_run_id)
    """,
    # Partial, and only the expiring table needs one: the retention sweep reads
    # by age and nothing else does.
    """
    CREATE INDEX ix_readiness_lane_b_cache_created_at
        ON readiness.lane_b_cache (created_at)
    """,
)


def upgrade() -> None:
    # The bootstrap connection creates the schema, as revisions 0012 and 0028 do
    # and for the same reason: the migration role deliberately holds no
    # database-level CREATE privilege. AUTHORIZATION makes every object below
    # migrate-owned, which is what ADR-0035's owner bypass rests on.
    op.execute("CREATE SCHEMA readiness AUTHORIZATION prope_migrate")

    # Before the role switch, and NOT optional. Table-level privileges are
    # checked only after schema USAGE, so without this the application ends up
    # with SELECT/INSERT/UPDATE on five tables it cannot reach at all, and the
    # error — `permission denied for schema readiness` — surfaces on a card read
    # as a 500 rather than as anything that names the cause.
    op.execute("GRANT USAGE ON SCHEMA readiness TO prope_app, prope_report")

    assume_migrate_role()

    op.execute(CREATE_DISMISSAL)
    op.execute(CREATE_REPORT)
    op.execute(CREATE_PROBE_RUN)
    op.execute(CREATE_PROBE_CASE_RESULT)
    op.execute(CREATE_LANE_B_CACHE)
    for statement in CREATE_INDEXES:
        op.execute(statement)

    enable_tenant_rls("readiness", "dismissal")
    enable_tenant_rls("readiness", "report")
    enable_tenant_rls("readiness", "probe_run")
    enable_tenant_rls("readiness", "probe_case_result")
    enable_tenant_rls("readiness", "lane_b_cache")

    # `report` gets no UPDATE and no DELETE. It is written once and it is a
    # reviewer's decision record — the same posture `history_event` has, for the
    # same reason, enforced the same way: by privilege rather than by a rule in
    # application code that a refactor can drop.
    grant_table("readiness", "report", app_privileges=["SELECT", "INSERT"])

    # `dismissal` may be deleted: un-dismissing is a legitimate act, and a person
    # who dismissed a finding by mistake must not need a migration to undo it.
    # It keeps no UPDATE — changing a reason in place would make the dismissal
    # rate readable and its reasons not.
    grant_table("readiness", "dismissal", app_privileges=["SELECT", "INSERT", "DELETE"])

    # The probe pair takes UPDATE because a run starts `running` and finishes,
    # and DELETE because `probe_case_result` expires at 180 days and the sweep
    # is an ordinary application delete.
    grant_table("readiness", "probe_run", app_privileges=["SELECT", "INSERT", "UPDATE"])
    grant_table(
        "readiness",
        "probe_case_result",
        app_privileges=["SELECT", "INSERT", "DELETE"],
    )

    # The cache is entirely disposable and says so in its grants.
    grant_table(
        "readiness",
        "lane_b_cache",
        app_privileges=["SELECT", "INSERT", "UPDATE", "DELETE"],
    )

    reset_role()


def downgrade() -> None:
    """Drops all five tables and the schema.

    Does not refuse, unlike revisions 0020 and 0026. Those guard
    ``ledger.call_record``, which is the accountability record and on which the
    application holds no DELETE at all. Nothing here is one: a readiness report
    is evidence attached to a decision that release-control records
    independently, and the approval itself survives untouched. Reverting the
    feature means discarding its findings, and pretending otherwise would be
    theatre.
    """
    assume_migrate_role()
    op.execute("DROP TABLE IF EXISTS readiness.lane_b_cache")
    op.execute("DROP TABLE IF EXISTS readiness.probe_case_result")
    op.execute("DROP TABLE IF EXISTS readiness.probe_run")
    op.execute("DROP TABLE IF EXISTS readiness.report")
    op.execute("DROP TABLE IF EXISTS readiness.dismissal")
    reset_role()
    op.execute("DROP SCHEMA IF EXISTS readiness")
