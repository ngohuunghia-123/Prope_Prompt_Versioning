"""the sixth ledger table, and the one guarantee this module chose not to carry

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-10

``ledger.workspace_retention``: one row per workspace, holding the window a body
written from now on is stamped against. It arrives with its whole guarantee
stack in one revision — columns, a named CHECK, the tenant policy and the grant
matrix — which is the shape 0002 established and 0003 repeated.

**D-09 — THIS IS A SIXTH TABLE, AND THE LOCK FILE NAMES FIVE.**
``docs/modules/call-ledger.lock.yml`` ``data.owns`` lists ``call_record``,
``call_body``, ``price_table``, ``workspace_spend`` and ``spend_ceiling``. This
is a deviation from that field and it is declared rather than absorbed: the
conflict is raised as ``docs/brainstorm/open_questions/OQ-018.md``, naming the
field, and per ``.planning/BSP-LINK.md`` the spec is NOT edited to agree.

The reasoning D-09 gives, restated here because a reader of this revision should
not have to find the CONTEXT file to know why the table exists. A spend ceiling
and a retention window are two policies with different owners and different
lifecycles. Folding the window onto ``spend_ceiling`` would put them in one row,
and a ``PUT /api/v1/workspaces/{id}/spend-ceiling`` that writes the whole row
would then clobber a retention window nobody in that request ever mentioned. A
generic key/value settings table was the other candidate and is worse: it cannot
carry ``ck_workspace_retention_window_is_positive``, because a CHECK over a text
value column would have to know which key it was looking at.

**D-10 — ``expires_at`` IS STAMPED ONCE AT WRITE AND NEVER REWRITTEN.**
``write_records`` computes ``created_at + retention_window`` at insert
(``src/prope/call_ledger/writer.py``), and nothing anywhere revisits that value.
Shortening a workspace's window therefore applies only to bodies written after
the change; every existing row keeps the expiry it was given. This is A-106 read
literally — the deletion job is an index scan on one column rather than a join
against a settings table that may have changed since — and the consequence is
stated rather than hidden: **a workspace that tightens its policy waits up to the
OLD window for its existing bodies, and ``oldest_body_age_seconds`` reads above
the new window meanwhile.**

There is deliberately no backfill. Rewriting ``expires_at`` on the existing rows
would be an ``UPDATE`` on ``ledger.call_body``, and 0003 granted ``prope_app``
exactly ``SELECT``, ``INSERT`` and ``DELETE`` on that table with the comment
"bodies are written once and deleted". Buying a backfill means widening a grant
Phase 1 withheld on stated reasoning, on the largest table in the system, so that
a policy change can take effect a few days earlier. It is not bought here.

**NO TEST RIG EDIT IS NEEDED, AND THAT IS THE POINT.** ADR-0045's coverage walk
enumerates tables from ``pg_class`` and asserts a ``workspace_id`` column, row
security enabled and a policy on each (``tests/architecture/test_tenant_coverage
.py``); the truncate fixture enumerates them from ``pg_tables``
(``tests/conftest.py``). Neither is told this table's name. So the table inherits
both for free, and if this revision forgot ``enable_tenant_rls`` the walk would
go red on its own rather than waiting for a reviewer to notice. This is the first
table added since Phase 1's five, and therefore the first real test of that
claim.

**THE A-055 GUARD THIS REVISION DELIBERATELY DOES NOT ADD.**
No ``call_body`` row may ever exist for a ``source = 'eval'`` call record
(A-055). There is no database constraint behind that rule and this revision does
not add one. A ``CHECK`` cannot reach another table, so the only shape that works
is a ``BEFORE INSERT`` trigger on ``call_body`` looking the referenced
``call_record.source`` up on every insert.

It is refused for three reasons, recorded here as a **knowing exception to this
project's database-first pattern** rather than left as an oversight:

1. It would put a per-row lookup on the highest-volume insert path in the system.
   ``call_body`` takes one row per gateway call, and the drain inserts them in
   batches; a trigger turns every one of those into an index probe against
   ``call_record``.
2. ``write_records`` is already the single choke point, and it already refuses —
   the raise is at ``src/prope/call_ledger/writer.py``, in the loop, before any
   row is built. No other code in this module writes ``ledger.call_body``.
3. ``docs/modules/call-ledger.lock.yml`` never asked for the trigger, and
   ``.planning/BSP-LINK.md`` forbids inventing schema the spec did not declare.

Because the guarantee lives in Python and not in the engine, the ABSENCE is
asserted rather than assumed: ``tests/security/test_eval_no_body_boundary.py``
proves both halves — that the write path refuses, and that a hand-written INSERT
as ``prope_migrate`` succeeds. A later phase that adds a body reader then
inherits a recorded boundary instead of a belief.

TYPES follow 0003. ``workspace_id`` and ``updated_by`` are ``text`` (ADR-0003
prefixed ULIDs) and are **values, not references** — no foreign key leaves
``ledger``, and neither of these has an intra-schema target anyway. ``updated_at``
is ``timestamptz`` (A-003). ``retention_window`` is a native ``interval``, which
is what makes the positivity CHECK expressible at all and what lets the reader
hand a ``timedelta`` straight back to Python.
"""

