"""the history schema, its two tables, and the closed action vocabulary

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-11

**WHAT THIS REVISION IS.** The ``history`` schema and its two tables —
``history_action_registry`` and
``history_event`` — arriving with the whole guarantee stack in one applied
migration: columns, named CHECKs, four indexes, the composite vocabulary key,
the tenant policy, the grant matrix and the thirty-one-row seed. Same shape
0002, 0003 and 0004 use.

**D-53 — THE LOCK FILE SAYS ``bigserial`` AND THIS SHIPS ``GENERATED ALWAYS AS
IDENTITY``.** A ``bigserial`` is a ``DEFAULT nextval(...)``, and a default is
only consulted when the caller omits the column — so under the lock's spelling a
hand-written INSERT supplying its own ``seq`` is accepted silently and the total
order stops being total. This is a **behavioural** deviation, not a spelling
one: ``tests/security/test_history_seq_cannot_be_supplied.py`` (plan 04-03)
asserts the refusal. It is owed an OQ against
``docs/modules/property-history.lock.yml`` ``data.owns -> history_event -> seq``
and ADR-0024's Decision block; **Phase 4's allocated range OQ-027..OQ-031 is
consumed, so the id is owed and unallocated** and is escalated to the
orchestrator in the phase's ``deferred-items.md`` §1. The spec is not edited to
agree (``.planning/BSP-LINK.md``).

**D-50 — THE LITERAL ``REVOKE`` THE LOCK FILE NAMES IS NOT ISSUED.**
``libraries_frameworks`` names ``REVOKE UPDATE, DELETE ON history.history_event
FROM prope_app``. ``prope_app`` never holds either, so the statement would be a
no-op that reads in a diff as protection; ``ddl.grant_table`` already argues the
positive form. Byte-identical end state, so no OQ is owed — the contrast with
D-53 above is the point.

**WHAT THIS REVISION ENFORCES, AND WHAT IT DELIBERATELY DOES NOT.** The
``(action, target_type)`` pairing is an engine fact — ``fk_history_event_action``
below. The ``details`` allow-list and ``requires_reason`` are not and cannot be:
a CHECK cannot reach another table, and ADR-0023 rejects triggers for this module
**by name** ("put the audit vocabulary in migrations rather than in a module,
where the allow-list of ADR-0024 cannot run"). Only two of 0004's three
anti-trigger reasons transfer — the volume argument does not, because
``history_event`` takes one row per state change, so a per-row registry probe
would be affordable here and is refused on the other two grounds.
``tests/security/test_history_validation_has_no_database_backstop.py`` (plan
04-04) asserts that absence rather than assuming it.

**THE RIG EDITS THIS REVISION FORCES, AND WHY 0004's CLAIM DOES NOT TRANSFER.**
0004 says no test rig edit is needed. True of a new *table*, false of a new
*schema*: ``tests/conftest.py`` (``schemaname = 'ledger'``),
``tests/architecture/test_tenant_coverage.py`` (``EXPECTED_ABSENT_SCHEMAS`` and
``== ("ledger",)``) and ``tests/integration/test_migration_chain.py`` (four
``ledger``-scoped constants) all name the schema as a literal. The first two go
red; the third goes **green-but-blind**, which is worse.

**TYPES.** Every ``*_id`` is ``text`` (ADR-0003 prefixed ULIDs) and every
timestamp is ``timestamptz`` (A-003). ``workspace_id``, ``actor_id`` and
``target_id`` are values, not references (A-122) — the property that makes
ADR-0054's tombstone-and-survive cost this module nothing. The module's only
foreign key is intra-schema.

**WHAT ``GENERATED ALWAYS`` GUARANTEES, AND THE ESCAPE HATCH IT DOES NOT CLOSE.**
PostgreSQL: for a ``GENERATED ALWAYS`` identity column "it is an error to insert
an explicit value (other than DEFAULT) without specifying either OVERRIDING
SYSTEM VALUE or OVERRIDING USER VALUE". No privilege is attached to
``OVERRIDING SYSTEM VALUE``, and the engine names the bypass in its own HINT — so
the refusal covers the statement anyone would write and not the statement someone
determined would write. Two halves record it:
``tests/security/test_history_seq_cannot_be_supplied.py`` proves both directions
at the engine, and ``tests/architecture/test_no_overriding_system_value.py``
refuses the token in source under ``src/prope/`` and ``alembic/`` — the half the
engine cannot close. The operational consequence: a supplied ``seq`` does **not**
advance the sequence, so the next engine-assigned value is lower than the
supplied one and sorts before an event written later. The order goes silently
wrong and stays wrong until the sequence climbs past it, which at "< 500 events
per prompt property per year" may be years. It is not a loud break.
"""

