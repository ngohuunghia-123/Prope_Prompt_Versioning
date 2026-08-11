"""PH-03 / ROADMAP SC1: a prompt's whole lifecycle, back in one ``read()`` call.

**The tenth event (D-76, OQ-033).** AC-3 enumerates the lifecycle as *"created,
revised twice, submitted, approved, released, its suite edited, access granted,
restored"* and then claims all TEN are returned. Counting the verbs gives nine.
The reading adopted here — recorded in ``OQ-033``, not invented by this file —
is that registering a property mints its first revision, so registration writes
TWO events: ``property_created`` for the property and ``revision_created`` for
revision 1. That closes the count at ten and makes ``revision_created`` a
three-event action in this lifecycle rather than two. If a human rules the
other way, ``OQ-033`` names the one line that changes.

**"Submission order" (ROADMAP SC1) and "seq DESC" (ROADMAP SC3) are the same
requirement.** The order key is ``seq``, descending (INT-007), and the returned
sequence is asserted as the EXACT REVERSE of the write order — which holds
under either phrasing and is what an Activity screen renders newest-first.

**Every event goes through ``append()``, never raw SQL.** prompt-registry and
release-control do not exist yet (Phase 13, Phase 22); what this test can
honestly prove is that their VOCABULARY and their SCOPE STAMPING land four
modules' events in one prompt's trail — the actual content of A-119's claim.
Seeding rows directly would prove the statement, not the seam.
"""

from sqlalchemy import text

from prope.db.session import workspace_transaction
from prope.property_history.append import append
from prope.property_history.domain import ActorType, HistoryEventDraft, PromptScope
from prope.property_history.read import READ_BY_PROMPT, read
from tests.property_history import ACTOR_ID, WORKSPACE_A, WORKSPACE_B, counting_statements, day

PROMPT_ID = "prm_01J0000000000000000000010"
OTHER_PROMPT_ID = "prm_01J0000000000000000000011"

REVISION_1 = "rev_01J0000000000000000000010"
REVISION_2 = "rev_01J0000000000000000000011"
REVISION_3 = "rev_01J0000000000000000000012"

SUITE_ID = "sui_01J0000000000000000000010"
GRANT_ID = "grt_01J0000000000000000000010"

COUNT_BY_ID = text("SELECT count(*) FROM history.history_event WHERE id = :id")

#: The lifecycle, D-76's reading, one row per append(). Each comment names the
#: writing module the row stands in for — none of the five modules exist yet.
LIFECYCLE = (
    ("property_created", "property", PROMPT_ID),        # prompt-registry
    ("revision_created", "revision", REVISION_1),        # prompt-registry — the tenth event, D-76
    ("revision_created", "revision", REVISION_2),        # prompt-registry — "revised twice"
    ("revision_created", "revision", REVISION_3),        # prompt-registry — "revised twice"
    ("revision_submitted", "revision", REVISION_3),      # release-control
    ("revision_approved", "revision", REVISION_3),       # release-control
    ("revision_released", "revision", REVISION_3),       # release-control — carries A-124's allow-list
    ("eval_suite_updated", "eval_suite", SUITE_ID),       # evaluation
    ("access_granted", "prompt_grant", GRANT_ID),         # access-control
    ("revision_restored", "revision", REVISION_2),        # release-control
)
LIFECYCLE_ACTIONS = [action for action, _, _ in LIFECYCLE]

#: revision_released's three registered detail_keys (0005's seed), asserted in
#: the direction that must PASS — Phase 4 asserts only the refusing direction.
RELEASE_DETAILS = {
    "version_id": "ver_01J0000000000000000000001",
    "previous_version_id": "ver_01J0000000000000000000000",
    "break_glass": False,
}


def _draft(action: str, target_type: str, target_id: str, **overrides) -> HistoryEventDraft:
    values = {
        "workspace_id": WORKSPACE_A,
        "actor_type": ActorType.USER,
        "actor_id": ACTOR_ID,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "occurred_at": day(5),
        "scope_prompt_id": PROMPT_ID,
        "details": RELEASE_DETAILS if action == "revision_released" else {},
    }
    values.update(overrides)
    return HistoryEventDraft(**values)


