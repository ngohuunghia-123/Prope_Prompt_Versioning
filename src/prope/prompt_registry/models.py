"""The `registry` tables as Core `Table` objects. Not the source of truth.

``prompt_property.released_revision_status`` is deliberately absent. It is a
STORED generated column that exists only to carry BR-03's half of
``fk_prompt_property_released_version_id``, and a column no statement may ever
name is one the application should not be able to name.

The four Usage Profile axes (revision 0030, ADR-0067) appear on BOTH tables, and
the duplication is D-02 rather than a copy-paste: the property's copy is what
somebody edits and the revision's is the snapshot a reviewer approved under. A
profile living only on the property would silently re-scope every past approval
when somebody flipped `internal` to `public`.

``revision_route_entry`` is a frozen copy of ``router_combo_entry`` and the
duplication is ADR-0069's decision, not an oversight: a combo is a template, and
a revision keeps its own copy so that editing the template changes nothing
already released. Neither table is reachable from the other here, because at the
one moment they touch — the copy, in ``commands.create_revision`` — the statement
is a single ``INSERT ... SELECT`` and there is no ORM relationship to traverse.

``folder`` carries no foreign key to ``prompt_property`` and none the other way.
The join between them is ``folder.slug = prompt_property.namespace``, written out
at the one site that needs it (``repository.list_folders``) rather than declared
here, because it is an outer join in both directions: a folder may hold no
prompts and a prompt may sit in a namespace nobody has named.
"""

from sqlalchemy import Column, DateTime, Integer, Table, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from prope.db.metadata import metadata

TIMESTAMPTZ = DateTime(timezone=True)

SCHEMA = "registry"

prompt_property = Table(
    "prompt_property",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("namespace", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("purpose", Text, nullable=False),
    Column("owner_id", Text, nullable=False),
    Column("access_level", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("tags", ARRAY(Text), nullable=False),
    Column("released_version_id", Text),
    Column("released_at", TIMESTAMPTZ),
    Column("search_text", Text, nullable=False),
    Column("audience", Text, nullable=False),
    Column("untrusted_input", Text, nullable=False),
    Column("acts", Text, nullable=False),
    Column("sensitivity", Text, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    Column("updated_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)

revision = Table(
    "revision",
    metadata,
    Column("version_id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("prompt_id", Text, nullable=False),
    Column("revision_number", Integer, nullable=False),
    Column("body", Text, nullable=False),
    Column("original_body", Text, nullable=False),
    Column("original_format", Text, nullable=False),
    Column("original_filename", Text),
    Column("conversion_model", Text),
    Column("conversion_schema_version", Text),
    Column("provider_config_id", Text),
    Column("upstream_model", Text),
    Column("route_combo_id", Text),
    Column("route_combo_name", Text),
    Column("parameters", JSONB, nullable=False),
    Column("fallback_answer", Text),
    Column("change_summary", Text, nullable=False),
    Column("tags", ARRAY(Text), nullable=False),
    Column("author_id", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("audience", Text, nullable=False),
    Column("untrusted_input", Text, nullable=False),
    Column("acts", Text, nullable=False),
    Column("sensitivity", Text, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)

folder = Table(
    "folder",
    metadata,
    Column("workspace_id", Text, primary_key=True),
    Column("slug", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("color", Text, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    Column("updated_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)

call_annotation = Table(
    "call_annotation",
    metadata,
    Column("workspace_id", Text, primary_key=True),
    Column("call_id", Text, primary_key=True),
    Column("prompt_id", Text, nullable=False),
    Column("verdict", Text, nullable=False),
    Column("categories", ARRAY(Text), nullable=False),
    Column("correction", Text, nullable=False),
    Column("note", Text, nullable=False),
    Column("annotated_by", Text, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    Column("updated_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)


router_combo = Table(
    "router_combo",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("display_name", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("created_by", Text, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    Column("updated_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)

#: The editable template's rungs. No surrogate id: `(combo_id, priority)` is the
#: key, the way `folder` and `call_annotation` above use composite keys, and
#: `priority` is the list index the client sent plus one rather than a number the
#: client chose — see `schemas.RouterComboWrite`.
router_combo_entry = Table(
    "router_combo_entry",
    metadata,
    Column("combo_id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("priority", Integer, primary_key=True),
    Column("provider_config_id", Text, nullable=False),
    Column("upstream_model", Text, nullable=False),
    schema=SCHEMA,
)

#: The frozen copy one revision keeps (ADR-0069). `route_combo_id` is repeated
#: here rather than being reachable through `version_id` alone, because it is
#: half of the composite foreign key that makes an entry impossible on a revision
#: which does not declare a route.
revision_route_entry = Table(
    "revision_route_entry",
    metadata,
    Column("version_id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    Column("route_combo_id", Text, nullable=False),
    Column("priority", Integer, primary_key=True),
    Column("provider_config_id", Text, nullable=False),
    Column("upstream_model", Text, nullable=False),
    schema=SCHEMA,
)
