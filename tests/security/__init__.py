"""Security tests — guarantees the database enforces, asserted against it.

Each test in this package carries a positive control. An RLS test against an
empty table passes for the wrong reason, and a privilege test whose UPDATE
matched zero rows is indistinguishable from one the engine refused.

The row builder below produces the simplest row the CHECK set accepts: a
gateway call with reported usage and no price row in force, which is
``cost_status = 'unpriced'`` with a NULL cost. Tests that want a refusal
override exactly the one field that should cause it, so the constraint named in
the error is the constraint under test.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

WORKSPACE_A = "wsp_01J0000000000000000000AAA"
WORKSPACE_B = "wsp_01J0000000000000000000BBB"

#: A tenant identifier carrying the character that breaks string-assembled SQL.
WORKSPACE_WITH_QUOTE = "wsp_o'brien"

#: The call's own timestamp. Never a default, never wall clock (ADR-0019).
CREATED_AT = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)

INSERT_CALL_RECORD = text(
    """
    INSERT INTO ledger.call_record (
        call_id, workspace_id, source, version_id, outcome,
        pinned, fallback, streaming,
        input_tokens, output_tokens, usage_status,
        cost, currency, price_row_id, cost_status,
        created_at
    ) VALUES (
        :call_id, :workspace_id, :source, :version_id, :outcome,
        false, false, false,
        :input_tokens, :output_tokens, :usage_status,
        :cost, :currency, :price_row_id, :cost_status,
        :created_at
    )
    """
)

SELECT_CALL_IDS = text("SELECT call_id FROM ledger.call_record ORDER BY call_id")
COUNT_CALL_RECORDS = text("SELECT count(*) FROM ledger.call_record")
READ_TENANT_GUC = text("SELECT current_setting('app.workspace_id', true)")


def call_record_values(**overrides: Any) -> dict[str, Any]:
    """The simplest row the CHECK set accepts, with targeted overrides."""
    values: dict[str, Any] = {
        "call_id": "cal_01J0000000000000000000001",
        "workspace_id": WORKSPACE_A,
        "source": "gateway",
        "version_id": "ver_01J0000000000000000000001",
        "outcome": "ok",
        "input_tokens": 120,
        "output_tokens": 340,
        "usage_status": "reported",
        "cost": None,
        "currency": None,
        "price_row_id": None,
        "cost_status": "unpriced",
        "created_at": CREATED_AT,
    }
    values.update(overrides)
    return values
