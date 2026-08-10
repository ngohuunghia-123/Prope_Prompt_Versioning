"""The fourth reader, asserted deliberately rather than left unlooked-at.

**This test proves an exposure, on purpose.** ``prope_report`` is created
``LOGIN BYPASSRLS`` (``alembic/versions/0001_roles_and_schemas.py:47``) and
``grant_table``'s ``report_select`` default gave it ``SELECT`` on
``ledger.call_body`` in the revision that created the table
(``alembic/ddl.py:103, 122-123``; ``alembic/versions/0003_ledger_tables.py:252``).
So **one statement on that credential reads every stored body in every
workspace**, with the tenant policy bypassed by role attribute rather than
evaded. ``tests/conftest.py`` has built that engine as a session fixture since
Phase 1; this is its first consumer.

**None of CL-10's three layers can see it.**
``tests/security/test_no_body_read_path.py`` asserts the assembled route table,
the module's internal Python surface, and the statements in ``src/`` that name
the table. All three are about *this application*. A database role is outside
every one of them.

**It is not obviously a defect.** ADR-0037 records ``prope_report`` as a
deliberate full-read reporting credential and ADR-0036's restore rehearsal
depends on it existing, and AC-10's text — *"route, parameter, or function"* —
does not reach a database role. **It is not obviously fine either.** The lock
file's first ``security_requirements`` clause is *"Bodies have no read path in
the MVP — no endpoint, **no export**, no admin viewer, and no join from another
module's query"*, and T-005's own reasoning is that *"a body's lifecycle is a
property of every place it can rest, not of the table it is meant to live in"* —
which is the argument ADR-0039 already used to exclude ``call_body`` from the
nightly dump. This is that argument one layer down.

**Phase 3 leaves the grant and records the exception** (plan 03-05, Task 3,
adopted ``assert-and-record``, status UNCONFIRMED). Three reasons, in order of
weight. ROADMAP SC4 is about routes, parameters and functions, and a database
role is none of the three, so the phase closes what it was given and hands the
excess upstream (ORCHESTRATION §5). ``grant_table``'s ``report_select`` defaults
to ``True`` for **every** table in the system, so revoking it here would fix one
table and leave the pattern that produced it in place — the decision that matters
is what that default should be for a table declared to have no reader, and no
phase should take that on evidence it turned up while writing a test. And
leaving it costs one migration later, while revoking it now against an unbuilt
restore rehearsal and an ADR that records the opposite costs a claim every later
module reads.

The third option — do nothing and mention it nowhere — is refused outright. A
year from now, *"we looked and decided not to"* and *"nobody looked"* must not be
the same artifact. The question lives in
``docs/brainstorm/open_questions/OQ-025.md``, clause 2.

**If this test starts failing, somebody revoked the grant.** Go and read
``OQ-025``'s answer before deciding whether the failure is the fix or the
regression — and if it is the fix, delete this file in the same change that adds
the ``REVOKE``, rather than leaving a test that documents a state the database
has left.

This test is also where the carried-forward ``prope_report`` discretion item from
Phases 1 and 2 lands. As phrased since Phase 1 it asks *"what grants does
``prope_report`` get on the new table"*, and this phase creates no table, so as
phrased it is vacuous. The live question was always this one.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from prope.call_ledger.domain import CallBodyDraft
from prope.call_ledger.writer import write_records
from prope.db.session import workspace_transaction
from tests.unit import WORKSPACE_A, WORKSPACE_B, gateway_draft

CALL_IN_A = "cal_01J0000000000000000RPTAAA"
CALL_IN_B = "cal_01J0000000000000000RPTBBB"

#: Distinguishable per workspace, so a cross-tenant read is visible as *which*
#: tenant's text came back rather than as a row count.
BODY_IN_A = "the request workspace A sent"
BODY_IN_B = "the request workspace B sent"

COUNT_BODIES = text("SELECT count(*) FROM ledger.call_body")
READ_ALL_BODIES = text(
    "SELECT workspace_id, request_body FROM ledger.call_body ORDER BY workspace_id"
)
READ_TENANT_GUC = text("SELECT current_setting('app.workspace_id', true)")

REPORT_BYPASSES_RLS = text("SELECT rolbypassrls FROM pg_roles WHERE rolname = 'prope_report'")
REPORT_MAY_SELECT_BODIES = text(
    "SELECT has_table_privilege('prope_report', 'ledger.call_body', 'SELECT')"
)


async def _seed_a_body(app_sessionmaker, workspace_id: str, call_id: str, body: str) -> None:
    """One gateway call with a body, written through the real write path.

    Through ``write_records`` rather than by hand: a body inserted by a test is a
    body a test decided the shape of, and the claim here is about the rows this
    system actually stores.
    """
    async with workspace_transaction(app_sessionmaker, workspace_id) as session:
        result = await write_records(
            session,
            [
                gateway_draft(
                    call_id=call_id,
                    workspace_id=workspace_id,
                    body=CallBodyDraft(
                        request_body=body, response_body="a response", byte_size=len(body)
                    ),
                )
            ],
        )
    assert result.bodies_written == 1


async def test_the_reporting_credential_reads_every_body_in_every_workspace(
    app_sessionmaker, migrate_engine: AsyncEngine, report_engine: AsyncEngine
) -> None:
    """The exposure itself: two workspaces, one statement, no tenant context.

    The positive control comes first and is read as the owner: without it, a
    ``prope_report`` read returning two rows would be indistinguishable from a
    table that happened to hold two rows anyone could see.

    ``current_setting('app.workspace_id', true)`` is asserted to be unset on the
    reading connection, because that is what makes this a **bypass** rather than
    a read inside a tenant context that a test forgot to leave.
    """
    await _seed_a_body(app_sessionmaker, WORKSPACE_A, CALL_IN_A, BODY_IN_A)
    await _seed_a_body(app_sessionmaker, WORKSPACE_B, CALL_IN_B, BODY_IN_B)

    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_BODIES)).scalar_one() == 2

    async with report_engine.begin() as reporting:
        assert (await reporting.execute(READ_TENANT_GUC)).scalar_one() in (None, "")
        rows = (await reporting.execute(READ_ALL_BODIES)).all()

    assert [(row.workspace_id, row.request_body) for row in rows] == [
        (WORKSPACE_A, BODY_IN_A),
        (WORKSPACE_B, BODY_IN_B),
    ], (
        "the reporting credential no longer reads both workspaces' bodies. Somebody revoked "
        "SELECT on ledger.call_body from prope_report, or removed BYPASSRLS. Read OQ-025 "
        "clause 2 before deciding whether that is the fix or the regression."
    )


async def test_the_runtime_credential_sees_only_its_own_tenant(
    app_sessionmaker, migrate_engine: AsyncEngine
) -> None:
    """The negative control, and the reason the test above is about a role.

    ``prope_app`` holds the same ``SELECT`` on the same table and reads exactly
    one row, because the tenant policy applies to it. That is the difference
    ``BYPASSRLS`` makes, observed rather than read out of ``pg_roles`` — and it is
    what stops the assertion above from being *"the table is readable"*, which
    would be true of any table and would prove nothing.
    """
    await _seed_a_body(app_sessionmaker, WORKSPACE_A, CALL_IN_A, BODY_IN_A)
    await _seed_a_body(app_sessionmaker, WORKSPACE_B, CALL_IN_B, BODY_IN_B)

    async with migrate_engine.begin() as control:
        assert (await control.execute(COUNT_BODIES)).scalar_one() == 2

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        rows = (await session.execute(READ_ALL_BODIES)).all()

    assert [(row.workspace_id, row.request_body) for row in rows] == [(WORKSPACE_A, BODY_IN_A)]


async def test_the_two_facts_behind_the_exposure_are_still_true(
    migrate_engine: AsyncEngine,
) -> None:
    """The mechanism, named at the catalogue so the failure says which half moved.

    Two independent facts produce the read above, and either one alone would not:
    the role attribute that makes the tenant policy inapplicable, and the grant
    that lets the role touch the table at all. Asserting them separately means a
    future ``REVOKE SELECT`` and a future ``ALTER ROLE ... NOBYPASSRLS`` are
    distinguishable failures rather than one red test with two possible causes.
    """
    async with migrate_engine.begin() as control:
        assert (await control.execute(REPORT_BYPASSES_RLS)).scalar_one() is True, (
            "prope_report no longer carries BYPASSRLS; ADR-0037 records it as a full-read "
            "reporting credential and ADR-0036's restore rehearsal assumes it"
        )
        assert (await control.execute(REPORT_MAY_SELECT_BODIES)).scalar_one() is True, (
            "prope_report no longer holds SELECT on ledger.call_body. If that was deliberate, "
            "OQ-025 clause 2 has been answered and this file should go with the migration."
        )
