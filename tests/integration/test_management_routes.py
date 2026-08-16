"""INT-028's five routes, against the live engine, through the assembled router.

**A route that answers 200 and writes nothing looks healthy** — the drain's
failure mode (plan 02-01) and the retention job's (plan 02-03), one layer up. So
nothing here believes a response body about what is stored. Every assertion about
state goes through ``migrate_engine``, the owner role subject to no policy, or
through the *function that will actually read the value in production*:
``read_retention_window`` for the window the drain reads, and
``seams.check_spend_ceiling`` for the ceiling.

**The ceiling round trip is the load-bearing test in this file.** ``api.py``
never imports ``seams.py`` — call-ledger is a sink and the route makes no
cross-module call — so the agreement between the columns the ``PUT`` writes and
the columns ``check_spend_ceiling`` reads is a **data** contract with no symbol
reference holding it together. This file is what holds it together: it imports
the real seam and drives it through the real route. If the two ever disagree
about ``enabled``, ``monthly_limit`` or ``currency``, this is the test that says
so.

**Where the three ceiling states are observed, and why not through a ``GET``.**
INT-028 registers ``PUT`` and no other method on
``/api/v1/workspaces/{id}/spend-ceiling``. There is no ``GET /spend-ceiling``,
this phase adds none, and the route-table test fails on a sixth ``/api/v1`` path.
So "never configured" and "configured then turned off" are told apart in the only
two places that exist: the ``PUT`` response body of the call that produced the
state, and the row itself read through ``migrate_engine``.

**The session boundary is overridden, and the override is a test seam rather
than a bypass.** ``prope.session_auth.require_session`` refuses every request
until Phase 7 (see its docstring), so these tests replace it through FastAPI's
``dependency_overrides``. ``test_every_route_refuses_without_a_session`` is the
control: the same application with no override serves nothing.
"""

import ast
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.sql.elements import TextClause

import prope.call_ledger.api as api_module
from prope.call_ledger.api import router
from prope.call_ledger.retention_settings import read_retention_window
from prope.call_ledger.schemas import (
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
    MAX_RETENTION_DAYS,
    ErrorCode,
    install_error_envelope,
)
from prope.call_ledger.seams import check_spend_ceiling
from prope.call_ledger.writer import UNPRICED_WORKLIST, period_month, write_records
from prope.db.session import workspace_transaction
from prope.session_auth import Session, require_session
from tests.integration._asgi import call
from tests.unit import (
    PROVIDER_CONFIG,
    UPSTREAM_MODEL,
    WORKSPACE_A,
    WORKSPACE_B,
    day,
    gateway_draft,
    seed_price_row,
)

ACTOR = "usr_01J000000000000000000001"
SESSION = Session(user_id=ACTOR, workspace_id=WORKSPACE_A)

#: One ``gateway_draft`` at the fixture prices — 300 input and 150 output tokens
#: at 0.00015 / 0.0006 per 1k. Every ceiling below sits either side of it. Same
#: figure ``tests/integration/test_ceiling_refuses_evals_only.py`` uses, derived
#: the same way, because both files have to place a limit against real traffic.
GATEWAY_COST = Decimal("0.000135")

READ_CEILING_ROW = text(
    """
    SELECT monthly_limit, per_run_limit, currency, enabled, updated_by
    FROM   ledger.spend_ceiling
    WHERE  workspace_id = :ws
    """
)
READ_SPEND = text(
    """
    SELECT currency, total_cost, call_count FROM ledger.workspace_spend
    WHERE  workspace_id = :ws AND period_month = :month
    """
)
READ_PRICE_ROWS = text(
    """
    SELECT price_row_id, workspace_id, provider_config_id, upstream_model,
           input_price_per_1k, output_price_per_1k, minimum_charge_per_request,
           currency, effective_from, created_by
    FROM   ledger.price_table
    ORDER  BY price_row_id
    """
)
COUNT_PRICE_ROWS = text("SELECT count(*) FROM ledger.price_table")
COUNT_RETENTION_ROWS = text("SELECT count(*) FROM ledger.workspace_retention")

#: Every path INT-028 registers, with its method. Used by the
#: refuses-without-a-session control so a route added later cannot skip it.
ROUTES = (
    ("POST", "/api/v1/prices"),
    ("GET", "/api/v1/prices"),
    ("GET", "/api/v1/prices/unpriced"),
    ("PUT", f"/api/v1/workspaces/{WORKSPACE_A}/spend-ceiling"),
    ("PUT", f"/api/v1/workspaces/{WORKSPACE_A}/retention"),
)


def build_application(sessionmaker: async_sessionmaker[AsyncSession]) -> FastAPI:
    """The router, mounted the way ``prope.app`` mounts it, minus the health routes.

    ``install_error_envelope`` is not optional decoration: without it a
    ``ManagementRefusal`` would surface as an unhandled exception and FastAPI's
    own validation answer would be a second error shape, which is exactly what
    A-045 says does not exist.
    """
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    install_error_envelope(application)
    application.include_router(router)
    application.state.sessionmaker = sessionmaker
    return application


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]) -> FastAPI:
    """The router with the session boundary overridden for the duration."""
    application = build_application(app_sessionmaker)
    application.dependency_overrides[require_session] = lambda: SESSION
    return application


