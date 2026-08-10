"""Reusable DDL emitters — the guarantee carriers every revision calls.

RESEARCH Pattern 10 recommends one revision per *kind* of guarantee (tables /
RLS / grants) so a reviewer can grep the diff for each one. This phase instead
puts one table's whole guarantee stack in one revision, because a tracer has to
prove the stack end to end in a single applied migration. Per-kind
greppability survives here rather than in the chain: every tenant policy in the
project is an :func:`enable_tenant_rls` call and every grant line is a
:func:`grant_table` call, so a reviewer greps the helper name.

Identifiers interpolated below are module constants and revision-supplied
schema/table names — never runtime values. The one place a runtime value
reaches SQL is the tenant identifier in ``prope.db.session``, and that one is
bound as a parameter.
"""

from alembic import op

MIGRATION_ROLE = "prope_migrate"
APP_ROLE = "prope_app"
REPORT_ROLE = "prope_report"

#: The session variable the tenant policy reads. ADR-0035.
TENANT_GUC = "app.workspace_id"


def assume_migrate_role(role: str = MIGRATION_ROLE) -> None:
    """Own everything this revision creates as ``prope_migrate``.

    ADR-0035's owner bypass is what keeps the migration role exempt from the
    tenant policy — "prope_migrate owns every table and prope_app owns none, so
    the runtime role is subject to policy and the migration role is not, with
    no additional grant machinery". That only holds if ``prope_migrate``
    actually owns the tables, so every revision from 0002 onward opens with
    this call.

    Transaction-local. Pair it with :func:`reset_role` before the revision
    ends, or Alembic's own write to ``public.alembic_version`` is attempted as
    ``prope_migrate``, which holds no privilege there.
    """
    op.execute(f"SET LOCAL ROLE {role}")


def reset_role() -> None:
    """Hand the connection back to the role Alembic connected as."""
    op.execute("RESET ROLE")


def enable_tenant_rls(
    schema: str,
    table: str,
    *,
    role: str = APP_ROLE,
    column: str = "workspace_id",
) -> None:
    """ADR-0035 / ADR-0045: the deny-by-default tenant policy for one table.

    Three tokens here are load-bearing and none is stylistic:

    ``ENABLE``, never ``FORCE``
        ``FORCE ROW LEVEL SECURITY`` would subject the table's owner —
        ``prope_migrate`` — to the policy, breaking every migration, backfill
        and test-rig setup path. ADR-0035 depends on the owner bypass.

    ``current_setting(..., true)`` — two arguments
        The one-argument form *raises* ``unrecognized configuration
        parameter`` on a connection where the variable was never set. The
        two-argument form returns NULL, the predicate is then NULL rather than
        true, and a missing filter yields zero rows. That inversion is the
        whole of ADR-0035; the second argument is what buys it.

    no cast (OQ-A, decided ``text-no-cast``)
        ADR-0035:43 and ADR-0045:89-90 write the predicate as
        ``... = current_setting('app.workspace_id')::uuid``. A workspace id is
        a ``wsp_``-prefixed ULID (ADR-0003, access-control.lock.yml:208), not a
        UUID, so the cast would raise where zero rows are required. Text on
        both sides; ``access.list_workspaces() RETURNS SETOF text``
        (ADR-0051:48) is the decisive evidence. The ADR wording is carried
        upstream for correction, not patched here.

    ``WITH CHECK`` written out
        It defaults to the ``USING`` expression, but ADR-0040 makes it the
        load-bearing half: a call record's ``workspace_id`` is denormalised by
        its caller, and a mis-stamped one is this module's realistic
        cross-tenant leak. Written out so it cannot be dropped by accident.
    """
    predicate = f"{column} = current_setting('{TENANT_GUC}', true)"
    op.execute(f"ALTER TABLE {schema}.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_tenant ON {schema}.{table} "
        f"FOR ALL TO {role} "
        f"USING ({predicate}) "
        f"WITH CHECK ({predicate})"
    )


def grant_table(
    schema: str,
    table: str,
    *,
    app_privileges: list[str],
    app_role: str = APP_ROLE,
    report_select: bool = True,
) -> None:
    """The grant matrix for one table (D-07, ADR-0037, T-006).

    ``REVOKE ALL ... FROM PUBLIC`` is the baseline, then exactly the named
    privileges to the runtime role. Granting only what is needed is preferred
    over ``GRANT ALL`` followed by a ``REVOKE``: both end in the same state and
    the positive form is the one a reviewer can read.

    ``prope_report`` gets ``SELECT`` in the same revision as the table.
    ADR-0037 already records that this is a full-read credential and that
    ADR-0036's restore rehearsal checks the role exists in the target cluster —
    which only bites if the grants exist, so role and grants ship together.

    There is deliberately no ``ALTER DEFAULT PRIVILEGES``. A future table
    should arrive with no privileges until somebody writes them.
    """
    op.execute(f"REVOKE ALL ON {schema}.{table} FROM PUBLIC")
    op.execute(f"GRANT {', '.join(app_privileges)} ON {schema}.{table} TO {app_role}")
    if report_select:
        op.execute(f"GRANT SELECT ON {schema}.{table} TO {REPORT_ROLE}")
