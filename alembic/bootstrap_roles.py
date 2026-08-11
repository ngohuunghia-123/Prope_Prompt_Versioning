"""The migrate service's second half: set the three role passwords.

Revision 0001 creates `prope_migrate`/`prope_app`/`prope_report` with no
password (D-05, ADR-0032) — the migration is not the place secrets belong.
This mirrors `tests/conftest.py`'s `_set_test_role_passwords` exactly, run
once per environment instead of once per test session: connect as the
superuser `alembic upgrade head` just used (`PROPE_DATABASE_URL` in the
`migrate` service), then `ALTER ROLE ... WITH PASSWORD` from the three
`PROPE_*_PASSWORD` variables `.env` carries for the `app`/`worker` roles to
connect with afterward.
"""

import asyncio
import os

from sqlalchemy import text
from sqlalchemy.pool import NullPool

from prope.db.engine import build_engine

ROLE_PASSWORD_ENV_VARS = {
    "prope_migrate": "PROPE_MIGRATE_PASSWORD",
    "prope_app": "PROPE_APP_PASSWORD",
    "prope_report": "PROPE_REPORT_PASSWORD",
}


def _escaped(password: str) -> str:
    return password.replace("'", "''")


async def _set_role_passwords(superuser_url: str, passwords: dict[str, str]) -> None:
    engine = build_engine(superuser_url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            for role, password in passwords.items():
                await connection.execute(
                    text(f"ALTER ROLE {role} WITH PASSWORD '{_escaped(password)}'")
                )
    finally:
        await engine.dispose()


def main() -> None:
    superuser_url = os.environ["PROPE_DATABASE_URL"]
    passwords = {}
    for role, env_var in ROLE_PASSWORD_ENV_VARS.items():
        password = os.environ.get(env_var)
        if not password:
            raise RuntimeError(f"{env_var} is required to bootstrap the {role} role's password")
        passwords[role] = password

    asyncio.run(_set_role_passwords(superuser_url, passwords))


if __name__ == "__main__":
    main()
