"""T-018 — `registry.revision` holds every prompt body in Prope, and it is policied.

The table carried **no tenant column for five module passes** because it was
reachable only through ``prompt_id``, so ADR-0035's original enumeration — tables
ALREADY CARRYING ``workspace_id`` — could not see the one table holding the asset
the entire product exists to protect. ADR-0045 inverted the rule and this is the
table the inversion caught, with no new decision required.

**Tested in the direction that fails open if wrong.** Two properties, and the
second is the one that matters:

* a read with the WRONG ``app.workspace_id`` returns zero rows;
* a read with NO ``app.workspace_id`` at all returns **zero rows, not all rows**.

The second is deny-by-default. ``current_setting('app.workspace_id', true)``
answers NULL when nothing set it, the predicate is then NULL rather than true,
and the row is filtered out — so a query somebody forgot to scope answers nothing
instead of answering everything. A one-argument ``current_setting`` would have
raised instead, and a policy that raised would have been "fixed" by removing it.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from prope.db.session import workspace_transaction
from tests.prompt_registry import seed_prompt, seed_revision
from tests.unit import WORKSPACE_A, WORKSPACE_B

OTHER_PROMPT = "prm_01J00000000000000000OTHR"

OTHER_REVISION = "rev_01J00000000000000000OTHR"

COUNT_REVISIONS = text("SELECT count(*) FROM registry.revision")

COUNT_PROMPTS = text("SELECT count(*) FROM registry.prompt_property")

READ_BODIES = text("SELECT body FROM registry.revision")

MISSTAMPED_REVISION = text(
    """
    INSERT INTO registry.revision (
        version_id, workspace_id, prompt_id, revision_number, body,
        parameters, change_summary, author_id, status, created_at
    ) VALUES (
        :version_id, :workspace_id, :prompt_id, 9, 'smuggled',
        '{}'::jsonb, 'smuggled', 'usr_x', 'Draft', now()
    )
    """
)


async def _two_tenants(migrate_engine) -> None:  # noqa: ANN001
    await seed_prompt(migrate_engine, workspace_id=WORKSPACE_A)
    await seed_revision(migrate_engine, workspace_id=WORKSPACE_A, body="tenant A's prompt text")

    await seed_prompt(
        migrate_engine,
        prompt_id=OTHER_PROMPT,
        workspace_id=WORKSPACE_B,
        namespace="other",
        name="thing",
    )
    await seed_revision(
        migrate_engine,
        version_id=OTHER_REVISION,
        prompt_id=OTHER_PROMPT,
        workspace_id=WORKSPACE_B,
        body="tenant B's prompt text",
    )


async def test_each_tenant_sees_only_its_own_revisions(
    migrate_engine, app_sessionmaker
) -> None:
    """The ordinary case. Two rows exist; each transaction sees one."""
    await _two_tenants(migrate_engine)

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        assert await db.scalar(COUNT_REVISIONS) == 1
        assert (await db.execute(READ_BODIES)).scalars().all() == ["tenant A's prompt text"]

    async with workspace_transaction(app_sessionmaker, WORKSPACE_B) as db:
        assert (await db.execute(READ_BODIES)).scalars().all() == ["tenant B's prompt text"]


async def test_a_read_with_no_tenant_set_returns_zero_rows_rather_than_all_rows(
    migrate_engine, app_sessionmaker
) -> None:
    """ADR-0045's inversion, asserted in the direction that fails open if wrong.

    A plain session — no ``workspace_transaction``, so no ``SET LOCAL`` — is
    exactly the query somebody writes when they forget the seam. It must answer
    **nothing**, and the count of what exists is asserted alongside so that
    "zero" cannot pass because the fixture wrote nothing.
    """
    await _two_tenants(migrate_engine)

    async with migrate_engine.begin() as connection:
        assert await connection.scalar(COUNT_REVISIONS) == 2

    async with app_sessionmaker() as unscoped:
        assert await unscoped.scalar(COUNT_REVISIONS) == 0
        assert await unscoped.scalar(COUNT_PROMPTS) == 0


async def test_a_misstamped_insert_is_refused_by_the_policys_with_check(
    migrate_engine, app_sessionmaker
) -> None:
    """The ``WITH CHECK`` half, written out in ``ddl.enable_tenant_rls`` on purpose.

    It defaults to the ``USING`` expression, so an omission would look identical
    in a diff and behave identically until the day somebody wrote a row into
    another tenant. ``registry.revision`` denormalises ``workspace_id`` from its
    parent (ADR-0045), which is precisely the shape where a mis-stamp is a
    realistic cross-tenant write rather than a theoretical one.
    """
    await _two_tenants(migrate_engine)

    with pytest.raises(ProgrammingError) as refused:
        async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
            await db.execute(
                MISSTAMPED_REVISION,
                {
                    "version_id": "rev_01J0000000000000000SMUG",
                    "workspace_id": WORKSPACE_B,
                    "prompt_id": OTHER_PROMPT,
                },
            )

    assert "policy" in str(refused.value).lower()
