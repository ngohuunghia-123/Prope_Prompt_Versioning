"""`probe.start` — the twenty-seventh action, and the one that was NOT reused

Revision ID: 0031
Revises: 0030
Create Date: 2026-08-20

**`run.start` describes a probe accurately, and that is why reusing it is the
trap.** *May spend workspace money dispatching against a revision* is exactly
what a probe does and exactly what `run.start` already names. Reusing it would
cost no vocabulary at all, no CHECK change, no seed decision, no migration.

It is refused because A-115's set is not a naming convention — it is mapped to
roles by ``access.role_permission`` rows. Reuse means **every role already
holding `run.start` gains probe capability on the deploy that ships this, with
nobody deciding**. A minted action starts ungranted, and somebody has to write
the row that grants it. That the list must be edited to grow is the feature
(``actions.py``), and it is why the same strings are also a database ``CHECK``.

**Seeded to Admin and Owner, and not to Reviewer.** A probe spends the
workspace's provider credit against a candidate revision, which is the same act
`run.start` is separated from `run.read` for. An Owner authors the prompt and
already carries `run.start`, so this is not a new class of spend for them. A
Reviewer reads a card somebody else produced; a Reviewer who could start probes
could bill the workspace by refreshing a screen. Which role SHOULD hold it is
OQ-006's, like every other row in this table — what this buys is that the answer
is a row rather than a code change.

**No history action is added.** ADR-0067 records a dismissal in
``readiness.dismissal`` on prompt-observation's A-102 precedent — a dismissed
finding is not a state change on a prompt property — so
``ck_history_action_registry_writing_module_values`` never has to learn a tenth
writing module. The one profile event this feature does need,
``usage_profile_changed``, is written by **prompt-registry** against registry's
own column, and prompt-registry is already a permitted writer. That row is
seeded here because it belongs to the same vocabulary widening and splitting it
across two revisions would leave a deploy window where the column exists and the
event that explains a change to it does not.
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, reset_role

from alembic import op

revision: str = "0031"
down_revision: str | Sequence[str] | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: Twenty-seven. Byte-identical to ``prope.access_control.actions.Action``, which
#: is the contract ``tests/contract/test_route_actions_map_onto_the_vocabulary.py``
#: and the seed both read.
WIDEN_ACTION_VOCABULARY = """
ALTER TABLE access.role_permission
    DROP CONSTRAINT ck_role_permission_action_values,
    ADD CONSTRAINT ck_role_permission_action_values CHECK (action IN (
        'prompt.read', 'prompt.create', 'prompt.edit', 'prompt.retire',
        'prompt.transfer_owner', 'prompt.grant', 'revision.create',
        'suite.read', 'suite.edit', 'run.start', 'run.read',
        'revision.submit', 'revision.approve',
        'release.create', 'release.break_glass', 'release.withdraw',
        'provider.configure', 'provider.rotate_credential', 'provider.disable',
        'catalogue.read',
        'workspace.manage_members', 'workspace.manage_keys',
        'price.manage', 'spend_ceiling.manage',
        'user.tombstone',
        'namespace.grant',
        'probe.start'
    ));
"""

#: A TUPLE for revision 0026's reason: asyncpg prepares every statement it is
#: given and a prepared statement holds exactly one command, so `op.execute` with
#: two raises `cannot insert multiple commands into a prepared statement`.
#:
#: The DELETE must run FIRST — narrowing the CHECK while a seeded `probe.start`
#: row exists fails the constraint.
NARROW_ACTION_VOCABULARY = (
    "DELETE FROM access.role_permission WHERE action = 'probe.start'",
    """
ALTER TABLE access.role_permission
    DROP CONSTRAINT ck_role_permission_action_values,
    ADD CONSTRAINT ck_role_permission_action_values CHECK (action IN (
        'prompt.read', 'prompt.create', 'prompt.edit', 'prompt.retire',
        'prompt.transfer_owner', 'prompt.grant', 'revision.create',
        'suite.read', 'suite.edit', 'run.start', 'run.read',
        'revision.submit', 'revision.approve',
        'release.create', 'release.break_glass', 'release.withdraw',
        'provider.configure', 'provider.rotate_credential', 'provider.disable',
        'catalogue.read',
        'workspace.manage_members', 'workspace.manage_keys',
        'price.manage', 'spend_ceiling.manage',
        'user.tombstone',
        'namespace.grant'
    ))
""",
)

SEED_PROBE_START_ACTION = """
INSERT INTO access.role_permission (role, action)
VALUES ('Admin', 'probe.start'), ('Owner', 'probe.start');
"""

#: prompt-registry's, not this module's. ``target_type`` is ``property`` because
#: the profile is a field on the prompt property, and the pairing is closed by
#: ``fk_history_event_action`` — a mismatch is a poisoned transaction rather than
#: a named refusal.
#:
#: ``detail_keys`` names the four axes so a reader can see WHICH axis moved.
#: A-124's allow-list refuses an unregistered key, so an event carrying anything
#: else is rejected by ``append`` rather than stored and puzzled over later. No
#: reason is required: changing a declaration is an ordinary edit, and demanding
#: a sentence for it is how a field stops being kept current.
SEED_PROFILE_HISTORY_ACTION = """
INSERT INTO history.history_action_registry
    (action, target_type, detail_keys, requires_reason, writing_module)
VALUES (
    'usage_profile_changed',
    'property',
    ARRAY['audience', 'untrusted_input', 'acts', 'sensitivity'],
    false,
    'prompt-registry'
);
"""


def upgrade() -> None:
    assume_migrate_role()
    op.execute(WIDEN_ACTION_VOCABULARY)
    op.execute(SEED_PROBE_START_ACTION)
    op.execute(SEED_PROFILE_HISTORY_ACTION)
    reset_role()


def downgrade() -> None:
    """Narrows the vocabulary back to twenty-six and drops the history action.

    The history event rows themselves are NOT deleted, and cannot be: the
    application holds no DELETE on ``history_event`` at the privilege level
    (ADR-0025), which is the whole of the append-only guarantee. So this
    downgrade will FAIL where any ``usage_profile_changed`` event has been
    written, and that failure is correct — reverting a feature must not quietly
    take rows out of the accountability record. The remedy is to leave the
    registry row in place, not to grant a DELETE.
    """
    assume_migrate_role()
    op.execute("DELETE FROM history.history_action_registry WHERE action = 'usage_profile_changed'")
    for statement in NARROW_ACTION_VOCABULARY:
        op.execute(statement)
    reset_role()
