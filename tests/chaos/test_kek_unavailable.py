"""AC-12 — a missing KEK is Prope's outage and must never read as a provider's.

The two look identical from outside: every call fails and the gateway serves
fallback answers. They are repaired completely differently, so the distinction is
carried by three separate things — a distinct gauge, a distinct error class with
`origin = prope`, and readiness withheld so an orchestrator does not route
traffic to a process that cannot serve any of it.
"""

import pytest
from prometheus_client import REGISTRY
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.app import create_app
from prope.provider_access import crypto
from prope.provider_access.dispatch import dispatch
from prope.provider_access.domain import DispatchError, ErrorClass, Origin
from prope.provider_access.failures import CLASSIFICATION
from tests.integration._asgi import call
from tests.provider_access import CONFIG_ID, seed_provider_config
from tests.unit import WORKSPACE_A


@pytest.fixture
def no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """The realistic trigger (A-135): a deploy that lost or truncated `.env`."""
    monkeypatch.delenv("PROPE_KEK_V1", raising=False)


def _gauge() -> float:
    value = REGISTRY.get_sample_value("prope_provider_access_kek_unavailable")
    return 0.0 if value is None else value


async def test_readiness_is_withheld_and_the_gauge_reads_one(
    app_engine, app_sessionmaker, no_key
) -> None:
    application = create_app()
    application.state.engine = app_engine
    application.state.sessionmaker = app_sessionmaker

    response = await call(application, "GET", "/readyz")

    assert response.status_code == 503
    assert response.json()["failed_check"] == "kek"
    assert _gauge() == 1.0


async def test_readiness_returns_when_the_key_returns(app_engine, app_sessionmaker) -> None:
    """It is a state and not an event, so recovery is observable without a
    restart — which is what makes the page actionable."""
    application = create_app()
    application.state.engine = app_engine
    application.state.sessionmaker = app_sessionmaker

    response = await call(application, "GET", "/readyz")

    assert response.status_code == 200
    assert response.json()["checks"] == ["database", "kek"]
    assert _gauge() == 0.0


async def test_a_dispatch_fails_with_a_class_no_provider_can_produce(
    migrate_engine, app_sessionmaker: async_sessionmaker[AsyncSession], no_key
) -> None:
    await seed_provider_config(migrate_engine)

    result = await dispatch(
        app_sessionmaker,
        workspace_id=WORKSPACE_A,
        provider_config_id=CONFIG_ID,
        upstream_model="gpt-4o-mini",
        parameters={},
        messages=({"role": "user", "content": "hi"},),
    )

    assert isinstance(result, DispatchError)
    assert result.error_class is ErrorClass.KEY_UNAVAILABLE
    assert result.origin is Origin.PROPE
    assert result.upstream_status is None


async def test_the_key_unavailable_class_is_neither_fallback_eligible_nor_retryable() -> None:
    """A fallback answer here would cover a total outage of the product with a
    canned string, and a retry would re-read an environment that has not
    changed."""
    facts = CLASSIFICATION[ErrorClass.KEY_UNAVAILABLE]

    assert facts.origin is Origin.PROPE
    assert facts.fallback_eligible is False
    assert facts.retryable is False


async def test_no_provider_origin_class_shares_the_key_unavailable_shape() -> None:
    """The distinction the whole failure mode rests on: nothing a provider does
    can be reported with `origin = prope`."""
    provider_classes = {
        error_class
        for error_class, facts in CLASSIFICATION.items()
        if facts.origin is Origin.PROVIDER
    }

    assert ErrorClass.KEY_UNAVAILABLE not in provider_classes
    assert ErrorClass.UPSTREAM_UNAVAILABLE in provider_classes


async def test_no_dispatch_log_line_blames_the_provider(
    migrate_engine, app_sessionmaker, no_key, caplog
) -> None:
    """"Reporting it as unreadiness would take the gateway down with it" is the
    other half of this; this half is that nobody reading the logs starts by
    calling the provider."""
    await seed_provider_config(migrate_engine)

    with caplog.at_level("WARNING"):
        await dispatch(
            app_sessionmaker,
            workspace_id=WORKSPACE_A,
            provider_config_id=CONFIG_ID,
            upstream_model="gpt-4o-mini",
            parameters={},
            messages=({"role": "user", "content": "hi"},),
        )

    written = " ".join(record.getMessage() for record in caplog.records)

    assert "upstream_unavailable" not in written
    assert "provider.example" not in written


async def test_a_stored_credential_cannot_be_decrypted_without_the_key(
    migrate_engine, no_key
) -> None:
    """AC-2's other direction, reached through the same failure: the row is
    intact and unreadable, which is the state a stolen dump leaves an attacker
    in permanently."""
    await seed_provider_config(migrate_engine)

    with pytest.raises(crypto.KeyUnavailable):
        crypto.highest_kek_version()
