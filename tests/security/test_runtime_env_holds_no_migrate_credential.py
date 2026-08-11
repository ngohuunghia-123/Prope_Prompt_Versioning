"""T-001. The two long-running services hold `prope_app` and nothing stronger.

ADR-0037 splits the credentials three ways so that a compromised application
process cannot alter a schema, drop a policy, or read across tenants. That split
is worth exactly as much as the compose file honours it, and the compose file is
the one artifact where the wrong environment variable is a one-line edit nobody
reviews as a security change.

`prope_migrate` owns every table and is the only role that can drop an RLS
policy. `prope_report` carries `BYPASSRLS`, which is the whole tenant boundary
turned off. Either one reaching `app` or `worker` makes ADR-0035's *"a missing
filter returns zero rows"* a statement about a role the process is no longer
using.

**This test fails loudly if the compose file is absent.** A skip here is a
security control that silently stopped running.
"""

from pathlib import Path

import yaml

COMPOSE_FILE = Path(__file__).resolve().parents[2] / "docker-compose.yml"

#: The services that run for the lifetime of the deployment and serve traffic.
#: `migrate` is deliberately not here: it is `restart: "no"`, one-shot, and it is
#: the only place the migrate credential legitimately appears.
RUNTIME_SERVICES = ("app", "worker")

#: Role names, matched as substrings against every environment value. A
#: connection string is `postgresql+asyncpg://<role>:<password>@host/db`, so the
#: role name is present verbatim in any URL that uses it.
FORBIDDEN_ROLES = ("prope_migrate", "prope_report")

#: The password variables, matched separately. A service could be handed
#: `PROPE_MIGRATE_PASSWORD` without a connection string and would then be one
#: line away from building one.
FORBIDDEN_VARIABLES = ("PROPE_MIGRATE_PASSWORD", "PROPE_REPORT_PASSWORD")


def _compose() -> dict:
    assert COMPOSE_FILE.exists(), (
        f"{COMPOSE_FILE} is missing. This is T-001's control and it does not skip: a "
        "credential-separation test that quietly stops running is worse than one that "
        "was never written, because the green suite now asserts something it does not check."
    )
    return yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))


def _environment(service: dict) -> dict[str, str]:
    """Compose accepts a mapping or a `KEY=value` list; both are read."""
    declared = service.get("environment", {})
    if isinstance(declared, list):
        return dict(item.split("=", 1) for item in declared)
    return {key: str(value) for key, value in declared.items()}


def test_the_runtime_services_exist_so_this_is_not_vacuous() -> None:
    services = _compose()["services"]

    for name in RUNTIME_SERVICES:
        assert name in services, f"{name} is not in the compose file; the walk found nothing"


def test_no_runtime_service_receives_a_migrate_or_report_credential() -> None:
    services = _compose()["services"]

    offences: list[str] = []
    for name in RUNTIME_SERVICES:
        environment = _environment(services[name])
        for key, value in environment.items():
            for role in FORBIDDEN_ROLES:
                if role in value:
                    offences.append(f"{name}.{key} names {role}")
            if key in FORBIDDEN_VARIABLES:
                offences.append(f"{name}.{key} is set")

    assert offences == [], (
        f"{offences} — ADR-0037's credential split is only worth what this file honours. "
        "prope_migrate can drop an RLS policy; prope_report carries BYPASSRLS."
    )


def test_no_runtime_service_pulls_an_unexamined_env_file() -> None:
    """An `env_file` is a credential surface this test cannot read.

    ADR-0032 puts one `.env` on the VM at `0600`, git-ignored — so a service
    declaring `env_file` would be handed a set of variables that is, by
    construction, absent from the repository and therefore unassertable here.
    The `${VAR}` interpolation the services already use gives compose the same
    values from the same file while leaving the *names* visible in this file,
    which is what makes the assertion above possible.
    """
    services = _compose()["services"]

    for name in RUNTIME_SERVICES:
        assert "env_file" not in services[name], (
            f"{name} declares env_file; T-001 can no longer see what it is handed"
        )


def test_the_one_shot_migrate_service_is_the_only_holder() -> None:
    """The positive control. Without it the assertions above pass on an empty file.

    `restart: "no"` is asserted alongside, because a migrate container that keeps
    restarting is a migrate container that keeps re-running — and it is also the
    property that makes "one-shot" a true description of where the credential
    lives.
    """
    migrate = _compose()["services"]["migrate"]
    environment = _environment(migrate)

    assert "PROPE_MIGRATE_PASSWORD" in environment
    assert "PROPE_REPORT_PASSWORD" in environment
    assert migrate["restart"] == "no"


def test_the_lifespan_refuses_a_privileged_credential() -> None:
    """T-001's runtime half: the compose file is not the only way in.

    Somebody starting a container by hand, or a `docker run` in an incident, can
    hand this process any URL. A process that came up with the migrate credential
    would serve every request correctly — which is the problem, because there is
    no symptom until something goes wrong.
    """
    import pytest

    from prope.app import refuse_a_privileged_credential

    for role in ("prope_migrate", "prope_report"):
        with pytest.raises(RuntimeError, match=role):
            refuse_a_privileged_credential(
                f"postgresql+asyncpg://{role}:secret@postgres:5432/prope"
            )

    # The one it must accept, and a name that merely contains a forbidden one.
    refuse_a_privileged_credential("postgresql+asyncpg://prope_app:secret@postgres:5432/prope")
    refuse_a_privileged_credential(
        "postgresql+asyncpg://prope_app:secret@postgres:5432/prope_migrate_notes"
    )