from collections.abc import Sequence

# `alembic/ddl.py`, imported by bare name rather than as `alembic.ddl` — that
# dotted name resolves to the installed Alembic package's own dialect-DDL
# submodule. `alembic.ini`'s prepend_sys_path puts this directory on the path.
from ddl import assume_migrate_role, enable_tenant_rls, grant_table, reset_role

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CREATE_HISTORY_ACTION_REGISTRY = """
CREATE TABLE history.history_action_registry (
    action           text     NOT NULL,
    target_type      text     NOT NULL,

    -- A set of identifiers, because the allow-list check is a set operation.
    -- Not jsonb, not a joined string. Empty for 28 of the 31 seeded rows.
    detail_keys      text[]   NOT NULL,

    requires_reason  boolean  NOT NULL,

    -- ADR-0024: a bounded Prometheus label. A typo mis-attributes an event's
    -- writer in a metric series, which is the quietest kind of wrong. The five
    -- literals are the module_id values as docs/modules/*.lock.yml spells them.
    writing_module   text     NOT NULL,

    CONSTRAINT pk_history_action_registry PRIMARY KEY (action),

    -- Looks like a redundant duplicate of the primary key and is not: a
    -- REFERENCES clause must name a unique constraint over exactly the
    -- referenced columns, so fk_history_event_action below needs this one.
    CONSTRAINT uq_history_action_registry_action UNIQUE (action, target_type),

    CONSTRAINT ck_history_action_registry_writing_module_values
        CHECK (writing_module IN (
            'prompt-registry', 'release-control', 'evaluation',
            'provider-access', 'access-control'
        ))
);
"""

# D-56: no workspace_id, and the absence is the decision. The vocabulary is
# closed install-wide (A-120), and under ADR-0035's inversion a tenant-scoped
# registry would return ZERO rows to registered_actions()'s declared consumer —
# a CI route-table test with no tenant context (INT-008) — so AC-6 would compare
# two empty sets and pass, vacuously, forever. A rule whose failure mode is a
# green test is what ADR-0045 was written about. The GLOBAL_TABLES entry in
# tests/architecture/test_tenant_coverage.py ships in this same change.

