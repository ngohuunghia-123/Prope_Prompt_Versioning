"""The Usage Profile — four declared axes on the property, stamped onto the revision

Revision ID: 0030
Revises: 0042
Create Date: 2026-08-20

**This is the column that makes `prompt-readiness` not a lint.** ADR-0067's
argument in one line: every competitor lints context-free, and a context-free
lint is right often enough to be installed and wrong often enough to be ignored.
It tells a prompt that runs on synthetic fixtures behind an internal dashboard
that it lacks a guardrail against public misuse, the person dismisses it, and
the next finding — the one that mattered — is dismissed with the same reflex.

**`undeclared` is a real value and not a NULL.** The two are not the same
statement. A NULL says *nobody has written anything here*, which is also what a
column added by a migration says about every row that predates it, and there
would be no way to tell "this predates the feature" from "this person looked and
declined to answer". The sentinel is what lets the card render an *undeclared —
assuming worst case* badge honestly, and it is what makes the resolution to the
conservative default (`public / third_party / irreversible / personal_data`) a
decision in one readable place rather than a `COALESCE` scattered across every
query that touches the profile.

**Eight columns, not four, and the duplication is the point (D-02).** A profile
that lived only on the mutable property would silently re-scope every past
finding and every past approval the moment somebody flipped `internal` to
`public`. A profile that lived only on the revision would make *"we launched
publicly"* require a new revision with an unchanged body. Both, so a reviewer
approves a body AND the exposure it was judged under, and the drift between the
two becomes DETECTABLE rather than silent — which is the fact
`prompt-improvement` will later raise `PROFILE_DRIFT` on.

Stamping is ADR-0019's pattern, unchanged: a figure keeps the row that explains
it. The cost stored on a call record keeps its `price_row_id` for exactly this
reason.

**prompt-registry writes both, and prompt-readiness writes neither.** Every lock
in this repo carries ``writes_tables_it_does_not_own: none``. The property copy
moves through the existing ``PATCH /api/v1/prompts/{prompt_id}`` under
``prompt.edit``; the revision copy is stamped by ``INSERT_REVISION`` itself, with
a ``SELECT`` from the property in the same statement. So D-02 costs no new edge
in either direction — registry writing registry's own columns.

**Stamped at create and NOT re-stamped at submit**, which is a correction to the
plan this migration was written from. Revision 0008 grants ``prope_app``
``UPDATE (status)`` on ``registry.revision`` and nothing else: the revision is
immutable at the PRIVILEGE level rather than by convention. Re-stamping at submit
would need a column-level grant on the four columns below, weakening the
guarantee A-002 rests on, to buy a property that ``readiness.report.profile_snapshot``
already provides — written once when the revision leaves ``Draft``, never
updated, and read by the reviewer as *the exposure this was judged under*.

**Never inferred (A-163).** No trigger derives these, no backfill guesses them,
and no model may write them. A model guessing that a prompt is customer-facing
and then lecturing about it is precisely the false positive the module exists to
avoid; inference here would be the bug and not the feature.
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, reset_role

from alembic import op

revision: str = "0030"
down_revision: str | Sequence[str] | None = "0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: The four axes, each lifted from the course material rather than invented, and
#: each carrying `undeclared` as its first member. Written once and applied to
#: both tables, because two hand-maintained copies of an enum is how the property
#: and its stamped snapshot come to disagree about what a legal value is.
AXES: tuple[tuple[str, tuple[str, ...]], ...] = (
    # deck 5 slide 11, slide 54 — who can reach this prompt at all.
    ("audience", ("undeclared", "internal", "authenticated_user", "public")),
    # deck 5 slide 22, slide 25 — what untrusted content reaches the context.
    ("untrusted_input", ("undeclared", "none", "user_text", "retrieved", "third_party")),
    # deck 5 slide 11, slide 54 — what the output can cause to happen.
    ("acts", ("undeclared", "answers_only", "emits_tool_calls", "irreversible")),
    # deck 6 slide 86 — what class of data is in play.
    ("sensitivity", ("undeclared", "synthetic", "business", "personal_data")),
)


def _add_axis_columns(table: str) -> None:
    """Add the four axes to one registry table, with their CHECKs.

    ``NOT NULL DEFAULT 'undeclared'`` rather than nullable: see the module
    docstring. The default is the sentinel and **not** the conservative worst
    case — resolving `undeclared` to `public / third_party / irreversible /
    personal_data` is the application's job, done in one place, where the badge
    that says so is rendered from the same branch.
    """
    for column, values in AXES:
        rendered = ", ".join(f"'{value}'" for value in values)
        op.execute(f"ALTER TABLE registry.{table} ADD COLUMN {column} text NOT NULL DEFAULT 'undeclared'")
        op.execute(
            f"ALTER TABLE registry.{table} ADD CONSTRAINT ck_{table}_{column}_values CHECK ({column} IN ({rendered}))"
        )


def upgrade() -> None:
    assume_migrate_role()

    # `prompt_property` is the editable one. `revision` is the stamped snapshot,
    # and it is immutable for the same reason the rest of the row is: A-021
    # makes a released revision's identity permanent, and an exposure declaration
    # a reviewer approved under is part of what they approved.
    _add_axis_columns("prompt_property")
    _add_axis_columns("revision")

    # A partial index over the property, serving the one cross-prompt question
    # the card's aggregate view asks at import time: which of these nine prompts
    # has nobody declared? Partial because the answer stops being interesting the
    # moment a workspace has declared most of its prompts, and an index over a
    # column that is 95% one value is an index the planner declines anyway.
    op.execute(
        "CREATE INDEX ix_prompt_property_workspace_id_undeclared "
        "ON registry.prompt_property (workspace_id) "
        "WHERE audience = 'undeclared'"
    )

    reset_role()


def downgrade() -> None:
    """Drops all eight columns.

    Safe to reverse and genuinely lossy: the declarations are gone. That is the
    honest outcome of removing the feature, and it is not the ``call_record``
    case — no accountability record depends on these, and every approval,
    release and history event survives untouched. A frozen readiness report keeps
    its own ``profile_snapshot``, which is exactly why that column exists in
    revision 0029 rather than being read back from here.
    """
    assume_migrate_role()
    op.execute("DROP INDEX IF EXISTS registry.ix_prompt_property_workspace_id_undeclared")
    for table in ("revision", "prompt_property"):
        for column, _values in AXES:
            op.execute(f"ALTER TABLE registry.{table} DROP COLUMN IF EXISTS {column}")
    reset_role()