@pytest.fixture
def unauthenticated(app_sessionmaker: async_sessionmaker[AsyncSession]) -> FastAPI:
    """The same application as it actually ships: nothing overridden."""
    return build_application(app_sessionmaker)


def price_payload(**overrides: object) -> dict[str, object]:
    """The simplest body ``POST /api/v1/prices`` accepts."""
    values: dict[str, object] = {
        "provider_config_id": PROVIDER_CONFIG,
        "upstream_model": UPSTREAM_MODEL,
        "input_price_per_1k": "0.00015",
        "output_price_per_1k": "0.0006",
        "currency": "USD",
        "effective_from": day(1).isoformat(),
    }
    values.update(overrides)
    return values


async def record_gateway_traffic(
    sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
    workspace_id: str,
    *,
    call_id: str,
    seed_price: bool = True,
) -> None:
    """One priced gateway call for ``workspace_id``, through the real write path.

    ``seed_price=False`` for a second call in the same workspace:
    ``uq_price_table_workspace_id`` refuses a duplicate
    ``(workspace_id, provider_config_id, upstream_model, effective_from)``, which
    is the uniqueness that makes effective-dated resolution deterministic
    (ADR-0019).
    """
    if seed_price:
        await seed_price_row(
            migrate_engine,
            workspace_id=workspace_id,
            price_row_id=f"prc_seed_{workspace_id[-3:]}",
        )
    async with workspace_transaction(sessionmaker, workspace_id) as session:
        await write_records(
            session, [gateway_draft(workspace_id=workspace_id, call_id=call_id)]
        )


# --------------------------------------------------------------------------- #
# The declared session boundary
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(("method", "path"), ROUTES)
async def test_every_route_refuses_without_a_session(
    unauthenticated: FastAPI, method: str, path: str
) -> None:
    """No route defaults to unauthenticated access. Five routes, five refusals.

    The failure this is shaped against is not "authentication is missing" — it
    is that five routes could have been mounted with no dependency at all and
    nothing in the repository would have said so (Pitfall 11).
    """
    response = await call(unauthenticated, method, path, json_body={} if method != "GET" else None)

    assert response.status_code == 401, response.body
    assert response.code == ErrorCode.SESSION_REQUIRED.value
    envelope = response.json()["error"]
    assert set(envelope) == {"code", "message", "details", "request_id"}
    assert envelope["request_id"].startswith("req_")


async def test_the_refusal_quotes_no_part_of_the_session_cookie(
    unauthenticated: FastAPI,
) -> None:
    """A session cookie is a credential; the refusal names none of it (A-046)."""
    secret = "sk-a-cookie-value-nobody-should-see"
    response = await call(
        unauthenticated,
        "GET",
        "/api/v1/prices",
        headers={"cookie": f"prope_session={secret}"},
    )

    assert response.status_code == 401
    assert secret not in response.body.decode()


# --------------------------------------------------------------------------- #
# POST /api/v1/prices — append-only, and CR-01
# --------------------------------------------------------------------------- #


async def test_a_price_row_is_appended_and_returned_with_a_prc_identifier(
    api: FastAPI, migrate_engine: AsyncEngine
) -> None:
    """The row lands, carries a server-generated ``prc_`` ULID, and is in force."""
    response = await call(api, "POST", "/api/v1/prices", json_body=price_payload())

    assert response.status_code == 201, response.body
    created = response.json()
    assert created["price_row_id"].startswith("prc_")
    # In force: nothing supersedes it, so the derived range is open-ended.
    assert created["effective_to"] is None
    assert created["created_by"] == ACTOR

    async with migrate_engine.begin() as connection:
        rows = (await connection.execute(READ_PRICE_ROWS)).mappings().all()

    assert len(rows) == 1
    assert rows[0]["price_row_id"] == created["price_row_id"]
    # The workspace comes from the session and is not a field a caller can send.
    assert rows[0]["workspace_id"] == WORKSPACE_A
    assert rows[0]["created_by"] == ACTOR


async def test_a_superseding_row_leaves_the_earlier_row_byte_identical(
    api: FastAPI, migrate_engine: AsyncEngine
) -> None:
    """T-02-31: a price is superseded by a NEW row and the old one is untouched.

    Asserted by comparing every column of the earlier row before and after, not
    by asserting the row still exists — an ``UPDATE`` would leave it existing.
    """
    first = (await call(api, "POST", "/api/v1/prices", json_body=price_payload())).json()

    async with migrate_engine.begin() as connection:
        before = (await connection.execute(READ_PRICE_ROWS)).mappings().all()[0]
    before_values = dict(before)

    second = (
        await call(
            api,
            "POST",
            "/api/v1/prices",
            json_body=price_payload(
                input_price_per_1k="0.0002", effective_from=day(10).isoformat()
            ),
        )
    ).json()
    assert second["price_row_id"] != first["price_row_id"]

    async with migrate_engine.begin() as connection:
        after = (await connection.execute(READ_PRICE_ROWS)).mappings().all()

    assert len(after) == 2
    survivor = next(row for row in after if row["price_row_id"] == first["price_row_id"])
    assert dict(survivor) == before_values


