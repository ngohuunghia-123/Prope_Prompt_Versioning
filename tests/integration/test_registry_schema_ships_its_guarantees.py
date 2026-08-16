"""AC-8 and AC-9, plus the privilege half of T-020, against the live catalogue.

Each of these is a sentence somewhere in prose — the lock file, ADR-0048,
ADR-0045 — that becomes false the moment a later revision breaks it without
anybody noticing. Written as a query over what the database actually holds
rather than as a reading of ``0008_registry_schema.py``: reading the migration
proves the migration says so, not that the database does.

**The trigger tests bypass the application entirely** and that is the whole
point of AC-8. A trigger is invisible at the call site — the criticism ADR-0042
levelled at absent policies — so a test that went through ``commands.create_
revision`` would pass just as well if the application maintained ``search_text``
itself, which is precisely the arrangement ADR-0048 rejected.
"""

from sqlalchemy import text

from tests.prompt_registry import PROMPT_ID, seed_prompt, seed_revision
from tests.unit import WORKSPACE_A

LIST_TRIGGERS = text(
    """
    SELECT t.tgname, c.relname
    FROM   pg_trigger AS t
    JOIN   pg_class AS c ON c.oid = t.tgrelid
    JOIN   pg_namespace AS n ON n.oid = c.relnamespace
    WHERE  n.nspname = 'registry' AND NOT t.tgisinternal
    ORDER  BY t.tgname
    """
)

READ_SEARCH_TEXT = text("SELECT search_text FROM registry.prompt_property WHERE id = :id")

READ_UPDATED_AT = text("SELECT updated_at FROM registry.prompt_property WHERE id = :id")

RETITLE = text("UPDATE registry.prompt_property SET title = :title WHERE id = :id")

APP_TABLE_PRIVILEGES = text(
    """
    SELECT table_name, privilege_type
    FROM   information_schema.table_privileges
    WHERE  table_schema = 'registry' AND grantee = 'prope_app'
    ORDER  BY table_name, privilege_type
    """
)

APP_COLUMN_PRIVILEGES = text(
    """
    SELECT table_name, column_name, privilege_type
    FROM   information_schema.column_privileges
    WHERE  table_schema = 'registry' AND grantee = 'prope_app'
      AND  privilege_type = 'UPDATE' AND table_name = 'revision'
    ORDER  BY column_name
    """
)

LIST_POLICIES = text(
    """
    SELECT tablename, policyname, qual, with_check
    FROM   pg_policies
    WHERE  schemaname = 'registry'
    ORDER  BY tablename
    """
)

LIST_INDEXES = text(
    "SELECT indexname FROM pg_indexes WHERE schemaname = 'registry' ORDER BY indexname"
)

LIST_EXTENSIONS = text(
    """
    SELECT e.extname, n.nspname
    FROM   pg_extension AS e
    JOIN   pg_namespace AS n ON n.oid = e.extnamespace
    WHERE  e.extname IN ('pg_trgm', 'unaccent')
    ORDER  BY e.extname
    """
)


async def test_both_search_text_triggers_exist(migrate_engine) -> None:
    """AC-8's first half. Two triggers, on the two tables ADR-0048 names."""
    async with migrate_engine.begin() as connection:
        triggers = (await connection.execute(LIST_TRIGGERS)).all()

    assert sorted(triggers) == [
        ("property_rebuilds_search_text", "prompt_property"),
        ("revision_rebuilds_search_text", "revision"),
    ]


async def test_a_direct_insert_bypassing_the_application_still_rewrites_search_text(
    migrate_engine,
) -> None:
    """AC-8's second half, and the reason the column is a trigger's and not the app's.

    Nothing in ``prope.prompt_registry`` runs in this test. The row goes in as
    ``prope_migrate`` — a migration, a backfill, a person with psql — and the
    parent's document still gains the body, because drift here is silent and
    wrong in the unsafe direction: a body edited without ``search_text``
    rewritten makes the prompt UN-FINDABLE BY ITS OWN NEW TEXT, with no error,
    no metric and no failed query.
    """
    await seed_prompt(migrate_engine)

    async with migrate_engine.begin() as connection:
        before = await connection.scalar(READ_SEARCH_TEXT, {"id": PROMPT_ID})

    assert "authentication" not in before

    await seed_revision(migrate_engine, body="Classify the authentication failure.")

    async with migrate_engine.begin() as connection:
        after = await connection.scalar(READ_SEARCH_TEXT, {"id": PROMPT_ID})

    assert "authentication" in after
    assert "first draft" in after


