"""The three `chat` tables as SQLAlchemy Core `Table` objects.

  - conversation:   one thread, owned by one person, inside one workspace
  - message:        one turn, with its trace, its citations and its directives
  - pending_action: a write the agent proposed and a person has not decided on

id prefixes: `cnv_`, `msg_`, `pac_`.

**Why the trace is a column and not a log line.** Deck 3 (p22) puts `trace` in
the shared state schema and gives the reason: without it, once the system has
finished running, nobody can say which path the decision took. A log line is
correct for an operator and useless for the person reading the thread three days
later, who is exactly who Prope's audit story is for. So it is stored, returned,
and bounded — and `observability.safe_detail` is what keeps content out of it.

**Why `pending_action` is a table and not a field on `message`.** Because it is
consumed, once, by a different request than the one that created it. A row with
its own `decided_at` makes "this was approved by this person at this time" a fact
the database holds, and makes a double-confirm a primary-key-shaped no-op rather
than a race two handlers have to agree about.
"""

from sqlalchemy import Column, DateTime, Integer, Table, Text
from sqlalchemy.dialects.postgresql import JSONB

from prope.db.metadata import metadata

#: A-003: UTC with an explicit offset.
TIMESTAMPTZ = DateTime(timezone=True)

SCHEMA = "chat"


conversation = Table(
    "conversation",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workspace_id", Text, nullable=False),
    # A value, not a foreign key into `access.user` — the posture
    # `history_event.actor_id` takes, and what makes ADR-0054's tombstone cost
    # this module nothing. A thread survives the person who opened it.
    Column("actor_id", Text, nullable=False),
    # Derived from the first turn's routed intent, never from its text: a title
    # taken from what somebody typed is prompt content in a list view.
    Column("title_code", Text, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    Column("updated_at", TIMESTAMPTZ, nullable=False),
    Column("message_count", Integer, nullable=False),
    schema=SCHEMA,
)


message = Table(
    "message",
    metadata,
    Column("id", Text, primary_key=True),
    Column("conversation_id", Text, nullable=False),
    Column("workspace_id", Text, nullable=False),
    Column("actor_id", Text, nullable=False),
    # `user` or `agent`. Literal ASCII wherever it travels, per `domain.py`'s
    # rule for anything stored or compared.
    Column("role", Text, nullable=False),
    Column("body", Text, nullable=False),
    # The routed intent, or NULL on a person's own turn.
    Column("intent", Text),
    # `TraceEntry` list, already through `safe_detail`.
    Column("trace", JSONB, nullable=False),
    # `Citation` list: which chunks and prompts the reply stands on.
    Column("citations", JSONB, nullable=False),
    # `UiDirective` list, already through `sanitise_directives`.
    Column("directives", JSONB, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    schema=SCHEMA,
)


pending_action = Table(
    "pending_action",
    metadata,
    Column("id", Text, primary_key=True),
    Column("conversation_id", Text, nullable=False),
    Column("workspace_id", Text, nullable=False),
    # Who it was proposed to. The confirmation route checks this: a link to a
    # confirmation card is not a capability to use it.
    Column("actor_id", Text, nullable=False),
    Column("tool", Text, nullable=False),
    Column("summary", Text, nullable=False),
    Column("preview", JSONB, nullable=False),
    # The exact payload the executor will run. Stored rather than recomputed, so
    # that what a person approved and what runs cannot differ.
    Column("arguments", JSONB, nullable=False),
    # `pending` | `confirmed` | `rejected`.
    Column("status", Text, nullable=False),
    Column("created_at", TIMESTAMPTZ, nullable=False),
    Column("decided_at", TIMESTAMPTZ),
    # What the confirmed write produced, so the thread can link to it.
    Column("result_prompt_id", Text),
    Column("result_version_id", Text),
    schema=SCHEMA,
)