async def test_a_free_tier_price_row_is_refused_and_nothing_is_inserted(
    api: FastAPI, migrate_engine: AsyncEngine
) -> None:
    """CR-01. A ``(0, 0)`` row is refused at the only place a human can create one.

    Phase 1's verifier established the chain and recommended this disposition:
    the CHECK permits it because it is non-negative, ``compute_cost`` returns
    exactly zero, and ``write_records`` then raises on a zero cost and discards
    the whole batch. One free-tier row poisons every batch containing a call it
    prices (T-02-32).
    """
    response = await call(
        api,
        "POST",
        "/api/v1/prices",
        json_body=price_payload(input_price_per_1k="0", output_price_per_1k="0"),
    )

    assert response.status_code == 422, response.body
    assert response.code == ErrorCode.PRICE_BOTH_PRICES_ARE_ZERO.value

    async with migrate_engine.begin() as connection:
        assert (await connection.execute(COUNT_PRICE_ROWS)).scalar_one() == 0


async def test_one_zero_price_beside_a_non_zero_one_is_accepted(api: FastAPI) -> None:
    """The negative control: CR-01 is about a row that prices EVERYTHING at zero.

    A model that charges for output and not for input is an ordinary price row,
    and refusing it would be refusing a real tariff to satisfy a rule about a
    different one.
    """
    response = await call(
        api, "POST", "/api/v1/prices", json_body=price_payload(input_price_per_1k="0")
    )

    assert response.status_code == 201, response.body


async def test_a_flat_per_request_tariff_is_accepted_despite_two_zero_rates(
    api: FastAPI, migrate_engine: AsyncEngine
) -> None:
    """Migration 0017 narrows CR-01 rather than repealing it.

    A provider that bills a flat amount per request and nothing per token is a
    real tariff, and ``(0, 0)`` is the only honest way to write its rates. The
    chain that made ``(0, 0)`` poisonous — zero cost, then a whole batch
    discarded — does not run when the floor is positive, so refusing this shape
    would be refusing a tariff to satisfy a rule about a different one.
    """
    response = await call(
        api,
        "POST",
        "/api/v1/prices",
        json_body=price_payload(
            input_price_per_1k="0",
            output_price_per_1k="0",
            minimum_charge_per_request="0.01",
        ),
    )

    assert response.status_code == 201, response.body
    assert response.json()["minimum_charge_per_request"] == "0.0100000000"

    async with migrate_engine.begin() as connection:
        rows = (await connection.execute(READ_PRICE_ROWS)).mappings().all()
    assert rows[0]["minimum_charge_per_request"] == Decimal("0.0100000000")


async def test_all_three_figures_at_zero_is_still_refused(
    api: FastAPI, migrate_engine: AsyncEngine
) -> None:
    """CR-01's actual condition, now that there are three ways to be non-zero.

    Such a row prices every call it applies to at exactly zero,
    ``ck_call_record_cost_is_never_zero`` refuses it at write time, and the whole
    batch is discarded (T-02-32).
    """
    response = await call(
        api,
        "POST",
        "/api/v1/prices",
        json_body=price_payload(
            input_price_per_1k="0",
            output_price_per_1k="0",
            minimum_charge_per_request="0",
        ),
    )

    assert response.status_code == 422, response.body
    assert response.code == ErrorCode.PRICE_BOTH_PRICES_ARE_ZERO.value

    async with migrate_engine.begin() as connection:
        assert (await connection.execute(COUNT_PRICE_ROWS)).scalar_one() == 0


async def test_a_negative_minimum_is_refused_by_the_engine(
    api: FastAPI, migrate_engine: AsyncEngine
) -> None:
    """``ck_price_table_minimum_charge_is_non_negative``, answered as the same
    ``code`` a negative per-1k price gets.

    Two CHECKs because 0017 could not extend 0003's, one refusal because "a
    figure on a rate card may not be negative" is one rule to whoever is typing
    — and a second code would be a second entry the SPA has to translate.
    """
    response = await call(
        api,
        "POST",
        "/api/v1/prices",
        json_body=price_payload(minimum_charge_per_request="-0.01"),
    )

    assert response.status_code == 422, response.body
    assert response.code == ErrorCode.PRICE_IS_NEGATIVE.value
    body = response.body.decode()
    assert "ck_price_table" not in body
    assert "constraint" not in body.lower()

    async with migrate_engine.begin() as connection:
        assert (await connection.execute(COUNT_PRICE_ROWS)).scalar_one() == 0