async def test_editing_a_title_rewrites_the_document_and_leaves_the_body_in_it(
    migrate_engine,
) -> None:
    """The second trigger, and the property that makes it more than a duplicate.

    A title edit must not blow the body out of the document. Rebuilding from
    scratch rather than appending is what makes an edit *replace* the old title
    rather than accumulate both — and re-reading the revisions is what stops the
    rebuild losing everything it did not receive as a parameter.
    """
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine, body="Classify the authentication failure.")

    async with migrate_engine.begin() as connection:
        await connection.execute(RETITLE, {"id": PROMPT_ID, "title": "Tiêu đề mới"})
        document = await connection.scalar(READ_SEARCH_TEXT, {"id": PROMPT_ID})

    assert "authentication" in document
    assert "tieu de moi" in document
    assert "refund classifier" not in document


async def test_saving_a_revision_moves_the_parent_updated_at(migrate_engine) -> None:
    """The consequence the lock calls *"desirable, and new"*.

    A freshly edited prompt rises to the top of the default ``updated_at DESC``
    list, because the trigger that rebuilds the document also stamps the parent.
    Asserted because the list endpoint's cursor is built on that ordering, so a
    change to it is a change to pagination.
    """
    await seed_prompt(migrate_engine)

    async with migrate_engine.begin() as connection:
        before = await connection.scalar(READ_UPDATED_AT, {"id": PROMPT_ID})

    await seed_revision(migrate_engine)

    async with migrate_engine.begin() as connection:
        after = await connection.scalar(READ_UPDATED_AT, {"id": PROMPT_ID})

    assert after > before


async def test_prope_app_may_not_delete_and_may_update_only_the_status_column(
    migrate_engine,
) -> None:
    """T-020's privilege half, which the threat note said was unavailable.

    ADR-0002 makes ``revision`` append-only and INT-012 needs ``UPDATE`` on
    ``status``, so the table cannot take ADR-0025's treatment wholesale. A
    COLUMN-level grant is the honest middle: the one column a command may move is
    the only one granted, and append-only stops being a convention.

    ``prompt_property`` holds no DELETE either — A-049 makes ``Retired`` a
    terminal status rather than a removal, and a privilege is what makes that
    true against a caller who disagrees.
    """
    async with migrate_engine.begin() as connection:
        table_grants = {
            (table, privilege)
            for table, privilege in (await connection.execute(APP_TABLE_PRIVILEGES)).all()
        }
        status_only = (await connection.execute(APP_COLUMN_PRIVILEGES)).all()

    assert ("revision", "DELETE") not in table_grants
    assert ("prompt_property", "DELETE") not in table_grants

    assert ("revision", "SELECT") in table_grants
    assert ("revision", "INSERT") in table_grants
    assert ("prompt_property", "UPDATE") in table_grants

    assert [column for _, column, _ in status_only] == ["status"]


async def test_every_table_carries_row_level_security_with_a_policy(migrate_engine) -> None:
    """AC-9. ``registry.revision`` is the table ADR-0045's inverted walk caught.

    It had no tenant column for five module passes because it was reachable only
    through ``prompt_id`` — and it holds EVERY PROMPT BODY IN PROPE. The policy
    reads ``workspace_id`` and its ``WITH CHECK`` is written out rather than
    defaulted, so a mis-stamped insert is refused as well as a foreign read.

    ``folder`` joined them at 0016. It holds nothing secret — a name and a colour
    for a namespace — but the list is asserted whole rather than per-table, so a
    new registry table that forgot its policy fails here and not in a review.
    """
    async with migrate_engine.begin() as connection:
        policies = (await connection.execute(LIST_POLICIES)).all()

    assert [table for table, _, _, _ in policies] == ["folder", "prompt_property", "revision"]
    for _, _, using, with_check in policies:
        assert "workspace_id" in using
        assert "current_setting" in using
        assert with_check is not None


async def test_the_trigram_index_and_both_extensions_ship_with_the_schema(
    migrate_engine,
) -> None:
    """ADR-0048's index, and A-150's folding dictionary, in the module's own schema.

    Installed into ``registry`` rather than ``public`` because revision 0001
    revoked everything on ``public`` from ``PUBLIC`` on purpose, and widening
    that to make room for an extension would undo a deny-by-default posture to
    save a schema qualifier.
    """
    async with migrate_engine.begin() as connection:
        indexes = (await connection.execute(LIST_INDEXES)).scalars().all()
        extensions = (await connection.execute(LIST_EXTENSIONS)).all()

    assert "ix_prompt_property_search_text" in indexes
    assert extensions == [("pg_trgm", "registry"), ("unaccent", "registry")]


async def test_the_workspace_column_on_revision_is_populated_not_merely_present(
    migrate_engine,
) -> None:
    """ADR-0045 asks for a column the enumeration can SEE, which is worth
    nothing if the write path leaves it NULL."""
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine)

    async with migrate_engine.begin() as connection:
        workspace = await connection.scalar(
            text("SELECT workspace_id FROM registry.revision WHERE prompt_id = :id"),
            {"id": PROMPT_ID},
        )

    assert workspace == WORKSPACE_A
