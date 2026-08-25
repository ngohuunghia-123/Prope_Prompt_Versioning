"""Revision 0005's four guarantees that are neither privileges nor generic invariants.

The failure mode this file is shaped against **looks healthy**. A migration that
creates the two tables and silently seeds nothing — or seeds into a table nobody
outside a tenant can read — produces a green schema-coverage walk and an empty
vocabulary, and the first symptom arrives in Phase 5 as an AC-6 comparison
between two empty sets. So the seed is read back, positively, on the session
that will actually read it in production.

Every read here goes through ``migrate_engine`` **except** the first test, which
must use ``app_sessionmaker``: the property under test is what the *application*
role sees with no tenant set. That inverts the file's own rule on purpose.
"""

from sqlalchemy import text

from tests.property_history import (
    COUNT_HISTORY_EVENTS,
    COUNT_REGISTRY_ROWS,
    REGISTRY_ACTION_COUNT,
    seed_history_event,
)

READ_REGISTRY = text(
    "SELECT action, target_type, detail_keys, requires_reason, writing_module "
    "FROM history.history_action_registry"
)

LIST_HISTORY_INDEXES = text(
    "SELECT indexname FROM pg_indexes "
    "WHERE schemaname = 'history' AND tablename = 'history_event' ORDER BY indexname"
)

#: ``pg_get_serial_sequence`` works for identity columns — "if the column is an
#: identity column, the associated sequence is the sequence internally created
#: for that column" — which is what makes this assertion writable without
#: knowing the generated sequence's name.
READ_SEQ_CACHE = text(
    "SELECT seqcache FROM pg_sequence "
    "WHERE seqrelid = pg_get_serial_sequence('history.history_event', 'seq')::regclass"
)

REQUIRES_REASON = {
    "revision_break_glass_released",
    "release_withdrawn",
    "revision_changes_requested",
    # Revision 0034, ADR-0068. Accepting a proposal needs no explanation — the
    # revision it produced is the explanation — while dismissing one is the
    # judgement call somebody may have to defend later, so the database asks for
    # the reason rather than the screen doing it.
    "improvement_proposal_dismissed",
}

#: Two at revision 0005, five after revision 0006's amendment (D-62), six after
#: revision 0022 (ADR-0057).
#:
#: AC-12 requires the grant events to carry *"actor, grantee, level, and
#: timestamp"*; three of those are envelope columns and the other two had nowhere
#: to go, because 0005 derived every payload from a lock-file ``outputs`` block
#: that names event names and says nothing about detail keys. ``role_revoked``
#: was asymmetric with ``role_assigned`` for the same reason — the trail recorded
#: that a role was taken away and not which one, from whom. The amendment is a
#: declared deviation carried as ``OQ-132``; no spec file was edited.
DECLARED_DETAIL_KEYS = {
    "revision_released": {"version_id", "previous_version_id", "break_glass"},
    "role_assigned": {"role", "grantee_user_id"},
    "role_revoked": {"role", "grantee_user_id"},
    "access_granted": {"grantee_user_id", "level"},
    "access_revoked": {"grantee_user_id", "level"},
    # ADR-0057. The actor is the joiner, so the invitation is the only thing the
    # row cannot otherwise name — an administrator reading the queue needs to see
    # which code let this person in.
    "member_join_requested": {"invite_id"},
    # ADR-0061. The same pair `access_granted` carries, and deliberately the same
    # pair: a namespace grant and a prompt grant are the same act at two scopes,
    # so an administrator reading the log reads one shape rather than two. What
    # tells them apart is `target_type`, which is `namespace_grant` here and is
    # in `NEVER_PROMPT_SCOPED_TARGET_TYPES` — a namespace is not a prompt, so the
    # row cannot carry a `scope_prompt_id`.
    "namespace_access_granted": {"grantee_user_id", "level"},
    "namespace_access_revoked": {"grantee_user_id", "level"},
    # ADR-0067. The four Usage Profile axes, and nothing else — no body, no
    # finding, no rule id. The event says somebody changed what this prompt is
    # FOR, which is a state change on a prompt property and therefore history's;
    # what a readiness card then said about it is not, and lives in
    # `readiness.report` where a reviewer's copy is frozen (A-102's line).
    "usage_profile_changed": {"audience", "untrusted_input", "acts", "sensitivity"},
    # ADR-0068. Which proposal, which detector raised it, which remedy family it
    # belonged to — and NOT the candidate body. That absence is the control: this
    # table is append-only at the privilege level (ADR-0025), so a body written
    # here could never be taken back out, and A-124's allow-list is what refuses
    # it rather than a rule somebody follows.
    "improvement_proposal_accepted": {"proposal_id", "detector_id", "remedy_family"},
    "improvement_proposal_dismissed": {"proposal_id", "detector_id", "remedy_family"},
    "improvement_proposal_expired": {"proposal_id", "detector_id", "remedy_family"},
    # Revision 0045. A prompt's `namespace/name` IS its model name, so a move is
    # a breaking change for every caller pointing at the old one; `from` and `to`
    # are what let somebody reading the log answer "when did this stop
    # resolving". No title, no body — the identity only.
    "model_name_changed": {"from", "to"},
}