async def test_a_price_row_omitting_the_minimum_stores_a_zero_floor(
    api: FastAPI, migrate_engine: AsyncEngine
) -> None:
    """The field is optional and its absence is a legible zero, not a NULL.

    This is what every row written before 0017 means, and it is what keeps a
    caller that has never heard of a per-request minimum sending the body it
    always sent.
    """
    response = await call(api, "POST", "/api/v1/prices", json_body=price_payload())

    assert response.status_code == 201, response.body
    assert response.json()["minimum_charge_per_request"] == "0.0000000000"

    async with migrate_engine.begin() as connection:
        rows = (await connection.execute(READ_PRICE_ROWS)).mappings().all()
    assert rows[0]["minimum_charge_per_request"] == Decimal("0")


async def test_a_colliding_row_is_refused_with_details_and_no_constraint_name(
    api: FastAPI, migrate_engine: AsyncEngine
) -> None:
    """INT-028's ``422`` on an ambiguous effective range, in the one envelope.

    ``details`` names the four values the caller sent; the message names none of
    the engine's words. A constraint name reaching a client is T-02-34, and it
    is also a string the SPA's translation catalogue has no entry for.
    """
    assert (await call(api, "POST", "/api/v1/prices", json_body=price_payload())).status_code == 201

    response = await call(api, "POST", "/api/v1/prices", json_body=price_payload())

    assert response.status_code == 422, response.body
    assert response.code == ErrorCode.PRICE_EFFECTIVE_RANGE_AMBIGUOUS.value

    error = response.json()["error"]
    assert set(error["details"]) == {
        "workspace_id",
        "provider_config_id",
        "upstream_model",
        "effective_from",
    }
    body = response.body.decode()
    assert "uq_price_table" not in body
    assert "constraint" not in body.lower()

    async with migrate_engine.begin() as connection:
        assert (await connection.execute(COUNT_PRICE_ROWS)).scalar_one() == 1


async def test_a_price_with_more_scale_than_the_column_is_refused(
    api: FastAPI, migrate_engine: AsyncEngine
) -> None:
    """An eleventh decimal place would be rounded away by ``numeric(20,10)``.

    A stored price different from the submitted one is what T-006's append-only
    privilege set exists to keep from happening quietly.
    """
    response = await call(
        api,
        "POST",
        "/api/v1/prices",
        json_body=price_payload(input_price_per_1k="0.00000000005"),
    )

    assert response.status_code == 422, response.body
    assert response.code == ErrorCode.MONEY_SCALE_EXCEEDED.value

    async with migrate_engine.begin() as connection:
        assert (await connection.execute(COUNT_PRICE_ROWS)).scalar_one() == 0


def test_the_router_issues_no_update_and_no_delete_against_the_price_table() -> None:
    """A structural gate, in ``test_no_sql_interpolation.py``'s posture.

    The behavioural half is asserted above. This is the structural half: every
    statement ``api.py`` can execute against ``ledger.price_table`` is a
    ``SELECT`` or an ``INSERT``. It matters because ``prope_app`` holds no
    ``UPDATE`` or ``DELETE`` grant on that table (T-006), so an ``UPDATE`` added
    here would surface as a **permission error** — and a route that meets a
    permission error is a route somebody will be tempted to fix by widening the
    grant rather than by asking why the grant is narrow.

    The assertion is over the **compiled statements**, not over the source text:
    a docstring that discusses ``UPDATE`` is prose, and a test that could not
    tell the difference would either fail on prose or pass by ignoring
    everything.
    """
    compiled = [
        str(value) for value in vars(api_module).values() if isinstance(value, TextClause)
    ]

    touching = [statement for statement in compiled if "ledger.price_table" in statement]
    assert touching, "no statement in api.py names ledger.price_table; has it moved?"
    for statement in touching:
        upper = statement.strip().upper()
        assert upper.startswith(("SELECT", "INSERT")), statement
        assert "UPDATE" not in upper, statement
        assert "DELETE" not in upper, statement

    # And every statement is a module-level constant, so the list above is the
    # whole set rather than the part that happened to be declared up front.
    tree = ast.parse(
        (Path(api_module.__file__).read_text(encoding="utf-8")),
        filename=api_module.__file__,
    )
    module_level = {
        node
        for assignment in tree.body
        if isinstance(assignment, ast.Assign)
        for node in ast.walk(assignment)
    }
    inline = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "text"
        and node not in module_level
    ]
    assert inline == [], "api.py builds SQL inside a function; every statement must be a constant"


# --------------------------------------------------------------------------- #
# GET /api/v1/prices — superseded rows, derived ranges, A-045 pagination
# --------------------------------------------------------------------------- #


