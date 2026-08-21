"""A sixth `writing_module`, and the three events ADR-0067 declined to write

Revision ID: 0034
Revises: 0033
Create Date: 2026-08-20

**Revision 0031's docstring said this constraint *"never has to learn a tenth
writing module"*, and that sentence was about readiness. It stands, and this
revision does not contradict it** — it widens the constraint for a different
module on a different fact.

The distinction is the whole reason this revision exists rather than being a
copy of a decision already taken. A readiness dismissal is **authoring-time
noise-suppression**: somebody is writing a prompt, a lint fires, and they say it
does not apply. A-102 is explicit that this is not a state change on a prompt
property — the property did not change — so it lives in `readiness.dismissal`
with its actor and its reason and nowhere else.

A **proposal disposition** is a different object. It is a person's decision about
a machine-authored change to a prompt that is **serving production traffic**, and
*who decided what the machine proposed* is exactly the accountability record
ADR-0025's append-only privilege model exists to keep. If the improvement agent
ever proposes something harmful and somebody accepts it, the question asked
afterwards is not *which lint was ignored* — it is *who said yes, and when, and
what were they shown*. That question has an answer only if this row exists.

**`gate_failed` is deliberately absent, and the draft spec is corrected here.**
A candidate that fails the eval gate never becomes a proposal — SR-3 discards it
before the insert — so there is no disposition to record. Writing a machine's
rejection of a machine's suggestion into the accountability record of a prompt
that never changed would dilute the trail with events no person took, and a
trail people learn to scroll past is a trail nobody reads. It is a counter,
`prope_improvement_gate_rejected_total`, and nothing else.

**`improvement_proposal_expired` has `actor_type = 'system'` and a NULL
`actor_id`.** It is the only event outside access-control's vocabulary with no
human actor. `ck_history_event_actor_id_present_unless_system` from revision 0005
already permits exactly this shape, so nothing in the schema moves for it — the
expiry is a fact about a deadline passing, and inventing a service account to
attribute it to would be a lie with a name.

Forty to forty-three.
"""

from collections.abc import Sequence

from ddl import assume_migrate_role, reset_role

from alembic import op

revision: str = "0034"
down_revision: str | Sequence[str] | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: Six. Byte-identical to the set `tests/contract/test_event_vocabulary_matches_the_locks.py`
#: reads out of `docs/modules/property-history.lock.yml`, which is the artifact
#: this constraint is downstream of rather than the other way round.
WIDEN_WRITING_MODULES = """
ALTER TABLE history.history_action_registry
    DROP CONSTRAINT ck_history_action_registry_writing_module_values,
    ADD CONSTRAINT ck_history_action_registry_writing_module_values CHECK (
        writing_module IN (
            'prompt-registry', 'release-control', 'evaluation',
            'provider-access', 'access-control',
            'prompt-improvement'
        )
    );
"""

#: A TUPLE for revision 0026's reason: asyncpg prepares every statement it is
#: given and a prepared statement holds exactly one command, so `op.execute`
#: with two raises `cannot insert multiple commands into a prepared statement`.
#:
#: The DELETE must run FIRST — narrowing the CHECK while the three seeded rows
#: exist fails the constraint.
NARROW_WRITING_MODULES = (
    "DELETE FROM history.history_action_registry WHERE writing_module = 'prompt-improvement'",
    """
ALTER TABLE history.history_action_registry
    DROP CONSTRAINT ck_history_action_registry_writing_module_values,
    ADD CONSTRAINT ck_history_action_registry_writing_module_values CHECK (
        writing_module IN (
            'prompt-registry', 'release-control', 'evaluation',
            'provider-access', 'access-control'
        )
    )
""",
)

#: `target_type` is `property` because the subject really is the prompt somebody
#: is deciding about, and the pairing is closed by `fk_history_event_action` — a
#: mismatch is a poisoned transaction rather than a named refusal.
#:
#: `detail_keys` names three: which proposal, which detector raised it, and which
#: remedy family it belonged to. A-124's allow-list refuses an unregistered key,
#: so an event carrying a candidate body — the one thing in this module that must
#: never reach an append-only table — is rejected by `append` rather than stored
#: and regretted. That the body is not in this list is the control.
#:
#: `requires_reason` is TRUE for the dismissal alone. The dismissal rate per
#: `detector_id` is this module's honest metric, and a rate without reasons
#: cannot tell *the detector is wrong* from *the remedy is wrong*, which are
#: opposite fixes. Accepting needs no sentence — the acceptance IS the statement,
#: and the revision it prefills carries its own change summary. Expiring needs
#: none either: nobody did it.
SEED_DISPOSITION_ACTIONS = """
INSERT INTO history.history_action_registry
    (action, target_type, detail_keys, requires_reason, writing_module)
VALUES
    ('improvement_proposal_accepted', 'property',
     ARRAY['proposal_id', 'detector_id', 'remedy_family'], false, 'prompt-improvement'),
    ('improvement_proposal_dismissed', 'property',
     ARRAY['proposal_id', 'detector_id', 'remedy_family'], true, 'prompt-improvement'),
    ('improvement_proposal_expired', 'property',
     ARRAY['proposal_id', 'detector_id', 'remedy_family'], false, 'prompt-improvement');
"""


def upgrade() -> None:
    assume_migrate_role()
    op.execute(WIDEN_WRITING_MODULES)
    op.execute(SEED_DISPOSITION_ACTIONS)
    reset_role()


def downgrade() -> None:
    """Narrows the writing modules back to five and drops the three actions.

    The history event rows themselves are NOT deleted, and cannot be: the
    application holds no DELETE on ``history_event`` at the privilege level
    (ADR-0025), which is the whole of the append-only guarantee. So this
    downgrade will FAIL where any proposal disposition has been recorded, and
    that failure is correct — reverting a feature must not quietly take rows out
    of the accountability record. The remedy is to leave the registry rows in
    place, not to grant a DELETE.
    """
    assume_migrate_role()
    for statement in NARROW_WRITING_MODULES:
        op.execute(statement)
    reset_role()