DECLARED_INDEXES = (
    "ix_history_event_workspace_id_action_seq",
    "ix_history_event_workspace_id_actor_id_seq",
    "ix_history_event_workspace_id_scope_prompt_id_seq",
    "ix_history_event_workspace_id_target_type_target_id_seq",
    "pk_history_event",
    "uq_history_event_seq",
)


async def test_the_registry_is_readable_with_no_tenant_context_and_holds_every_action(
    app_sessionmaker, migrate_engine
):
    """D-56, asserted positively rather than merely declared.

    One assertion proves four things at once: the table is genuinely global, the
    seed landed, ``prope_app`` holds ``SELECT`` on it, and this is exactly the
    read ADR-0038's process-start cache performs — so it fails for the real
    reason if the exemption is ever reversed.

    **Any test of the vocabulary that opens ``workspace_transaction`` is a
    warning sign.** If the registry is correct it does not need one; if it needs
    one the registry is wrong. The companion count on ``history_event`` is the
    positive control's mirror: it proves the session really has no tenant
    context, so the seeded rows came from the exemption and not from a leaky policy.

    **37 until migration 0026**, which seeded `namespace_access_granted` and
    `namespace_access_revoked` (ADR-0061); 40 at 0028
    (`observability_content_viewed`); 41 at 0031 (`usage_profile_changed`); 44
    at 0034 (the three `improvement_proposal_*`); 45 at 0045
    (`model_name_changed`). The number is pinned rather than derived on purpose:
    a vocabulary that grows without anybody noticing is the failure this count
    exists to catch, so adding an action is meant to cost one line here.

    It cost more than one line this time, because the count was in the test's
    NAME as well as its body and the name is not what fails. The number stays
    pinned in the assertion, where being wrong is loud; it is out of the name,
    where it only ever generated renames.
    """
    # The control needs a row to hide, or the zero below is true against an empty
    # table and distinguishes no hypothesis from any other.
    await seed_history_event(migrate_engine)

    async with app_sessionmaker() as session:
        assert (await session.execute(COUNT_REGISTRY_ROWS)).scalar_one() == REGISTRY_ACTION_COUNT
        assert (await session.execute(COUNT_HISTORY_EVENTS)).scalar_one() == 0

    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_HISTORY_EVENTS)).scalar_one() == 1


async def test_the_registry_carries_the_declared_reasons_and_detail_key_sets(
    migrate_engine,
):
    """The part of the seed fully determined by the specs, so it is asserted.

    ``requires_reason`` is stated identically in this lock file, in
    ``release-control.lock.yml`` and in INT-006. The action *names* are Phase
    5's AC-6 and are deliberately not asserted here.
    """
    async with migrate_engine.begin() as connection:
        rows = (await connection.execute(READ_REGISTRY)).all()

    assert {action for action, _, _, requires, _ in rows if requires} == REQUIRES_REASON

    keys = {action: set(detail_keys) for action, _, detail_keys, _, _ in rows}
    assert {action: value for action, value in keys.items() if value} == DECLARED_DETAIL_KEYS


async def test_the_four_declared_indexes_exist_by_name(migrate_engine):
    """D-55 fixed the number at four for four declared read shapes, plus the two
    constraint-backed indexes. The count is pinned rather than derived because a
    GIN index on ``details`` is the fifth somebody will reach for."""
    async with migrate_engine.begin() as connection:
        indexes = (await connection.execute(LIST_HISTORY_INDEXES)).scalars().all()

    assert tuple(indexes) == DECLARED_INDEXES


async def test_the_identity_sequence_has_no_cache(migrate_engine):
    """With a cache above one "the values might be generated out of sequence
    when all the sessions are considered" — the one setting that destroys
    ``seq``'s only property, and one ``ALTER SEQUENCE`` away from being wrong
    with nothing else noticing."""
    async with migrate_engine.begin() as connection:
        assert (await connection.execute(READ_SEQ_CACHE)).scalar_one() == 1