CREATE_HISTORY_EVENT = """
CREATE TABLE history.history_event (
    -- D-53. GENERATED ALWAYS, not bigserial: a default is only consulted when
    -- the caller omits the column, and prope_app holds INSERT by design.
    --
    -- CACHE 1 is also the default and is written out anyway: above one, "the
    -- values might be generated out of sequence when all the sessions are
    -- considered", which is the one setting that destroys this column's only
    -- property and is one ALTER SEQUENCE away.
    --
    -- MONOTONIC IS NOT GAPLESS, and nothing may infer a deletion from a gap
    -- (AC-10 is a Phase 6 test named "events are never deleted"). A rolled-back
    -- INSERT consumes a value and never returns it; a validation refusal in
    -- check_event raises before any statement is issued and consumes nothing.
    -- ASSIGNMENT ORDER IS NOT COMMIT ORDER either — two transactions can take 5
    -- and 6 and commit 6 first, so a reader between the commits sees 6 with no
    -- 5. Inside one transaction (PH-04, AC-4) the order is exact; across
    -- transactions it is not, which lands on Phase 5's cursor pagination.
    seq              bigint       GENERATED ALWAYS AS IDENTITY (CACHE 1) NOT NULL,

    -- The identity, and the primary key: an hev_-prefixed ULID (A-045). It is
    -- what INT-006's envelope returns and what is logged. A bigint surrogate
    -- beside it would be two identities for one row.
    id               text         NOT NULL,

    workspace_id     text         NOT NULL,
    actor_type       text         NOT NULL,
    actor_id         text,
    action           text         NOT NULL,
    target_type      text         NOT NULL,
    target_id        text         NOT NULL,
    scope_prompt_id  text,
    reason           text,

    -- The inversion of 0003's call one schema over. `call_body.request_body` is
    -- text because "jsonb would reject a malformed body, which is exactly the
    -- body worth keeping". Here the payload is assembled by our own code out of
    -- allow-listed keys and never carries provider content, so a malformed
    -- payload is a caller bug and refusing it at the engine is right. One rule
    -- applied twice, not two contradictory ones. NOT NULL DEFAULT '{}' because
    -- NULL and {} would be two spellings of "no details" and the allow-list
    -- check would grow a branch nobody writes. No GIN index: no query in any
    -- lock file reads a details key.
    details          jsonb        NOT NULL DEFAULT '{}'::jsonb,

    -- D-54: no database-stamped `written_at` beside this. `seq` already carries
    -- every ordering claim the module makes, and BSP-LINK forbids inventing
    -- schema the spec did not declare.
    occurred_at      timestamptz  NOT NULL,

    CONSTRAINT pk_history_event PRIMARY KEY (id),

    -- Not the fifth index D-55 refuses: D-55 is about query support, this
    -- enforces a constraint. The sequence guarantees distinctness only while
    -- nobody restarts it, and the test rig restarts it between tests by design
    -- (D-48) — so this is what makes "seq is a total order" a property of the
    -- table rather than of the sequence's history. Write cost is a right-edge
    -- B-tree insert on a monotonically increasing bigint.
    CONSTRAINT uq_history_event_seq UNIQUE (seq),

    -- Never a native enum (Pitfall 4): adding a value cannot run inside a
    -- transaction block and removing one is impossible at any price.
    CONSTRAINT ck_history_event_actor_type_values
        CHECK (actor_type IN ('user', 'system')),

    -- actor_id is null ONLY in the system case; a system actor WITH an id is
    -- permitted. Named so a test can say which rule refused.
    CONSTRAINT ck_history_event_actor_id_present_unless_system
        CHECK (actor_id IS NOT NULL OR actor_type = 'system'),

    -- Characters, not bytes, and a CHECK rather than varchar(500): ADR-0053
    -- ships a Vietnamese-only interface, so a byte cap would silently be a
    -- ~170-character cap for every user the MVP has. A named CHECK is also
    -- droppable and re-addable, where a type change on an append-only table is
    -- a rewrite prope_app cannot perform.
    CONSTRAINT ck_history_event_reason_length
        CHECK (reason IS NULL OR char_length(reason) <= 500),

    -- D-57. No ON DELETE or ON UPDATE clause of any kind: the registry is
    -- SELECT-only for prope_app and A-120's vocabulary is closed, so the case
    -- cannot arise, and naming a behaviour for an impossible case invites
    -- someone to make it possible (0003:216-221).
    --
    -- The cross-tenant objection is disposed of rather than assumed:
    -- referential-integrity checks always bypass row security, which is why
    -- test_no_foreign_key_leaves_the_schema exists — but this key's target is
    -- global and byte-identical for every workspace, so its success leaks
    -- nothing. [AGENT JUDGEMENT, from arithmetic and not a measurement] every
    -- insert takes a FOR KEY SHARE lock on one of 31 rows; those locks are
    -- mutually compatible, and multixacts arise only from concurrent locks on
    -- the SAME row. One app and one worker on one VM (ADR-0033), 200
    -- appends/sec spread over 31 rows with millisecond transactions. The escape
    -- hatch is recorded rather than pre-emptively tuned: dropping the key is
    -- cheap at any time, adding it back after the pilot is a validating scan
    -- over a never-shrinking audit table. Do not touch
    -- autovacuum_multixact_freeze_max_age.
    CONSTRAINT fk_history_event_action
        FOREIGN KEY (action, target_type)
        REFERENCES history.history_action_registry (action, target_type)
);
"""

