"""INT-016 is **soft**: an unreadable model catalogue must not stop an author saving.

The registry reads provider-access's catalogue when a revision names an upstream
model, and that read is advisory. The catalogue is a **cache of somebody else's
API** — it is empty on a configuration that has never refreshed, stale on one
whose last refresh failed, and wrong for the minutes between a provider adding a
model and the next refresh. Every one of those states is normal.

**What refusing would cost.** The prompt body is the asset this product exists to
protect, and the author has it in a browser tab. A save refused because a cache
of a third party's model list did not mention a name makes the outage of that
third party into data loss here — for a check that could not have been trusted
anyway, since the catalogue can be wrong in both directions.

**What is not soft**, and the line this file draws: ``provider_config_id`` is a
real foreign key into ``provider.provider_config``. An unknown configuration is
refused with a ``422``, because that is a fact about this database rather than a
cached opinion about somebody else's. The distinction is the whole of INT-016 —
one column is checked by the engine and the other is checked by a log line.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.access_control import (
    seed_member,
    seed_role,
    seed_session,
    seed_user,
    seed_workspace,
)
from tests.integration._asgi import call
from tests.prompt_registry import PROMPT_ID, registry_api, seed_prompt, seed_revision
from tests.provider_access import CONFIG_ID, seed_catalogue_entry, seed_credential, seed_provider_config

SESSION_ID = "ses_registry_chaos_0000000001"

BINDING = {"provider_config_id": CONFIG_ID, "upstream_model": "gpt-4o-mini"}

EMPTY_THE_CATALOGUE = text("DELETE FROM provider.model_catalogue")

READ_BINDING = text(
    "SELECT provider_config_id, upstream_model FROM registry.revision WHERE version_id = :id"
)


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with registry_api(app_sessionmaker) as application:
        yield application


def _author() -> dict[str, str]:
    return {"cookie": f"prope_session={SESSION_ID}"}


async def _workspace(migrate_engine) -> None:  # noqa: ANN001
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)
    await seed_member(migrate_engine)
    await seed_role(migrate_engine, "Owner")
    await seed_session(migrate_engine, SESSION_ID)
    await seed_prompt(migrate_engine)
    await seed_provider_config(migrate_engine)
    await seed_credential(migrate_engine)


async def _save(api, **binding) -> object:  # noqa: ANN001, ANN003
    return await call(
        api,
        "POST",
        f"/api/v1/prompts/{PROMPT_ID}/revisions",
        json_body={"body": "You are a helpful assistant.", "change_summary": "bind", **binding},
        headers=_author(),
    )


async def test_a_revision_saves_when_the_catalogue_is_empty(api, migrate_engine) -> None:
    """The refresh never ran, or it failed. The author still saves.

    An empty catalogue is indistinguishable from a broken one, which is why the
    check does not run at all when there is nothing in it: treating *"I know of
    no models"* as *"that model does not exist"* would refuse every save against
    a configuration whose first refresh had not completed.
    """
    await _workspace(migrate_engine)

    response = await _save(api, **BINDING)

    assert response.status_code == 201, response.body

    payload = response.json()
    assert payload["provider_config_id"] == CONFIG_ID
    assert payload["upstream_model"] == "gpt-4o-mini"


async def test_a_revision_saves_when_the_catalogue_disagrees(api, migrate_engine) -> None:
    """The catalogue is populated and does **not** list the model. Still a 201.

    This is the case a hard check would refuse, and it is the one that happens on
    the day a provider ships a model before the next refresh picks it up. The
    binding is written verbatim, so the gateway resolves the name the author
    typed rather than one the registry substituted.
    """
    await _workspace(migrate_engine)
    await seed_catalogue_entry(migrate_engine, model_id="some-other-model")

    response = await _save(api, **BINDING)

    assert response.status_code == 201, response.body

    async with migrate_engine.begin() as connection:
        row = (
            await connection.execute(READ_BINDING, {"id": response.json()["version_id"]})
        ).one()

    assert row == (CONFIG_ID, "gpt-4o-mini")


async def test_a_revision_saves_when_the_catalogue_goes_away_between_saves(
    api, migrate_engine
) -> None:
    """A catalogue that was readable and is not any more — the actual degradation.

    A binding that validated yesterday must not become unsaveable today because
    a refresh emptied the cache. The second save is byte-identical to the first
    except for the state of somebody else's table.
    """
    await _workspace(migrate_engine)
    await seed_catalogue_entry(migrate_engine, model_id="gpt-4o-mini")

    first = await _save(api, **BINDING)
    assert first.status_code == 201, first.body

    async with migrate_engine.begin() as connection:
        await connection.execute(EMPTY_THE_CATALOGUE)

    second = await _save(api, **BINDING)

    assert second.status_code == 201, second.body
    assert second.json()["revision_number"] == 2


async def test_an_unknown_provider_configuration_is_still_refused(api, migrate_engine) -> None:
    """The hard half. This is a foreign key, not a cache, and it says 422.

    Stated beside the soft cases deliberately: without it, *"the catalogue is
    advisory"* would be indistinguishable from *"nothing about the binding is
    checked"*, and a typo in a configuration id would be stored and only
    discovered at the first production call.
    """
    await _workspace(migrate_engine)

    response = await _save(
        api, provider_config_id="prv_01J00000000000000NOSUCH", upstream_model="gpt-4o-mini"
    )

    assert response.status_code == 422, response.body
    assert response.code == "registry_unknown_provider_config"


async def test_the_catalogue_is_never_read_when_no_model_is_named(api, migrate_engine) -> None:
    """A revision with no binding at all, which is what every first draft is.

    The catalogue read is skipped rather than made to succeed on nulls: a prompt
    that has not chosen a provider yet is the normal state during authoring, and
    ``ck_revision_binding_is_whole`` is what makes the pair all-or-nothing.
    """
    await _workspace(migrate_engine)

    response = await _save(api)

    assert response.status_code == 201, response.body
    assert response.json()["provider_config_id"] is None
    assert response.json()["upstream_model"] is None


async def test_half_a_binding_is_refused_at_the_edge_and_not_called_a_conflict(
    api, migrate_engine
) -> None:
    """``ck_revision_binding_is_whole``, met as a 422 rather than as a lie.

    An upstream model with no provider configuration would resolve to whichever
    provider the next piece of code happened to pick — the implicit default that
    makes a released revision untraceable — so it is refused.

    **The second half of the name is the part that was wrong.** The write path
    retries a revision-number collision once and used to treat *any* integrity
    violation as that collision, so this request came back as ``409 somebody
    else saved a revision of this prompt first``: a message about a race that did
    not happen, unactionable by the author, and counted in
    ``revision_conflict_total`` as contention. The retry loop now branches on
    ``uq_revision_prompt_id`` by name and re-raises everything else.
    """
    await _workspace(migrate_engine)

    response = await _save(api, upstream_model="gpt-4o-mini")

    assert response.status_code == 422, response.body
    assert response.code != "registry_revision_conflict"


async def test_the_check_constraint_is_the_backstop_underneath_that(migrate_engine) -> None:
    """The edge refusal is a message; the CHECK is the guarantee.

    Written directly as the owner, past every schema and every handler, because
    the claim is that the pair is all-or-nothing in the database and not only in
    pydantic — a future write path that skipped ``RevisionCreate`` would still be
    unable to store half a binding.
    """
    await _workspace(migrate_engine)

    with pytest.raises(IntegrityError, match="ck_revision_binding_is_whole"):
        await seed_revision(migrate_engine, upstream_model="gpt-4o-mini")
