"""AC-6 and BR-03: the database refuses an unapproved released pointer.

**This is the one failure that makes the whole product worthless** — production
serving prompt text nobody approved — and it is the reason the enforcement is a
constraint rather than an ``if``. Every test below writes as ``prope_migrate``,
the OWNER, which bypasses row-level security and every application code path:
what is left refusing the write is the engine.

The constraint is a composite foreign key from
``(released_version_id, released_revision_status)`` into
``revision (version_id, status)``, where the second column of the referencing
pair is a STORED generated column that is the literal ``'Approved'`` whenever a
pointer is set. ``MATCH SIMPLE`` skips the check entirely when either column is
NULL, which is what lets INT-014's withdrawal exist without a carve-out
(ADR-0009).
"""

import pytest
from sqlalchemy import TextClause, text
from sqlalchemy.exc import IntegrityError, ProgrammingError

from tests.prompt_registry import (
    PROMPT_ID,
    VERSION_ID,
    approve,
    day,
    release,
    seed_prompt,
    seed_revision,
)

CONSTRAINT = "fk_prompt_property_released_version_id"

RELEASE = text(
    """
    UPDATE registry.prompt_property
       SET released_version_id = :version_id, released_at = :now
     WHERE id = :prompt_id
    """
)

DEMOTE = text("UPDATE registry.revision SET status = :status WHERE version_id = :version_id")

CLEAR = text(
    """
    UPDATE registry.prompt_property
       SET released_version_id = NULL, released_at = NULL
     WHERE id = :prompt_id
    """
)

READ_POINTER = text("SELECT released_version_id FROM registry.prompt_property WHERE id = :id")

WRITE_GENERATED_COLUMN = text(
    "UPDATE registry.prompt_property SET released_revision_status = 'Approved' WHERE id = :id"
)


async def _execute(migrate_engine, statement: TextClause, values: dict) -> None:  # noqa: ANN001
    async with migrate_engine.begin() as connection:
        await connection.execute(statement, values)


async def _pointer(migrate_engine) -> str | None:  # noqa: ANN001
    async with migrate_engine.begin() as connection:
        return await connection.scalar(READ_POINTER, {"id": PROMPT_ID})


async def test_a_draft_target_is_rejected_by_the_database(migrate_engine) -> None:
    """AC-6 exactly: the write is rejected and the pointer is unchanged."""
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine)

    with pytest.raises(IntegrityError) as refused:
        await _execute(
            migrate_engine,
            RELEASE,
            {"prompt_id": PROMPT_ID, "version_id": VERSION_ID, "now": day(2)},
        )

    assert CONSTRAINT in str(refused.value)
    assert await _pointer(migrate_engine) is None


@pytest.mark.parametrize("status", ["Draft", "In review"])
async def test_every_unapproved_status_is_rejected(migrate_engine, status: str) -> None:
    """Both non-terminal statuses, because the constraint compares one literal.

    Parametrised rather than written twice so that adding a fourth status to
    ``ck_revision_status_values`` without thinking about BR-03 fails here.
    """
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine, status=status)

    with pytest.raises(IntegrityError):
        await _execute(
            migrate_engine,
            RELEASE,
            {"prompt_id": PROMPT_ID, "version_id": VERSION_ID, "now": day(2)},
        )


async def test_an_approved_target_is_accepted(migrate_engine) -> None:
    """The positive control. A constraint that refused everything would pass
    every test above and break the product."""
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine)
    await approve(migrate_engine)
    await release(migrate_engine)

    assert await _pointer(migrate_engine) == VERSION_ID


async def test_a_released_revision_cannot_be_demoted_out_of_approved(
    migrate_engine,
) -> None:
    """The direction nobody thinks of, and the one a status command could hit.

    INT-012 accepts ``Approved -> Draft`` — that is the changes-requested path —
    so the state machine alone would let a reviewer put a LIVE revision back into
    Draft while the gateway is still serving it. The constraint refuses it from
    the other side, which is what makes *the released revision is always
    Approved* an invariant over time rather than only at the moment of release.
    """
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine)
    await approve(migrate_engine)
    await release(migrate_engine)

    with pytest.raises(IntegrityError) as refused:
        await _execute(migrate_engine, DEMOTE, {"version_id": VERSION_ID, "status": "Draft"})

    assert CONSTRAINT in str(refused.value)


async def test_clearing_the_pointer_needs_no_carve_out_in_the_constraint(
    migrate_engine,
) -> None:
    """ADR-0009's structural argument, asserted rather than described.

    A NULL pointer skips the check under ``MATCH SIMPLE``, so a withdrawal
    requires nothing of the constraint that enforces BR-03. That is why INT-014
    is a separate command instead of ``set_released_revision(..., NULL)``: the
    alternative would have bought one function signature at the price of a NULL
    carve-out in a non-negotiable rule.
    """
    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine)
    await approve(migrate_engine)
    await release(migrate_engine)

    await _execute(migrate_engine, CLEAR, {"prompt_id": PROMPT_ID})

    assert await _pointer(migrate_engine) is None


async def test_the_generated_column_cannot_be_written_by_anybody(migrate_engine) -> None:
    """The half of the mechanism that would otherwise be a hole.

    If ``released_revision_status`` were an ordinary column the application
    maintained, a write that set it to ``'Approved'`` beside a Draft pointer
    would satisfy the foreign key by lying. ``GENERATED ALWAYS ... STORED`` makes
    that unreachable at the engine, for the owner as much as for ``prope_app``.
    """
    await seed_prompt(migrate_engine)

    with pytest.raises((ProgrammingError, IntegrityError)) as refused:
        await _execute(migrate_engine, WRITE_GENERATED_COLUMN, {"id": PROMPT_ID})

    assert "generated" in str(refused.value).lower()
