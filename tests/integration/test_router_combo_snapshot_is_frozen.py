"""ADR-0069 — a combo is a template, and what a revision copies from it is frozen.

This is the decision the whole feature is organised around, and it has two
justifications that pull in the same direction.

**A-024.** Provider and model are part of the revision, so the approval record
describes what can run. A live reference would mean a Settings dialog could
change what an approved revision does, and the approval chain becomes decorative
— the exact failure BR-02 exists to prevent.

**ADR-0012's cache, which is the stronger one.** The gateway's resolution cache
has a 30 s TTL and *nothing invalidates it*; broker-based invalidation was
proposed twice and rejected twice on merit. Under a live reference, an edit here
would be a production change the cache cannot see and cannot be told about, and
the same prompt would route two ways depending on which process answered. Under
a snapshot the cached value is immutable **by privilege** —
`revision_route_entry` holds `SELECT, INSERT` and never `UPDATE` or `DELETE` —
so a stale cache entry is not merely tolerable, it is correct.

Everything below is driven through the real routes, because the claim is about
what a *save* does.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.errors import ErrorCode
from tests.access_control import (
    seed_member,
    seed_role,
    seed_session,
    seed_user,
    seed_workspace,
)
from tests.integration._asgi import call
from tests.prompt_registry import PROMPT_ID, registry_api, seed_prompt
from tests.provider_access import (
    CONFIG_ID,
    CREDENTIAL_ID,
    seed_credential,
    seed_provider_config,
)

SESSION_ID = "ses_registry_router_00000001"

BACKUP_CONFIG_ID = "prv_01J000000000000000PROV2"

#: Derived from the shipped one so the two cannot silently become the same id.
#: `ck_credential_id_prefix` also refuses anything that is not `crd_`-shaped.
BACKUP_CREDENTIAL_ID = f"{CREDENTIAL_ID[:-1]}2"

OPEN, CLOSE = "<system>", "</system>"

READ_ROUTE = text(
    """
    SELECT priority, provider_config_id, upstream_model, route_combo_id
    FROM   registry.revision_route_entry
    WHERE  version_id = :version_id
    ORDER  BY priority
    """
)

READ_REVISION_BINDING = text(
    """
    SELECT provider_config_id, upstream_model, route_combo_id, route_combo_name
    FROM   registry.revision
    WHERE  version_id = :version_id
    """
)


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with registry_api(app_sessionmaker) as application:
        yield application


def _author() -> dict[str, str]:
    return {"cookie": f"prope_session={SESSION_ID}"}


async def _workspace_with_two_providers(migrate_engine) -> None:  # noqa: ANN001
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    # BOTH roles on one person, because ADR-0069 put combo CRUD behind
    # `provider.configure` and that is an **Admin** permission, while
    # `revision.create` is an **Owner** one. `pk_role_binding` is
    # `(workspace_id, user_id, role)`, so holding both is a legal state and not
    # a test-only fiction.
    #
    # It is also the honest shape of the split: a workspace's providers are
    # administered, combos over those providers are administered too, and a
    # prompt owner SELECTS one — `catalogue.read`, which Owner holds — rather
    # than defining it. Somebody who does both jobs holds both roles.
    await seed_role(migrate_engine, "Owner")
    await seed_role(migrate_engine, "Admin")
    await seed_session(migrate_engine, SESSION_ID)
    await seed_provider_config(migrate_engine)
    await seed_credential(migrate_engine)
    await seed_provider_config(migrate_engine, BACKUP_CONFIG_ID, credential_id=BACKUP_CREDENTIAL_ID)
    await seed_credential(
        migrate_engine, credential_id=BACKUP_CREDENTIAL_ID, provider_config_id=BACKUP_CONFIG_ID
    )
    await seed_prompt(migrate_engine)


def _combo(**overrides) -> dict:
    return {
        "display_name": "Primary and backup",
        "description": "",
        "entries": [
            {"provider_config_id": CONFIG_ID, "upstream_model": "gpt-4o-mini"},
            {"provider_config_id": BACKUP_CONFIG_ID, "upstream_model": "gpt-4o"},
        ],
        **overrides,
    }


async def _create_combo(api, **overrides) -> dict:  # noqa: ANN001
    response = await call(
        api, "POST", "/api/v1/router-combos", json_body=_combo(**overrides), headers=_author()
    )
    assert response.status_code == 201, response.body
    return response.json()


async def _create_revision(api, **body) -> dict:  # noqa: ANN001
    response = await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/revisions",
        json_body={"body": f"{OPEN}be helpful{CLOSE}", "change_summary": "bind a route", **body},
        headers=_author(),
    )
    return response


async def _route_of(migrate_engine, version_id: str) -> list[tuple]:  # noqa: ANN001
    async with migrate_engine.begin() as connection:
        rows = await connection.execute(READ_ROUTE, {"version_id": version_id})
        return [tuple(row) for row in rows.all()]


async def test_naming_a_combo_copies_its_entries_onto_the_revision(
    api, migrate_engine
) -> None:
    """The client names the TEMPLATE; the server copies it.

    There is deliberately no `route` field on the request. Accepting a
    client-built list would make *"which combo was this"* a claim rather than a
    fact, and would let a caller compose a route no combo in Settings ever
    contained.
    """
    await _workspace_with_two_providers(migrate_engine)
    combo = await _create_combo(api)

    created = await _create_revision(api, router_combo_id=combo["combo_id"])

    assert created.status_code == 201, created.body
    body = created.json()
    assert body["route_combo_id"] == combo["combo_id"]
    assert body["route_combo_name"] == "Primary and backup"
    assert [entry["priority"] for entry in body["route"]] == [1, 2]
    assert body["route"][0]["provider_config_id"] == CONFIG_ID
    assert body["route"][1]["upstream_model"] == "gpt-4o"
    # A route and a pair are mutually exclusive, and the pair columns are the
    # half that stays NULL — which is what keeps `ck_revision_binding_is_whole`
    # meaning exactly what it always meant.
    assert body["provider_config_id"] is None
    assert body["upstream_model"] is None


async def test_editing_the_template_afterwards_changes_nothing_already_written(
    api, migrate_engine
) -> None:
    """The claim the settings dialog makes, asserted against the rows.

    Adopting an edit takes a new revision and a new approval. That is not a
    limitation somebody worked around — it is the product: a route reaching
    production without a human approval is the one thing Prope exists to make
    impossible.
    """
    await _workspace_with_two_providers(migrate_engine)
    combo = await _create_combo(api)
    created = await _create_revision(api, router_combo_id=combo["combo_id"])
    version_id = created.json()["version_id"]

    before = await _route_of(migrate_engine, version_id)

    replaced = await call(
        api,
        "PUT",
        f"/api/v1/router-combos/{combo['combo_id']}",
        json_body=_combo(
            display_name="Renamed entirely",
            # Reversed, so the edit changes the ORDER as well as the name —
            # order is the whole meaning of a route, and a snapshot that
            # followed a reorder would be the worst version of this bug: the
            # rungs would all still be there, and the wrong one would answer.
            entries=[
                {"provider_config_id": BACKUP_CONFIG_ID, "upstream_model": "gpt-4o"},
                {"provider_config_id": CONFIG_ID, "upstream_model": "gpt-4o-mini"},
            ],
        ),
        headers=_author(),
    )

    assert replaced.status_code == 200, replaced.body
    assert await _route_of(migrate_engine, version_id) == before

    async with migrate_engine.begin() as connection:
        row = (
            await connection.execute(READ_REVISION_BINDING, {"version_id": version_id})
        ).one()

    # The NAME is snapshotted too, so a review screen still reads correctly
    # after a rename rather than showing whatever the template is called today.
    assert row.route_combo_name == "Primary and backup"


async def test_deleting_the_template_leaves_the_revision_intact(
    api, migrate_engine
) -> None:
    """`route_combo_id` on the revision is a VALUE with no foreign key.

    ADR-0054's rule for `actor_id`, applied to a second thing that has to
    outlive its referent: a workspace tidying up its combos must never be able
    to break a released prompt.
    """
    await _workspace_with_two_providers(migrate_engine)
    combo = await _create_combo(api)
    created = await _create_revision(api, router_combo_id=combo["combo_id"])
    version_id = created.json()["version_id"]
    before = await _route_of(migrate_engine, version_id)

    deleted = await call(
        api, "DELETE", f"/api/v1/router-combos/{combo['combo_id']}", headers=_author()
    )

    assert deleted.status_code == 204, deleted.body
    assert await _route_of(migrate_engine, version_id) == before

    readable = await call(api, "GET", f"/api/v1/revisions/{version_id}", headers=_author())
    assert readable.status_code == 200
    assert len(readable.json()["route"]) == 2


async def test_a_pair_and_a_combo_together_are_refused(api, migrate_engine) -> None:
    """`ck_revision_binds_a_pair_or_a_route_never_both`, surfaced as a 422.

    Refused by the schema before it reaches the database, so the message names
    the fields somebody sent rather than a constraint they have never heard of —
    and refused by the database underneath either way.
    """
    await _workspace_with_two_providers(migrate_engine)
    combo = await _create_combo(api)

    response = await _create_revision(
        api,
        router_combo_id=combo["combo_id"],
        provider_config_id=CONFIG_ID,
        upstream_model="gpt-4o-mini",
    )

    assert response.status_code == 422, response.body


async def test_an_unknown_combo_is_not_found_and_leaves_no_revision_behind(
    api, migrate_engine
) -> None:
    """The savepoint held, and the 404 is the same answer another tenant's combo gets.

    Two claims in one test. The refusal comes from the engine —
    `INSERT_REVISION`'s `LEFT JOIN` yields a NULL name, which trips
    `ck_revision_route_provenance_is_whole` — so there is no extra read and RLS
    makes "another workspace's combo" and "no such combo" byte-identical.

    And the revision must not survive: `create_revision` writes inside
    `db.begin_nested()`, which is also why the "routed marker with zero entries"
    check is a rowcount rather than a deferred constraint trigger. A deferred
    constraint fires at COMMIT — outside the savepoint — and would poison the
    whole request transaction instead of one attempt.
    """
    await _workspace_with_two_providers(migrate_engine)

    response = await _create_revision(api, router_combo_id="rtc_01J0000000000000000NONE")

    assert response.status_code == 404, response.body
    assert response.code == ErrorCode.REGISTRY_UNKNOWN_ROUTER_COMBO

    async with migrate_engine.begin() as connection:
        remaining = await connection.scalar(
            text("SELECT count(*) FROM registry.revision WHERE prompt_id = :prompt_id"),
            {"prompt_id": PROMPT_ID},
        )

    assert remaining == 0, "a failed route copy left a revision behind"


async def test_a_one_entry_combo_is_refused_before_it_can_be_saved(
    api, migrate_engine
) -> None:
    """Two rungs minimum, because a one-rung combo is today's single binding
    wearing a new name — and a name a reviewer has to open a second screen to
    read."""
    await _workspace_with_two_providers(migrate_engine)

    response = await call(
        api,
        "POST",
        "/api/v1/router-combos",
        json_body=_combo(entries=[{"provider_config_id": CONFIG_ID, "upstream_model": "gpt-4o-mini"}]),
        headers=_author(),
    )

    assert response.status_code == 422, response.body


async def test_the_same_provider_and_model_twice_is_refused(api, migrate_engine) -> None:
    """`uq_router_combo_entry_target`, as a message about the list somebody typed.

    The same provider with a DIFFERENT model is not a duplicate and is not
    refused — a cheaper model on a key that already works is one of the two
    things this feature is for.
    """
    await _workspace_with_two_providers(migrate_engine)

    duplicate = await call(
        api,
        "POST",
        "/api/v1/router-combos",
        json_body=_combo(
            entries=[
                {"provider_config_id": CONFIG_ID, "upstream_model": "gpt-4o-mini"},
                {"provider_config_id": CONFIG_ID, "upstream_model": "gpt-4o-mini"},
            ]
        ),
        headers=_author(),
    )

    cheaper_second_model = await call(
        api,
        "POST",
        "/api/v1/router-combos",
        json_body=_combo(
            display_name="Same key, cheaper model",
            entries=[
                {"provider_config_id": CONFIG_ID, "upstream_model": "gpt-4o"},
                {"provider_config_id": CONFIG_ID, "upstream_model": "gpt-4o-mini"},
            ],
        ),
        headers=_author(),
    )

    assert duplicate.status_code == 422, duplicate.body
    assert cheaper_second_model.status_code == 201, cheaper_second_model.body


async def test_the_list_reports_how_many_revisions_copied_a_combo(
    api, migrate_engine
) -> None:
    """`revision_count` blocks nothing and is not meant to.

    It is what lets the edit dialog say *"editing this changes nothing already
    released"* and be believed, and what lets the delete confirmation say how
    much is standing on its own frozen copy.
    """
    await _workspace_with_two_providers(migrate_engine)
    combo = await _create_combo(api)

    empty = await call(api, "GET", "/api/v1/router-combos", headers=_author())
    assert [row["revision_count"] for row in empty.json()] == [0]

    await _create_revision(api, router_combo_id=combo["combo_id"])

    listed = await call(api, "GET", "/api/v1/router-combos", headers=_author())
    assert listed.status_code == 200, listed.body
    assert [row["revision_count"] for row in listed.json()] == [1]