async def test_superseded_rows_are_returned_with_their_derived_ranges(api: FastAPI) -> None:
    """A-102: a superseded row keeps being returned, and its range is derived.

    The range is half-open — the earlier row's ``effective_to`` is the later
    row's ``effective_from``, which is exactly what ``pricing.PRICE_IN_FORCE``
    already implements. Nothing stores it.
    """
    await call(api, "POST", "/api/v1/prices", json_body=price_payload())
    await call(
        api,
        "POST",
        "/api/v1/prices",
        json_body=price_payload(effective_from=day(10).isoformat()),
    )

    page = (await call(api, "GET", "/api/v1/prices")).json()

    assert len(page["items"]) == 2
    by_from = sorted(page["items"], key=lambda item: item["effective_from"])
    assert by_from[0]["effective_to"] == by_from[1]["effective_from"]
    assert by_from[1]["effective_to"] is None


async def test_a_row_for_another_model_does_not_close_this_model_s_range(
    api: FastAPI,
) -> None:
    """The window partitions by key, so an unrelated model is not a supersession."""
    await call(api, "POST", "/api/v1/prices", json_body=price_payload())
    await call(
        api,
        "POST",
        "/api/v1/prices",
        json_body=price_payload(upstream_model="gpt-4o", effective_from=day(10).isoformat()),
    )

    page = (await call(api, "GET", "/api/v1/prices")).json()

    assert [item["effective_to"] for item in page["items"]] == [None, None]


async def test_the_page_defaults_to_fifty_and_pages_with_a_cursor(
    api: FastAPI, migrate_engine: AsyncEngine
) -> None:
    """A-045's default, and the cursor that follows it. 51 rows, two pages."""
    for index in range(DEFAULT_PAGE_LIMIT + 1):
        await seed_price_row(
            migrate_engine,
            price_row_id=f"prc_{index:022d}",
            effective_from=day(1) + timedelta(hours=index),
        )

    first = (await call(api, "GET", "/api/v1/prices")).json()
    assert len(first["items"]) == DEFAULT_PAGE_LIMIT
    assert first["next_cursor"] == first["items"][-1]["price_row_id"]

    second = (
        await call(api, "GET", "/api/v1/prices", params={"cursor": first["next_cursor"]})
    ).json()
    assert len(second["items"]) == 1
    assert second["next_cursor"] is None

    seen = [item["price_row_id"] for item in first["items"] + second["items"]]
    assert len(set(seen)) == DEFAULT_PAGE_LIMIT + 1


async def test_a_limit_above_the_maximum_is_refused_rather_than_clamped(
    api: FastAPI,
) -> None:
    """T-02-33. 200 is a cap, and 201 is a ``422`` in the one envelope.

    Clamping would serve a page the caller did not ask for and report success,
    which is ``set_retention_window``'s reason for refusing a non-positive
    window one module over.
    """
    accepted = await call(api, "GET", "/api/v1/prices", params={"limit": MAX_PAGE_LIMIT})
    assert accepted.status_code == 200

    refused = await call(api, "GET", "/api/v1/prices", params={"limit": MAX_PAGE_LIMIT + 1})
    assert refused.status_code == 422, refused.body
    assert refused.code == ErrorCode.VALIDATION_FAILED.value
    # FastAPI's own answer would have been ``{"detail": [...]}``. A-045 says
    # there is one error shape, so the envelope handler is what produced this.
    assert "detail" not in refused.json()


async def test_money_crosses_the_wire_as_a_string_with_all_ten_places(
    api: FastAPI,
) -> None:
    """``numeric(20,10)`` survives the round trip exactly, and never as a float.

    A JSON number would hand a figure of order 0.00007 to a client's double and
    give it back changed; ``str(Decimal("1E-10"))`` would hand it over in
    scientific notation.
    """
    created = await call(
        api,
        "POST",
        "/api/v1/prices",
        json_body=price_payload(input_price_per_1k="0.0000000001"),
    )

    assert b'"input_price_per_1k":"0.0000000001"' in created.body
    assert Decimal(created.json()["input_price_per_1k"]) == Decimal("0.0000000001")


# --------------------------------------------------------------------------- #
# GET /api/v1/prices/unpriced — the route Phase 1 said Phase 2 owed
# --------------------------------------------------------------------------- #