async def test_a_prompts_whole_lifecycle_comes_back_from_one_read(
    app_sessionmaker, app_engine, migrate_engine
):
    # None of the ten actions requires a reason (0005's seed); absence is not
    # an oversight.
    appended_ids: list[str] = []
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        for action, target_type, target_id in LIFECYCLE:
            appended_ids.append(await append(session, _draft(action, target_type, target_id)))

    # Four decoys, none of which may leak into PROMPT_ID's Activity.
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        # Present ⇒ the scope predicate is not filtering by prompt.
        decoy_other_prompt = await append(
            session,
            _draft(
                "property_created",
                "property",
                OTHER_PROMPT_ID,
                scope_prompt_id=OTHER_PROMPT_ID,
            ),
        )
        # Present ⇒ null scopes are being matched.
        decoy_no_prompt = await append(
            session,
            _draft("workspace_created", "workspace", WORKSPACE_A, scope_prompt_id=None),
        )
        # Present ⇒ the read is matching on target_id rather than scope_prompt_id
        # — this is D-77's silent-failure decoy: a revision_created about this
        # very prompt's own revision, with no scope stamped. Phase 6's
        # prope_property_history_null_scope_prompt_total is the metric that
        # would catch the real-world version of this row.
        decoy_null_scope = await append(
            session,
            _draft("revision_created", "revision", REVISION_2, scope_prompt_id=None),
        )

    # Its own tenant transaction: proves prope_app CAN write this row for
    # WORKSPACE_B, so the decoy is one the application could really produce.
    # Present ⇒ the workspace predicate is not filtering, or RLS is not applied.
    async with workspace_transaction(app_sessionmaker, WORKSPACE_B) as session:
        decoy_other_workspace = await append(
            session,
            _draft(
                "property_created",
                "property",
                PROMPT_ID,
                workspace_id=WORKSPACE_B,
                scope_prompt_id=PROMPT_ID,
            ),
        )

    decoy_ids = {decoy_other_prompt, decoy_no_prompt, decoy_null_scope, decoy_other_workspace}

    # Vacuity guard: every decoy is really in the table before it is asserted
    # absent from the read — a filter that dropped everything would look green
    # without this.
    async with migrate_engine.begin() as control:
        for decoy_id in decoy_ids:
            landed = (await control.execute(COUNT_BY_ID, {"id": decoy_id})).scalar_one()
            assert landed == 1, f"decoy {decoy_id} was never written; the test proves nothing"

    # counting_statements starts AFTER workspace_transaction's own
    # set_config — that call is the tenant context, not the read.
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        with counting_statements(app_engine) as statements:
            events = await read(session, PromptScope(WORKSPACE_A, PROMPT_ID))

    assert len(events) == 10, f"expected 10 events, got {[e.action for e in events]}"
    assert [event.action for event in events] == list(reversed(LIFECYCLE_ACTIONS))
    assert [event.id for event in events] == list(reversed(appended_ids))
    assert {event.target_type for event in events} == {
        "property",
        "revision",
        "eval_suite",
        "prompt_grant",
    }
    seqs = [event.seq for event in events]
    assert seqs == sorted(seqs, reverse=True) and len(set(seqs)) == len(seqs)

    returned_ids = {event.id for event in events}
    for decoy_id in decoy_ids:
        assert decoy_id not in returned_ids

    released = next(e for e in events if e.action == "revision_released")
    assert dict(released.details) == RELEASE_DETAILS

    assert len(statements) == 1
    assert "JOIN" not in READ_BY_PROMPT.text.upper()
    assert READ_BY_PROMPT.text.count("history.history_event") == 1

    # Vacuity guard: the read is a filter, not a fixed answer — the decoy
    # prompt's own scope returns exactly its one event.
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        other_events = await read(session, PromptScope(WORKSPACE_A, OTHER_PROMPT_ID))
    assert [event.id for event in other_events] == [decoy_other_prompt]