# No CHECK on target_type anywhere. ADR-0024 calls it a closed enumeration; the
# registry's 31 seeded rows ARE that enumeration, and history_event.target_type
# is closed by the composite key above. A CHECK listing 13 literals would be a
# second copy of a list, and a fourteenth value would become a DROP/ADD
# CONSTRAINT with a validating scan over an append-only table.

# Every index leads with workspace_id, as every declared index in Prope does.
# All four ship with the table, not with the reader that uses them (D-55): three
# back INT-007's declared read scopes and one backs A-126's hand-run Success
# SQL. Cheap now, awkward later on the one table in Prope that only ever grows
# (A-121). The longest name is 55 characters, counted rather than assumed,
# against PostgreSQL's 63-byte identifier limit.
CREATE_INDEXES = (
    # The Activity view — GET /api/v1/prompts/{id}/activity, Phase 5.
    """
    CREATE INDEX ix_history_event_workspace_id_scope_prompt_id_seq
        ON history.history_event (workspace_id, scope_prompt_id, seq DESC)
    """,
    # One subject's trail, Phase 5.
    """
    CREATE INDEX ix_history_event_workspace_id_target_type_target_id_seq
        ON history.history_event (workspace_id, target_type, target_id, seq DESC)
    """,
    # A person's actions — what makes AC-9 answerable after a tombstone.
    """
    CREATE INDEX ix_history_event_workspace_id_actor_id_seq
        ON history.history_event (workspace_id, actor_id, seq DESC)
    """,
    # A-126's Success-metric queries, hand-run.
    """
    CREATE INDEX ix_history_event_workspace_id_action_seq
        ON history.history_event (workspace_id, action, seq)
    """,
)