from collections.abc import Sequence

# `alembic/ddl.py`, imported by bare name rather than as `alembic.ddl` — that
# dotted name resolves to the installed Alembic package's own dialect-DDL
# submodule. `alembic.ini`'s prepend_sys_path puts this directory on the path.
from ddl import assume_migrate_role, enable_tenant_rls, grant_table, reset_role

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CREATE_WORKSPACE_RETENTION = """
CREATE TABLE ledger.workspace_retention (
    -- The whole key. One window per workspace, so the drain's per-group read
    -- (D-11) is a primary-key lookup returning at most one row rather than a
    -- scan it has to hope the planner indexes.
    --
    -- A value, not a reference: the `access` schema does not exist until phase 7
    -- and call-ledger may not reference it even then. It is also what ADR-0045's
    -- coverage walk looks for, so the column name is load-bearing twice over.
    workspace_id      text         NOT NULL,

    -- A native interval rather than an integer number of days. Two reasons: the
    -- positivity rule below is then a plain comparison the engine understands,
    -- and asyncpg hands the value back as a `timedelta`, so the reader does no
    -- unit arithmetic that could disagree with `writer.DEFAULT_RETENTION_WINDOW`.
    retention_window  interval     NOT NULL,

    -- On the row, for exactly the reason `spend_ceiling.updated_by` is on its
    -- row: a retention window is not a state change on a prompt property, so
    -- A-014 does not reach it, and recording it in property-history would mean
    -- inventing a forbidden edge (A-102).
    updated_by        text         NOT NULL,

    -- Genuinely "when the database saw this", so it does default — the same
    -- split `call_record` draws between `created_at` (the caller's, no default)
    -- and `written_at` (the database's, defaulted).
    updated_at        timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_workspace_retention PRIMARY KEY (workspace_id),

    -- T-02-11. A zero or negative window makes every body written after it
    -- expire at or before the instant it was written, which is a data-destroying
    -- setting reachable from `PUT /api/v1/workspaces/{id}/retention`. Refused at
    -- the engine so `set_retention_window` can surface the refusal rather than
    -- clamp a value the caller asked for into one they did not.
    CONSTRAINT ck_workspace_retention_window_is_positive
        CHECK (retention_window > interval '0')
);
"""


def upgrade() -> None:
    """Create ``ledger.workspace_retention`` with its whole guarantee stack."""
    assume_migrate_role()

    op.execute(CREATE_WORKSPACE_RETENTION)

    # T-02-09. In the same revision that creates the table, never a later one:
    # the window between the two would be a table `prope_app` can read across
    # tenants, and ADR-0045's walk is what makes forgetting this a red test.
    enable_tenant_rls("ledger", "workspace_retention")

    # UPDATE because a PUT that sets a window is an upsert — the same reasoning
    # `spend_ceiling` carries for "set or clear a ceiling". No DELETE: clearing a
    # window is not a thing the API offers, and its meaning would be "revert to
    # the 30-day default", which a caller expresses by setting 30 days.
    #
    # `report_select` takes its default of True, which resolves the discretion
    # item Phase 1 carried forward on this table's read grants. A retention
    # window is a policy setting rather than a body, and ADR-0037 already records
    # `prope_report` as a full-read credential; withholding SELECT here would
    # make the reporting role unable to explain why a body is still present.
    grant_table(
        "ledger",
        "workspace_retention",
        app_privileges=["SELECT", "INSERT", "UPDATE"],
    )

    reset_role()


def downgrade() -> None:
    """Drop the table. Its policy and grants go with it.

    Note what this does not undo, per D-10: every ``expires_at`` already stamped
    from a window this table held stays exactly as it is, because it was never a
    reference to a row here in the first place.
    """
    assume_migrate_role()
    op.execute("DROP TABLE IF EXISTS ledger.workspace_retention")
    reset_role()
