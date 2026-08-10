"""The one shared MetaData, and the naming convention 23 later phases inherit.

Two decisions are encoded here and both are easy to get wrong once.

**No default schema.** A single ``MetaData(schema="ledger")`` shared by all
eight modules would silently put the next module's tables in ``ledger``; eight
independent ``MetaData`` objects would make Alembic's single linear chain
awkward to point at. One shared object with no default, and each module's
tables declaring ``{"schema": "<module>"}`` explicitly, is the shape that
survives eight modules.

**A naming convention.** Without one, PostgreSQL names constraints itself and
``op.drop_constraint`` needs names nobody can predict. With one, every
constraint name is deterministic, so a security test can assert *which*
constraint refused a write rather than only that something did.

These tables are for the application to query. They are never the source of
truth for DDL — the migration is (D-04, A-128).
"""

from sqlalchemy import MetaData

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)