# D-59. The seed is a migration and not a startup task for two reasons.
# ADR-0038's whole safety argument is a deploy ordering — "the row exists, then
# the code that names it starts" — which only exists if the seed is a migration;
# and D-57's key means the registry must be non-empty before the first event can
# be written, so a startup seed would make the first append after a fresh deploy
# a race. A separate data revision is refused as two revisions that must not be
# applied apart, for no gain. The sharp edge ADR-0038 already records: the
# thirty-second action is a new revision plus a restart.
#
# The 31 rows are derived by reading the five writing modules' `outputs` blocks,
# NOT ADR-0024's Context table, which lists 30 and omits `user_tombstoned`. The
# union is exactly 31 with no adjustment.
#
# `requires_reason` is true for exactly three, stated identically in this lock
# file, in release-control.lock.yml and in INT-006 — the one registry column
# fully determined by the specs.
#
# `detail_keys` is seeded non-empty for exactly two, and every other action is
# seeded empty INCLUDING FIVE WHOSE KEYS A LOCK FILE ALREADY DECLARES. Declared
# keys exist for seven of 31 actions, not three (CONTEXT's D-61 states this
# wrongly; corrected here and in deferred-items §5). `user_tombstoned` is
# declared deliberately empty by ADR-0054. evaluation.lock.yml:96 declares that
# eval_suite_updated / eval_run_started / eval_run_completed /
# eval_run_interrupted each carry "the prompt_id, version_id, suite_version, and
# actor" — prompt_id maps to scope_prompt_id and actor to actor_id, but
# version_id and suite_version are columns history_event does not have, so they
# are details keys declared today in a lock file that exists. They are seeded
# EMPTY anyway, as a choice: Phase 16 is the module that will write them and
# should register them with its own test, and a key seeded now by a phase that
# cannot exercise it is a guess with a green test behind it. The cost, stated
# here rather than discovered twelve phases later: Phase 16 writing
# eval_run_started with details={"version_id": ...} against this seed is refused
# with unknown_detail_key. No phase owns "each writing module registers its own
# keys"; OQ-029 carries the obligation.
#
# `target_type` is DERIVED, not read. ADR-0024 and A-122 call it a closed
# enumeration and it is enumerated nowhere; the only member stated anywhere in
# docs/ is `user` (A-151, ADR-0054). Thirteen values result. The cost of being
# wrong is bounded: nothing joins on it, AC-6 asserts only the action names, and
# D-57 makes the pairing an engine fact even though the vocabulary is a
# judgement. See OQ-029.
SEED_ACTION_REGISTRY = """
INSERT INTO history.history_action_registry
    (action, target_type, detail_keys, requires_reason, writing_module)
VALUES
    -- prompt-registry, 5. OQ-028: `retired` carries no target type at all, and
    -- `owner_changed` / `access_level_changed` name a FIELD rather than a
    -- subject, so three of these do not satisfy A-120's own
    -- <target_type>_<past participle> rule. Seeded as the lock files literally
    -- spell them, because AC-6 is an asserted equality and A-120 is prose.
    ('property_created',              'property',        '{}', false, 'prompt-registry'),
    ('revision_created',              'revision',        '{}', false, 'prompt-registry'),
    ('owner_changed',                 'property',        '{}', false, 'prompt-registry'),
    ('access_level_changed',          'property',        '{}', false, 'prompt-registry'),
    ('retired',                       'property',        '{}', false, 'prompt-registry'),

    -- release-control, 8. Two of the three requires_reason rows are here.
    ('revision_submitted',            'revision',        '{}', false, 'release-control'),
    ('revision_approved',             'revision',        '{}', false, 'release-control'),
    ('revision_changes_requested',    'revision',        '{}', true,  'release-control'),
    ('revision_released',             'revision',
        '{version_id,previous_version_id,break_glass}',        false, 'release-control'),
    ('revision_restored',             'revision',        '{}', false, 'release-control'),
    ('revision_break_glass_released', 'revision',        '{}', true,  'release-control'),
    ('release_withdrawn',             'release',         '{}', true,  'release-control'),
    ('review_task_closed',            'review_task',     '{}', false, 'release-control'),

    -- evaluation, 4. All four have declared keys (version_id, suite_version)
    -- and are seeded empty on purpose — see the note above.
    ('eval_suite_updated',            'eval_suite',      '{}', false, 'evaluation'),
    ('eval_run_started',              'eval_run',        '{}', false, 'evaluation'),
    ('eval_run_completed',            'eval_run',        '{}', false, 'evaluation'),
    ('eval_run_interrupted',          'eval_run',        '{}', false, 'evaluation'),

    -- provider-access, 4.
    ('provider_configured',           'provider_config', '{}', false, 'provider-access'),
    ('provider_updated',              'provider_config', '{}', false, 'provider-access'),
    ('provider_disabled',             'provider_config', '{}', false, 'provider-access'),
    ('credential_rotated',            'provider_config', '{}', false, 'provider-access'),

    -- access-control, 10. `user_tombstoned` is the row ADR-0024's Context table
    -- omits and ADR-0054 requires.
    ('workspace_created',             'workspace',       '{}', false, 'access-control'),
    ('member_added',                  'member',          '{}', false, 'access-control'),
    ('member_removed',                'member',          '{}', false, 'access-control'),
    ('role_assigned',                 'role',
        '{role,grantee_user_id}',                              false, 'access-control'),
    ('role_revoked',                  'role',            '{}', false, 'access-control'),
    ('access_granted',                'prompt_grant',    '{}', false, 'access-control'),
    ('access_revoked',                'prompt_grant',    '{}', false, 'access-control'),
    ('api_key_created',               'api_key',         '{}', false, 'access-control'),
    ('api_key_revoked',               'api_key',         '{}', false, 'access-control'),
    ('user_tombstoned',               'user',            '{}', false, 'access-control');
"""


