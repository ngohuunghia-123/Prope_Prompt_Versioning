"""The improvement schema — ADR-0068's four tables, and the two indexes that ARE the controls

Revision ID: 0033
Revises: 0032
Create Date: 2026-08-20

**Two partial unique indexes here are security controls rather than performance
choices, and both are stated in `prompt-improvement.lock.yml` as such.**

`uq_improvement_proposal_one_open_per_prompt` is the rate cap. At most one open
proposal per prompt — the control the rubber-stamp literature asks for, because
*"break down large batches"* is worthless if a batch can be a hundred. In the
database rather than in a service check, for the reason every other control in
this product is: a check in application code is a control somebody refactors
away, and nothing fails when they do.

`uq_improvement_finding_one_open_per_detector` is the dedupe. A recurring signal
bumps `occurrence_count` and `last_seen` rather than opening a second row, so an
inbox says *"this has happened 14 times"* instead of showing fourteen items. That
is the same alert-fatigue prescription applied to the data model instead of to a
render.

**`sweep` has no retention term and the absence is load-bearing.** `is_first_sweep`
is what makes the summary-instead-of-two-hundred-findings behaviour a property of
the DATA rather than of a code path somebody can regress. A retention term on this
table would let a dormant workspace's rows age out and silently make it a
first-time workspace again — a bug that reports itself as a friendly summary
rather than as an error. One row per workspace per day is 365 rows a year.

**No foreign key leaves this schema.** `prompt_id`, `version_id`, `gate_run_id`
and every actor column are values. The rule ADR-0054 established for `actor_id`
and revisions 0028 and 0029 restated for `call_id`, applied here without
exception. `proposal.finding_id` points at `improvement.finding` — inside this
schema, where a cascade is a parent-child cleanup rather than a cross-module
coupling.

**No `blocker` severity, inherited from ADR-0067 §4 rather than re-argued.** A
post-publish finding has even less standing to gate a future decision than a
pre-publish one, so `ck_improvement_finding_severity_values` admits the same two
values `readiness` does.
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, enable_tenant_rls, grant_table, reset_role

from alembic import op

revision: str = "0033"
down_revision: str | Sequence[str] | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: The durable half of a finding. Unlike a readiness finding — recomputed from a
#: body on every card read and frozen at submit — this one is a row with a life:
#: it opens, recurs, and is closed by a person or by the signal going away.
#:
#: `params` carries the detector's numbers (the two windows' counts, the ratio,
#: the percentile) so the card can render *"truncation went from 2% to 31%"*
#: without re-reading a window that has since moved. ADR-0019's rule: the figure
#: keeps the row that explains it.
#:
#: `evidence_line` is the ONE sentence the triage model wrote, already through
#: the output rail — length-capped, URL-free, markdown-link-free and
#: credential-redacted BEFORE storage. The CHECK below is the backstop that makes
#: an unbounded line impossible even from a path that forgot to call the rail.
CREATE_FINDING = """
CREATE TABLE improvement.finding (
    id                text         NOT NULL,
    workspace_id      text         NOT NULL,

    -- A VALUE. `registry.prompt_property` is another module's table.
    prompt_id         text         NOT NULL,

    detector_id       text         NOT NULL,
    severity          text         NOT NULL,
    params            jsonb        NOT NULL DEFAULT '{}'::jsonb,
    evidence_line     text,

    first_seen        timestamptz  NOT NULL,
    last_seen         timestamptz  NOT NULL,
    occurrence_count  integer      NOT NULL DEFAULT 1,

    status            text         NOT NULL DEFAULT 'open',
    dismissed_reason  text,
    dismissed_by      text,
    dismissed_at      timestamptz,

    created_at        timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_improvement_finding PRIMARY KEY (id),
    CONSTRAINT ck_improvement_finding_id_prefix CHECK (id LIKE 'fnd\\_%'),

    -- ADR-0067 §4, inherited rather than re-argued. There is no third value and
    -- the schema must not carry one: a value that does nothing is an argument
    -- for making it do something, filled in later by whoever is in a hurry.
    CONSTRAINT ck_improvement_finding_severity_values
        CHECK (severity IN ('advice', 'warning')),

    CONSTRAINT ck_improvement_finding_status_values
        CHECK (status IN ('open', 'dismissed', 'resolved')),

    -- A dismissal without a reason makes the dismissal RATE unreadable: it
    -- cannot tell "the detector is wrong" from "the remedy is wrong", which are
    -- opposite fixes. `readiness.dismissal`'s rule, and OQ-157's input.
    CONSTRAINT ck_improvement_finding_dismissal_carries_a_reason
        CHECK (status <> 'dismissed'
               OR (dismissed_reason IS NOT NULL
                   AND length(btrim(dismissed_reason)) > 0
                   AND dismissed_by IS NOT NULL
                   AND dismissed_at IS NOT NULL)),

    CONSTRAINT ck_improvement_finding_occurrence_count_is_positive
        CHECK (occurrence_count >= 1),

    CONSTRAINT ck_improvement_finding_evidence_line_is_bounded
        CHECK (evidence_line IS NULL OR char_length(evidence_line) <= 400)
);
"""

#: The queue. One open row per prompt, by index — see the module docstring.
#:
#: `candidate_body` is stored rather than regenerated so that what was reviewed
#: and what is applied cannot differ. chat-orchestrator's stored-arguments
#: property, and the reason is the same: a proposal that re-derived its body at
#: accept time would be a different proposal wearing the reviewed one's id.
#:
#: `gate_delta` holds the per-case eval result the card renders. It is stored
#: because the gate run's own rows expire on evaluation's terms and a card
#: written a year ago must still read — ADR-0019's rule again.
CREATE_PROPOSAL = """
CREATE TABLE improvement.proposal (
    id              text         NOT NULL,
    workspace_id    text         NOT NULL,
    prompt_id       text         NOT NULL,
    finding_id      text         NOT NULL,

    remedy_kind     text         NOT NULL,
    remedy_family   text,

    -- NULL for `note` and `case`: neither proposes a body. The CHECK below is
    -- what keeps the pairing honest, because a note carrying a candidate body
    -- would be an edit that nothing gated.
    candidate_body  text,

    -- A VALUE. `evaluation.eval_run` is another module's table, and this id is
    -- carried so the delta stays attributable without this module reading one
    -- back.
    gate_run_id     text,
    gate_delta      jsonb,

    status          text         NOT NULL DEFAULT 'open',
    decided_by      text,
    decided_at      timestamptz,
    expires_at      timestamptz  NOT NULL,

    created_at      timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_improvement_proposal PRIMARY KEY (id),
    CONSTRAINT ck_improvement_proposal_id_prefix CHECK (id LIKE 'prp\\_%'),

    CONSTRAINT ck_improvement_proposal_remedy_kind_values
        CHECK (remedy_kind IN ('note', 'case', 'edit')),

    -- The closed family catalogue (ADR-0068 §3). Free-form rewriting does not
    -- exist, and this is where that sentence is enforced rather than intended.
    CONSTRAINT ck_improvement_proposal_remedy_family_values
        CHECK (remedy_family IS NULL OR remedy_family IN (
            'tighten_refusal_block', 'add_length_rule', 'add_brevity_clause'
        )),

    CONSTRAINT ck_improvement_proposal_status_values
        CHECK (status IN ('open', 'accepted', 'dismissed', 'expired')),

    -- SR-3, in the schema. An `edit` carries a body, a family AND a gate run —
    -- a row that proposed a body without a gate behind it is exactly what this
    -- module refuses to render, and refusing it here means it cannot be stored
    -- either. Anything that is not an edit carries none of the three.
    CONSTRAINT ck_improvement_proposal_an_edit_is_gated
        CHECK (
            (remedy_kind = 'edit'
             AND candidate_body IS NOT NULL
             AND remedy_family IS NOT NULL
             AND gate_run_id IS NOT NULL
             AND gate_delta IS NOT NULL)
            OR
            (remedy_kind <> 'edit'
             AND candidate_body IS NULL
             AND gate_run_id IS NULL)
        ),

    CONSTRAINT ck_improvement_proposal_a_decision_has_an_actor
        CHECK (status IN ('open', 'expired')
               OR (decided_by IS NOT NULL AND decided_at IS NOT NULL)),

    CONSTRAINT fk_improvement_proposal_finding
        FOREIGN KEY (finding_id) REFERENCES improvement.finding (id) ON DELETE CASCADE
);
"""

#: One row per workspace per pass. The counters are the sweep's own record of
#: what it looked at, which is what makes "nothing was wrong" distinguishable
#: from "nothing ran" — the failure ADR-0051 exists to prevent, where an
#: unscoped read returns zero rows and the job looks healthy.
CREATE_SWEEP = """
CREATE TABLE improvement.sweep (
    id               text         NOT NULL,
    workspace_id     text         NOT NULL,

    window_start     timestamptz  NOT NULL,
    window_end       timestamptz  NOT NULL,

    prompts_scanned  integer      NOT NULL DEFAULT 0,
    findings_opened  integer      NOT NULL DEFAULT 0,
    is_first_sweep   boolean      NOT NULL DEFAULT false,

    completed_at     timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_improvement_sweep PRIMARY KEY (id),
    CONSTRAINT ck_improvement_sweep_id_prefix CHECK (id LIKE 'swp\\_%'),
    CONSTRAINT ck_improvement_sweep_window_is_ordered CHECK (window_end > window_start)
);
"""

#: The re-probe schedule. One row per workspace, `enabled` FALSE by default —
#: the probe spends the workspace's provider credit, so opt-in is the whole
#: posture and a default of true would bill somebody for a feature they never
#: chose.
#:
#: Empty `namespaces` and `prompt_ids` with `enabled = true` means EVERY released
#: prompt. That is a deliberate choice a person makes on a screen that shows the
#: estimated weekly cost first (A-166), not an accident of two empty arrays.
CREATE_SCHEDULE = """
CREATE TABLE improvement.schedule (
    workspace_id  text         NOT NULL,

    enabled       boolean      NOT NULL DEFAULT false,
    cadence_days  integer      NOT NULL DEFAULT 7,

    namespaces    text[]       NOT NULL DEFAULT ARRAY[]::text[],
    prompt_ids    text[]       NOT NULL DEFAULT ARRAY[]::text[],

    last_run_at   timestamptz,

    updated_by    text         NOT NULL,
    updated_at    timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_improvement_schedule PRIMARY KEY (workspace_id),

    -- Bounded on both ends. Daily is the floor because the probe costs money and
    -- a cadence shorter than the sweep that feeds it measures nothing new;
    -- ninety days is the ceiling because a guardrail checked less often than a
    -- quarter is a guardrail nobody is checking.
    CONSTRAINT ck_improvement_schedule_cadence_is_bounded
        CHECK (cadence_days BETWEEN 1 AND 90)
);
"""

#: Every index leads with `workspace_id`, as every declared index in Prope does.
#: The RLS predicate is on that column, so an index that did not lead with it
#: would be an index the planner uses after filtering rather than before.
CREATE_INDEXES = (
    # THE DEDUPE. A recurring signal bumps a count; it does not open a second
    # row. Partial, because a closed finding must not block a genuinely new
    # occurrence of the same detector months later.
    """
    CREATE UNIQUE INDEX uq_improvement_finding_one_open_per_detector
        ON improvement.finding (workspace_id, prompt_id, detector_id)
        WHERE status = 'open'
    """,
    # THE RATE CAP (SR-2). One open proposal per prompt, and the second one
    # waits. This is a control, not an optimisation.
    """
    CREATE UNIQUE INDEX uq_improvement_proposal_one_open_per_prompt
        ON improvement.proposal (workspace_id, prompt_id)
        WHERE status = 'open'
    """,
    # The inbox: open findings for a workspace, newest activity first. The
    # `visible_subject_filter` set narrows it afterwards, in the caller's own
    # WHERE clause (ADR-0020).
    """
    CREATE INDEX ix_improvement_finding_workspace_id_status_last_seen
        ON improvement.finding (workspace_id, status, last_seen DESC)
    """,
    # The per-prompt tab, beside ADR-0055's call-records tab.
    """
    CREATE INDEX ix_improvement_finding_workspace_id_prompt_id
        ON improvement.finding (workspace_id, prompt_id, last_seen DESC)
    """,
    """
    CREATE INDEX ix_improvement_proposal_workspace_id_finding_id
        ON improvement.proposal (workspace_id, finding_id)
    """,
    # The expiry sweep reads by deadline and nothing else does. Partial, so it
    # holds only the rows that can still expire.
    """
    CREATE INDEX ix_improvement_proposal_expires_at
        ON improvement.proposal (expires_at)
        WHERE status = 'open'
    """,
    # `is_first_sweep` is answered by "does this workspace have ANY sweep row",
    # which is this index answering EXISTS rather than a count.
    """
    CREATE INDEX ix_improvement_sweep_workspace_id_completed_at
        ON improvement.sweep (workspace_id, completed_at DESC)
    """,
)


def upgrade() -> None:
    # The bootstrap connection creates the schema, as revisions 0012, 0028 and
    # 0029 do and for the same reason: the migration role deliberately holds no
    # database-level CREATE privilege. AUTHORIZATION makes every object below
    # migrate-owned, which is what ADR-0035's owner bypass rests on.
    op.execute("CREATE SCHEMA improvement AUTHORIZATION prope_migrate")

    # Before the role switch, and NOT optional. Table privileges are checked
    # only after schema USAGE, so without this the application ends up with
    # grants on four tables it cannot reach at all, and the error —
    # `permission denied for schema improvement` — surfaces on an inbox read as
    # a 500 rather than as anything that names the cause. Revision 0028's
    # docstring warns about exactly this omission.
    op.execute("GRANT USAGE ON SCHEMA improvement TO prope_app, prope_report")

    assume_migrate_role()

    op.execute(CREATE_FINDING)
    op.execute(CREATE_PROPOSAL)
    op.execute(CREATE_SWEEP)
    op.execute(CREATE_SCHEDULE)
    for statement in CREATE_INDEXES:
        op.execute(statement)

    enable_tenant_rls("improvement", "finding")
    enable_tenant_rls("improvement", "proposal")
    enable_tenant_rls("improvement", "sweep")
    enable_tenant_rls("improvement", "schedule")

    # `finding` takes UPDATE because it recurs and is dismissed, and DELETE
    # because a closed one expires at 365 days on an ordinary application sweep.
    grant_table(
        "improvement",
        "finding",
        app_privileges=["SELECT", "INSERT", "UPDATE", "DELETE"],
    )

    # `proposal` likewise: it is decided, it expires, and a decided one is
    # deleted at 180 days.
    grant_table(
        "improvement",
        "proposal",
        app_privileges=["SELECT", "INSERT", "UPDATE", "DELETE"],
    )

    # **`sweep` gets NO DELETE, and that is the retention decision expressed as
    # a privilege.** Its rows are what `is_first_sweep` is computed from, so a
    # deletion would silently make a dormant workspace a first-time workspace
    # again. A term written only in a lock file is a term a later sweep job can
    # contradict; a missing grant is not.
    grant_table("improvement", "sweep", app_privileges=["SELECT", "INSERT"])

    # One row per workspace, upserted by the schedule route.
    grant_table(
        "improvement",
        "schedule",
        app_privileges=["SELECT", "INSERT", "UPDATE"],
    )

    reset_role()


def downgrade() -> None:
    """Drops all four tables and the schema.

    Does not refuse, unlike revisions 0020 and 0026. Those guard
    ``ledger.call_record``, which is the accountability record and on which the
    application holds no DELETE at all. Nothing here is one: a finding is a
    measurement that can be taken again from data that is still in the ledger,
    and the one part of this module that IS accountability — who decided what
    the machine proposed — lives in ``history.history_event`` and is untouched
    by this revision. Reverting the feature therefore loses a queue and no
    decision.
    """
    assume_migrate_role()
    op.execute("DROP TABLE improvement.proposal")
    op.execute("DROP TABLE improvement.finding")
    op.execute("DROP TABLE improvement.sweep")
    op.execute("DROP TABLE improvement.schedule")
    reset_role()
    op.execute("DROP SCHEMA improvement")