async def test_the_unpriced_route_returns_what_the_phase_1_query_returns(
    api: FastAPI, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Served by ``writer.UNPRICED_WORKLIST`` unchanged — no second aggregate.

    Compared against a direct execution of the same statement rather than
    against a hand-written expectation, because the point is that there is one
    projection and this route serves it.
    """
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        await write_records(
            session,
            [
                gateway_draft(call_id="cal_unpriced_one"),
                gateway_draft(call_id="cal_unpriced_two"),
                gateway_draft(call_id="cal_unpriced_three", upstream_model="gpt-4o"),
            ],
        )

    served = (await call(api, "GET", "/api/v1/prices/unpriced")).json()

    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        direct = (await session.execute(UNPRICED_WORKLIST)).mappings().all()

    assert [(row["upstream_model"], row["unpriced_calls"]) for row in direct] == [
        (item["upstream_model"], item["unpriced_calls"]) for item in served
    ]
    assert [item["unpriced_calls"] for item in served] == [2, 1]


async def test_the_unpriced_worklist_carries_counts_and_no_figure(
    api: FastAPI, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """It is a worklist, not a total (INT-028): counts of calls, never money.

    An unpriced call has a NULL cost by construction, so there is nothing here
    to sum — but a route could have added one anyway. The field set is pinned,
    so a cost, a body or a byte size joining this response fails here as well as
    in the route-table test's OpenAPI walk.
    """
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as session:
        await write_records(session, [gateway_draft(call_id="cal_worklist_shape")])

    served = (await call(api, "GET", "/api/v1/prices/unpriced")).json()

    assert len(served) == 1
    assert set(served[0]) == {"provider_config_id", "upstream_model", "unpriced_calls", "since"}


# --------------------------------------------------------------------------- #
# PUT /api/v1/workspaces/{id}/retention — the write half of what the drain reads
# --------------------------------------------------------------------------- #


async def test_a_window_written_by_the_route_is_the_one_the_drain_reads(
    api: FastAPI, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """D-11's two halves meet: the route writes, ``read_retention_window`` reads.

    Asserted through the resolver ``prope.worker`` binds into the drain, not by
    reading the row — a route that wrote to the right table with the wrong units
    would pass a row-shaped assertion and starve the drain of the value.
    """
    response = await call(
        api,
        "PUT",
        f"/api/v1/workspaces/{WORKSPACE_A}/retention",
        json_body={"retention_days": 7},
    )

    assert response.status_code == 200, response.body
    assert response.json()["retention_days"] == 7

    assert await read_retention_window(app_sessionmaker, WORKSPACE_A) == timedelta(days=7)


@pytest.mark.parametrize("days", [0, -1])
async def test_a_non_positive_window_is_refused_and_stores_nothing(
    api: FastAPI, migrate_engine: AsyncEngine, days: int
) -> None:
    """``ck_workspace_retention_window_is_positive``, surfaced and never clamped.

    The guarantee stays at the engine; this route translates the refusal into
    the one envelope rather than re-checking it, so there is one place a
    retention window can be judged.
    """
    response = await call(
        api,
        "PUT",
        f"/api/v1/workspaces/{WORKSPACE_A}/retention",
        json_body={"retention_days": days},
    )

    assert response.status_code == 422, response.body
    assert response.code == ErrorCode.RETENTION_WINDOW_NOT_POSITIVE.value

    async with migrate_engine.begin() as connection:
        assert (await connection.execute(COUNT_RETENTION_ROWS)).scalar_one() == 0


async def test_a_window_above_the_bound_is_a_422_and_stores_nothing(
    api: FastAPI, migrate_engine: AsyncEngine
) -> None:
    """CR-01 at the route: the upper bound refuses before any ``timedelta`` is built.

    ``set_retention`` evaluates ``timedelta(days=payload.retention_days)`` before
    a statement exists, and above ``timedelta.max.days`` that raises
    ``OverflowError`` — an ``ArithmeticError`` that ``classify_write_failure``
    matches nowhere, so it would fall to the ``PERMANENT`` default and dead-letter
    two modules from here. ``le=MAX_RETENTION_DAYS`` makes it a ``422`` at the
    boundary instead, carrying the **existing** ``VALIDATION_FAILED``: no
    ``ErrorCode`` member was added, because a code the SPA's catalogue has never
    seen renders as nothing at all (ADR-0053).

    **This is a fix landed before its own exposure**, which is the cheap moment.
    ``require_session`` answers ``401`` unconditionally until Phase 7, so nobody
    can reach this route in production yet; the ``api`` fixture drives the handler
    through ``dependency_overrides``, which is this file's existing test seam and
    not a weakening of the boundary —
    ``test_every_route_refuses_without_a_session`` is the control that says so.
    """
    response = await call(
        api,
        "PUT",
        f"/api/v1/workspaces/{WORKSPACE_A}/retention",
        json_body={"retention_days": MAX_RETENTION_DAYS + 1},
    )

    assert response.status_code == 422, response.body
    assert response.code == ErrorCode.VALIDATION_FAILED.value

    async with migrate_engine.begin() as connection:
        assert (await connection.execute(COUNT_RETENTION_ROWS)).scalar_one() == 0


async def test_the_largest_window_the_bound_allows_still_takes_effect(
    api: FastAPI, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """The positive control for the test above: the cap is a cap, not a wall.

    Without this, a bound accidentally set to something absurdly small — or a
    handler that started refusing every window — would leave the ``422`` test
    passing for the wrong reason.
    """
    response = await call(
        api,
        "PUT",
        f"/api/v1/workspaces/{WORKSPACE_A}/retention",
        json_body={"retention_days": MAX_RETENTION_DAYS},
    )

    assert response.status_code == 200, response.body
    assert await read_retention_window(app_sessionmaker, WORKSPACE_A) == timedelta(
        days=MAX_RETENTION_DAYS
    )


async def test_a_workspace_the_session_cannot_see_is_not_found_never_forbidden(
    api: FastAPI, migrate_engine: AsyncEngine
) -> None:
    """T-02-30. ``403`` would confirm the workspace exists; ``404`` says nothing.

    And nothing is written — not to the named workspace, and not to the
    session's own, which is the failure a route that ignored ``{id}`` would have.
    """
    response = await call(
        api,
        "PUT",
        f"/api/v1/workspaces/{WORKSPACE_B}/retention",
        json_body={"retention_days": 7},
    )

    assert response.status_code == 404, response.body
    assert response.code == ErrorCode.NOT_FOUND.value
    assert WORKSPACE_B not in response.body.decode()

    async with migrate_engine.begin() as connection:
        assert (await connection.execute(COUNT_RETENTION_ROWS)).scalar_one() == 0


# --------------------------------------------------------------------------- #
# PUT /api/v1/workspaces/{id}/spend-ceiling — the round trip through the seam
# --------------------------------------------------------------------------- #


async def test_a_ceiling_set_below_recorded_spend_makes_the_seam_refuse(
    api: FastAPI,
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
) -> None:
    """The whole loop: real traffic, a ``PUT``, then the real ``check_spend_ceiling``.

    The refusal is produced by traffic through ``write_records`` rather than by
    a hand-inserted ``workspace_spend`` row, so what is asserted is the
    arithmetic of the write path and not the arithmetic of this test.
    """
    await record_gateway_traffic(
        app_sessionmaker, migrate_engine, WORKSPACE_A, call_id="cal_over_the_line"
    )

    allowed_before = await check_spend_ceiling(app_sessionmaker, WORKSPACE_A, now=day(5))
    assert allowed_before.allowed is True

    response = await call(
        api,
        "PUT",
        f"/api/v1/workspaces/{WORKSPACE_A}/spend-ceiling",
        json_body={
            "enabled": True,
            "monthly_limit": str(GATEWAY_COST / 2),
            "currency": "USD",
        },
    )
    assert response.status_code == 200, response.body

    decision = await check_spend_ceiling(app_sessionmaker, WORKSPACE_A, now=day(5))
    assert decision.allowed is False
    assert decision.reason is not None


async def test_clearing_the_limit_allows_again_and_leaves_the_spend_untouched(
    api: FastAPI,
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
) -> None:
    """Clearing writes the cleared state. It does not delete, and it does not bill.

    The spend row is compared before and after: a route that touched
    ``ledger.workspace_spend`` while clearing a ceiling would be a route that
    changed what a workspace is recorded as having spent.
    """
    await record_gateway_traffic(
        app_sessionmaker, migrate_engine, WORKSPACE_A, call_id="cal_cleared"
    )
    month = period_month(day(5))

    await call(
        api,
        "PUT",
        f"/api/v1/workspaces/{WORKSPACE_A}/spend-ceiling",
        json_body={
            "enabled": True,
            "monthly_limit": str(GATEWAY_COST / 2),
            "currency": "USD",
        },
    )
    assert (await check_spend_ceiling(app_sessionmaker, WORKSPACE_A, now=day(5))).allowed is False

    async with migrate_engine.begin() as connection:
        spend_before = dict(
            (await connection.execute(READ_SPEND, {"ws": WORKSPACE_A, "month": month}))
            .mappings()
            .one()
        )

    cleared = await call(
        api,
        "PUT",
        f"/api/v1/workspaces/{WORKSPACE_A}/spend-ceiling",
        json_body={"enabled": False, "monthly_limit": None, "currency": "USD"},
    )
    assert cleared.status_code == 200, cleared.body

    assert (await check_spend_ceiling(app_sessionmaker, WORKSPACE_A, now=day(5))).allowed is True

    async with migrate_engine.begin() as connection:
        spend_after = dict(
            (await connection.execute(READ_SPEND, {"ws": WORKSPACE_A, "month": month}))
            .mappings()
            .one()
        )
    assert spend_after == spend_before


async def test_a_disabled_row_and_no_row_both_allow_and_are_told_apart(
    api: FastAPI,
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
) -> None:
    """The three states, observed in the only two places INT-028 leaves open.

    ``WORKSPACE_A`` is configured and then turned off; ``WORKSPACE_B`` was never
    configured. Both allow. They are distinguished by the ``PUT`` response body
    — which states ``enabled`` and both limits — and by the row itself. There is
    no ``GET /spend-ceiling`` and none is called here: the route-table test fails
    on a sixth ``/api/v1`` path.
    """
    response = await call(
        api,
        "PUT",
        f"/api/v1/workspaces/{WORKSPACE_A}/spend-ceiling",
        json_body={
            "enabled": False,
            "monthly_limit": "1.0000000000",
            "per_run_limit": "0.5000000000",
            "currency": "USD",
        },
    )

    assert response.status_code == 200, response.body
    state = response.json()
    assert state["enabled"] is False
    assert state["monthly_limit"] == "1.0000000000"
    assert state["per_run_limit"] == "0.5000000000"
    assert state["currency"] == "USD"

    assert (await check_spend_ceiling(app_sessionmaker, WORKSPACE_A, now=day(5))).allowed is True
    assert (await check_spend_ceiling(app_sessionmaker, WORKSPACE_B, now=day(5))).allowed is True

    async with migrate_engine.begin() as connection:
        configured = (
            (await connection.execute(READ_CEILING_ROW, {"ws": WORKSPACE_A})).mappings().all()
        )
        never = (
            (await connection.execute(READ_CEILING_ROW, {"ws": WORKSPACE_B})).mappings().all()
        )

    assert len(configured) == 1
    assert configured[0]["enabled"] is False
    assert configured[0]["updated_by"] == ACTOR
    assert never == []


async def test_a_per_run_limit_with_no_monthly_limit_is_stored_and_is_not_yet_a_check(
    api: FastAPI,
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
) -> None:
    """The two limits are independent, and the per-run one is declared, not checked.

    **Both halves are asserted, because a gap that is only written down is a
    belief.** The route accepts a per-run limit alone and the row holds it; and
    ``check_spend_ceiling`` **allows**, because plan 02-04 built the monthly
    check only and said so at ``CeilingReason``: *"the per-run ceiling is also
    declared and also defaults off; whichever phase makes it a check adds its
    member here rather than reusing this one"*. If this test starts failing
    because the decision is now a refusal, somebody has made the per-run limit a
    check and this test and that note should be updated together.
    """
    await record_gateway_traffic(
        app_sessionmaker, migrate_engine, WORKSPACE_A, call_id="cal_per_run"
    )

    response = await call(
        api,
        "PUT",
        f"/api/v1/workspaces/{WORKSPACE_A}/spend-ceiling",
        json_body={
            "enabled": True,
            "per_run_limit": str(GATEWAY_COST / 2),
            "currency": "USD",
        },
    )

    assert response.status_code == 200, response.body
    assert response.json()["monthly_limit"] is None
    assert Decimal(response.json()["per_run_limit"]) == GATEWAY_COST / 2

    async with migrate_engine.begin() as connection:
        row = (await connection.execute(READ_CEILING_ROW, {"ws": WORKSPACE_A})).mappings().one()
    assert row["monthly_limit"] is None
    assert row["per_run_limit"] == GATEWAY_COST / 2

    assert (await check_spend_ceiling(app_sessionmaker, WORKSPACE_A, now=day(5))).allowed is True


async def test_a_limit_with_no_currency_is_refused(
    api: FastAPI, migrate_engine: AsyncEngine
) -> None:
    """A ceiling the seam could not evaluate is a ceiling that never refuses.

    ``check_spend_ceiling`` treats a limit whose currency is NULL as
    **unevaluable**: it fails open, allows, and increments
    ``prope_call_ledger_ceiling_check_total{result="failed_open"}`` — a counter
    with no scraper until plan 03-04 mounts ``/metrics``. So the route refuses to
    create one, at the only place a human can (A-104: an open-failing check
    nobody watches is an off switch).
    """
    response = await call(
        api,
        "PUT",
        f"/api/v1/workspaces/{WORKSPACE_A}/spend-ceiling",
        json_body={"enabled": True, "monthly_limit": "1.0"},
    )

    assert response.status_code == 422, response.body
    assert response.code == ErrorCode.SPEND_CEILING_LIMIT_NEEDS_CURRENCY.value

    async with migrate_engine.begin() as connection:
        assert (
            await connection.execute(READ_CEILING_ROW, {"ws": WORKSPACE_A})
        ).mappings().all() == []


async def test_a_negative_limit_is_refused(api: FastAPI, migrate_engine: AsyncEngine) -> None:
    """``ledger.spend_ceiling`` has no positivity CHECK, so this route is the guard.

    A negative limit refuses every eval run forever — recorded spend is never
    below zero — and says so nowhere.
    """
    response = await call(
        api,
        "PUT",
        f"/api/v1/workspaces/{WORKSPACE_A}/spend-ceiling",
        json_body={"enabled": True, "monthly_limit": "-1.0", "currency": "USD"},
    )

    assert response.status_code == 422, response.body
    assert response.code == ErrorCode.SPEND_CEILING_LIMIT_IS_NEGATIVE.value

    async with migrate_engine.begin() as connection:
        assert (
            await connection.execute(READ_CEILING_ROW, {"ws": WORKSPACE_A})
        ).mappings().all() == []


async def test_enabled_has_no_default_so_a_ceiling_cannot_be_set_unarmed(
    api: FastAPI,
) -> None:
    """Omitting ``enabled`` is a refusal, not a silently-off ceiling.

    A default of ``False`` would let ``{"monthly_limit": ..., "currency": ...}``
    return ``200`` and enforce nothing, which is the exact shape of a workspace
    losing the ceiling somebody set.
    """
    response = await call(
        api,
        "PUT",
        f"/api/v1/workspaces/{WORKSPACE_A}/spend-ceiling",
        json_body={"monthly_limit": "1.0", "currency": "USD"},
    )

    assert response.status_code == 422, response.body
    assert response.code == ErrorCode.VALIDATION_FAILED.value