def upgrade() -> None:
    """Create the ``history`` schema with its whole guarantee stack and its seed."""
    # Before assume_migrate_role(): prope_migrate is not guaranteed to hold
    # CREATE ON DATABASE, which is why 0001 created `ledger` as the connected
    # superuser. AUTHORIZATION is what makes prope_migrate own everything
    # created inside, which is what ADR-0035's owner bypass rests on (ADR-0027).
    op.execute("CREATE SCHEMA history AUTHORIZATION prope_migrate")
    op.execute("GRANT USAGE ON SCHEMA history TO prope_app, prope_report")

    assume_migrate_role()

    # The registry is created and seeded before history_event, because the
    # composite key points at it.
    op.execute(CREATE_HISTORY_ACTION_REGISTRY)
    op.execute(SEED_ACTION_REGISTRY)
    op.execute(CREATE_HISTORY_EVENT)

    for statement in CREATE_INDEXES:
        op.execute(statement)

    # T-04-03. In the same revision that creates the table, never a later one:
    # the window between the two would be a table prope_app can read across
    # tenants. history_action_registry deliberately gets no call at all (D-56),
    # with its GLOBAL_TABLES entry shipping in this same change.
    enable_tenant_rls("history", "history_event")

    # PH-02 IN ITS ENTIRETY. No UPDATE, no DELETE, in this revision or any later
    # one — ADR-0025's "a log the application can rewrite is a Sheet with better
    # indexing". SELECT alongside INSERT is a requirement rather than
    # generosity: PostgreSQL requires SELECT on every column a statement
    # references, and the tenant policy's predicate references workspace_id
    # (0003:246-251 records the identical reasoning for call_body). SELECT is
    # also what INT-007's read() needs in Phase 5.
    #
    # report_select takes its default of True, and the argument is made rather
    # than inherited. ADR-0037 was written about this exact table: A-126's
    # cross-workspace Success SQL reads history_event, and withholding SELECT
    # from prope_report sends that query back to prope_migrate — the only role
    # that can DELETE a history row, and precisely the outcome ADR-0037 exists
    # to prevent. Granting is not the lenient option here. The
    # counter-consideration, stated rather than omitted: `reason` is
    # user-authored free text and `details` is a payload, so prope_report is a
    # full-read credential over the module's two most content-bearing columns —
    # a posture ADR-0037 already declares, whose control is A-124's allow-list
    # and A-020's line, not a grant.
    grant_table("history", "history_event", app_privileges=["SELECT", "INSERT"])

    # D-51, derived from ADR-0038 rather than chosen: "there is no user-editable
    # path and no API that writes it, so there is no runtime event that could
    # make the cache stale". That is what makes a process-lifetime cache with no
    # invalidation safe — the only writer is prope_migrate, the only write is a
    # migration, and ADR-0031 restarts the application after migrating.
    grant_table("history", "history_action_registry", app_privileges=["SELECT"])

    reset_role()


def downgrade() -> None:
    """Drop both tables and the schema.

    Reverse dependency order: the event table first, then the registry its
    composite key points at. Nothing is left un-undone — no other schema
    references ``history`` and nothing outside it holds a value derived from it.
    """
    assume_migrate_role()
    op.execute("DROP TABLE IF EXISTS history.history_event")
    op.execute("DROP TABLE IF EXISTS history.history_action_registry")
    op.execute("DROP SCHEMA IF EXISTS history CASCADE")
    reset_role()
