"""history.history_action_registry gains 'api_key_scope_set' — the missing third of a trio

Revision ID: 0021
Revises: 0020
Create Date: 2026-08-16

**A key's reach can now change after it is minted, so the change needs a row.**
Until now ``access.api_key.scope_model_names`` was written once at creation and
never again — there was no route to change it — which is why the vocabulary
carried ``api_key_created`` and ``api_key_revoked`` and nothing between them.
``PUT /api/v1/workspaces/{id}/keys/{key_id}/scope`` puts something between them:
a live credential quietly reaching one more prompt than it did yesterday. That is
precisely the class of fact property-history exists to hold, and leaving it out
would make the trail claim a key's reach was fixed for its whole life when it was
not.

**0016 declined to add an action and this one adds one; the difference is the
subject.** That revision's argument was that a folder "holds no revision, cannot
be approved, cannot be released and cannot serve a call", so who made a drawer
buys no traceability. A consumer key is the opposite on every clause — it is the
thing that *serves calls*, and its scope is the list of prompts it may serve.

**The detail allow-list is empty, and that is copied from ``api_key_created``
deliberately rather than by omission.** That action's registry row is ``'{}'`` so
that there is no registered slot for the scope, the name, the ``last_four`` or any
part of the secret (AC-7, revision 0005). Recording the model names here would
reintroduce exactly the slot that row exists to withhold — and a model name is
``namespace/name``, which for a private prompt is the disclosure BR-01 closes as
not-found. The event says *this key's reach was changed, by this person, at this
instant*; **what** it was changed to is a property of the key, readable from
``GET /workspaces/{id}/keys`` by somebody holding ``workspace.manage_keys``. The
audit question the trail must answer is who moved it and when, and that is
answered without naming a prompt to a reader who may not see it.

``requires_reason`` is false, matching both its neighbours. A reason is demanded
where the act is exceptional and needs justifying at the moment it happens —
break-glass, a withdrawal, a change request. Widening a key is ordinary
administration.
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, reset_role

from alembic import op

revision: str = "0021"
down_revision: str | Sequence[str] | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: ``history_action_registry`` is written by migrations and only by migrations
#: (D-51 grants ``prope_app`` SELECT alone), which is what makes ADR-0038's
#: un-invalidated cache of it safe. So this is an INSERT in a migration rather
#: than a seed the application performs at startup.
ADD_SCOPE_SET_ACTION = """
INSERT INTO history.history_action_registry
    (action, target_type, detail_keys, requires_reason, writing_module)
VALUES
    ('api_key_scope_set', 'api_key', '{}', false, 'access-control');
"""

DROP_SCOPE_SET_ACTION = """
DELETE FROM history.history_action_registry WHERE action = 'api_key_scope_set';
"""


def upgrade() -> None:
    assume_migrate_role()
    op.execute(ADD_SCOPE_SET_ACTION)
    reset_role()


def downgrade() -> None:
    """Refuses while an event references it — ``history_event`` has no DELETE (PH-02)."""
    assume_migrate_role()
    op.execute(DROP_SCOPE_SET_ACTION)
    reset_role()
