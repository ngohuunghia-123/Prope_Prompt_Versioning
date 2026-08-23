# ADR-0061 — The namespace is the unit of authorisation, for keys and for people

**Status**: Accepted
**Date**: 2026-08-18
**Decision**: user ("change per-prompt api key to per-folder api key, and RBAC per-folder for users too")
**Module**: access-control (the grant table, the key scope, the visible filter) / prompt-registry (the
namespace it already carries) / gateway (INT-004's argument)
**Supersedes**: nothing. **Amends**: A-081's scope shape, A-118's `ids` mode, ADR-0020's `Subject`
**Related**: A-007, A-021, A-081, A-111, A-112, A-115, A-116, A-118, ADR-0020, ADR-0035, ADR-0048,
ADR-0059, ADR-0060, ADR-0062, BR-01, OQ-006, OQ-079, OQ-147, OQ-150, INT-001, INT-002, INT-004

## Context

Two unrelated-looking problems turned out to be the same problem.

**An API key is scoped to a list of prompt names.** `api_key.scope_model_names text[]`, default-deny,
one entry per prompt (A-081). An admin issuing a key for a product that calls a thousand prompts
enumerates a thousand names, and every release of a new prompt is a second act — the lock already
records this as *"a cost worth watching in the pilot, since a consumer who was never granted it sees a
not-found with no explanation."* At a thousand entries it stops being a cost worth watching and becomes
the reason nobody issues a second key.

**An observation has no container, so it has no access rule.** ADR-0060 shipped
`prompt-observation` with SR-2 saying so in as many words: an observation has no owner and no access
level, so BR-01's private-by-default rule has nothing to key on, and visibility is workspace membership
plus `prompt.create`. That is a real widening, it is the largest open item in OQ-147, and it has no fix
inside that module — you cannot make a rule about ownership for a thing that has no owner.

**Both are the same missing concept: a container that authority attaches to.** Prope has one already
and has never used it for this.

### The folder is already the namespace, and the namespace is already on the row

`registry.folder` is `(workspace_id, slug)` — **flat**, no parent column, no tree. Its
`ck_folder_slug_shape` is byte-identical to `ck_prompt_property_namespace_shape`, deliberately: the
lock says *"the slug **is** the namespace, and a folder whose slug no prompt could ever carry would be
a drawer nothing fits in."*

Three consequences fall out, and all three are what make this decision cheap rather than expensive:

- **The gateway already has it.** `ModelName.parse` splits `namespace/name` at the edge of every
  request, and `ModelReference` carries the result. A namespace-scoped key check is a comparison
  against a value already in memory — **no extra read, on the hot path, ever**.
- **The registry already has it.** `prompt_property.namespace` is a `NOT NULL` column on the row the
  caller has already read before it asks `may()`. ADR-0020's arrangement extends without strain: the
  caller passes `namespace` alongside `owner_id` and `access_level`, from the same row.
- **There is no hierarchy to walk.** This is the fact the whole decision rests on. A nested folder tree
  would need ancestor resolution, ancestor resolution needs the folder table, and access-control is
  forbidden to read it — ADR-0020 would break. **Flat folders are what make per-folder authority
  expressible at all**, and that is now a constraint rather than an accident. See Consequences.

## Decision

**Authority attaches to the namespace. Three changes, one shape.**

### 1. A person may be granted a namespace

A new table, `access.namespace_grant (workspace_id, namespace, grantee_user_id, level, granted_by,
granted_at)`, mirroring `prompt_grant` row for row, with the same two levels (`viewer | editor`,
A-112's ceiling unchanged — no grant confers approve, release, withdraw or break-glass, at any scope).

`may()`'s union grows a **fifth** source, checked after the per-prompt grant and answered by the same
`GRANT_ACTIONS` policy map. Nothing subtracts; there is still no deny-override branch, for A-111's
reason.

**`prompt_grant` stays.** Sharing exactly one prompt is a real thing people do, and removing it to make
the model tidier would be trading a use case for a diagram. The two coexist; the namespace grant is the
bulk instrument and the prompt grant is the scalpel. Whether `prompt_grant` eventually retires is
OQ-150, and it is a question for after a workspace has used both.

**`access_level` stays too, and is untouched.** BR-01's private-by-default is a property of a prompt,
enforced as not-found and by RLS underneath. A namespace grant is a fifth way to be allowed, not a new
default. A prompt in a namespace nobody has granted is exactly as private as it is today.

### 2. The grant is on the namespace **value**, not on the `folder` row

There is **no foreign key** from `namespace_grant` to `registry.folder`, and there must not be one, for
migration 0016's own reasons restated one table further out. `folder` is a **label**: 0016 says there
is no FK from `prompt_property` either, that `list_folders` returns *the union of declared rows and
namespaces observed on prompts*, and that deleting a row *"removes the label, never a prompt."*

So a grant names a string, the way `prompt_grant.prompt_id` and `history_event.actor_id` name strings.
Three things follow and each is load-bearing:

- **A namespace with no `folder` row can still be granted.** Most namespaces in a live workspace are
  observed rather than declared; a permission model that only worked on declared ones would work on the
  minority.
- **Deleting a folder row does not revoke anything.** It removes a label. Revocation is deleting the
  grant, which is a different act with its own event — and the alternative, a cascade, would mean
  renaming a drawer silently cut off everyone using it.
- **An unrecognised namespace denies.** There is no fallback to workspace-visible for a namespace
  nobody has granted, which is the failure this shape is chosen to avoid: a typo'd namespace on a new
  prompt must make it invisible to colleagues (annoying, correctable, safe), never visible to everyone
  (silent, uncorrectable, and the exact disclosure BR-01 exists to close).

### 3. A key is scoped by namespace, and by name, and the union is the answer

`api_key` gains `scope_namespaces text[] NOT NULL DEFAULT '{}'` beside the existing
`scope_model_names`. INT-004 becomes:

```sql
SELECT EXISTS (
    SELECT 1 FROM access.api_key
    WHERE  id = :key_id AND revoked_at IS NULL
      AND (:model_name = ANY(scope_model_names) OR :namespace = ANY(scope_namespaces))
)
```

The gateway passes `:namespace` from the `ModelName` it already parsed. One indexed read, as before.

**Additive rather than a replacement**, and the reasoning is not timidity. Both arrays default empty, so
**A-081's default-deny survives byte for byte**: a key with neither array set resolves nothing, without
a branch anybody could forget. Every key that exists keeps working unchanged. And the two granularities
answer different questions — *this product owns this folder* is the thousand-prompt case, while *this
one integration may call this one prompt in a shared folder* is a case a namespace-only scope cannot
express at all. Dropping `scope_model_names` later, if nobody uses it, is one migration; adding it back
after dropping it is a migration plus an incident.

### 4. `visible_subject_filter` gains a fourth mode, and A-118's ceiling stops mattering

A-118 records its own revisit condition: *"a workspace's prompt count makes an explicit id list too
large to push into a query"*, watched by the `visible_filter_ids_size` histogram. Namespace grants
answer that condition rather than postponing it. INT-002 returns
`{mode: all | none | ids | namespaces, ids?, namespaces?}`, and the caller's `WHERE` gains a disjunct it
can evaluate itself:

```sql
WHERE workspace_id = :ws
  AND (owner_id = :actor OR id = ANY(:ids) OR namespace = ANY(:namespaces))
```

A person granted four folders holding two thousand prompts is four strings on the wire, not two
thousand ids. The histogram stays flat for the case that was going to move it.

**Amended 2026-08-19, at build: `mode` is a label, not a discriminated union.** As first written, the
four values read as mutually exclusive, and the SQL block immediately above them does not — it applies
`ids` and `namespaces` in one disjunction. The prose was wrong and the SQL was right, which the
implementation surfaced at the first call site: an actor can hold three per-prompt grants **and** two
folder grants, and a return shape that had to pick one of the two payloads could not have described
that person's visibility at all.

The shipped `VisibleFilter` carries both payloads; `mode` names whichever is populated, so the
histogram and the log line stay legible, and `IDS` wins when both are — it is the narrower dimension
and the one A-118's histogram was written to watch. The consumer contract is unchanged and deliberately
unbranched: `ALL` short-circuits, everything else ORs both payloads into a predicate the consumer can
evaluate itself. There is exactly one `if` in a correct consumer.

That shape was chosen for its failure direction. A consumer written before `namespaces` existed reads
only `ids` and therefore **narrows** — it shows too few prompts, which somebody reports, rather than too
many, which nobody does. A fourth exclusive mode would have failed the other way: a consumer that had
never heard of it would have fallen through its `if/elif` chain to whatever its `else` did, which in
every existing implementation is the unfiltered branch.

## Alternatives rejected

**Give `folder` a real identity and a foreign key from `prompt_property`.** The tidy relational answer,
and the one migration 0016 argues against for three paragraphs: it would make a display label
load-bearing for the gateway's hot path, and it would mean a workspace could not hold a prompt in a
namespace nobody has named. Rejected here for a fourth reason 0016 could not have had — under this
decision the FK would make **deleting a folder row a permission change**, so renaming a drawer would
become a security event.

**Nested folders.** Asked for by everyone who has ever seen a folder. Rejected, and now expensively
rather than cheaply: ancestor resolution requires reading the folder tree, access-control is forbidden
to read `registry`, and ADR-0020's whole arrangement — the caller passes the subject's attributes,
because there is exactly one of each — collapses when the attribute is a path whose meaning depends on
rows the oracle cannot see. A nested design needs either a materialised ancestor set passed on every
`Subject` (workable, and a much larger change) or the forbidden edge (not workable). **Flat is now a
constraint with a reason, not a limitation waiting to be lifted.**

**Replace `prompt_grant` with `namespace_grant` outright.** Fewer tables, one concept. Rejected: it
loses per-prompt sharing entirely, and `prompt_grant` carries a foreign key to `workspace_member` that
the tombstone path (ADR-0054) already depends on. Two tables with one policy map between them is
cheaper than one table plus a lost capability.

**Scope keys by namespace only, dropping `scope_model_names`.** What was actually asked for, and it is
90% of the value. Rejected on the 10%: a key that may call one prompt in a folder full of prompts is
unexpressible, and that is the shape of every integration that is *given* access rather than *owning*
it. The union costs one `OR`.

**A `namespace` subject type on `may()` instead of a grant table.** Would need no new table — the
caller asks `may(actor, 'prompt.read', Subject(type=NAMESPACE, id=namespace))`. Rejected because it
answers the wrong question: `may()` is about one subject, and the expensive case here is *listing*,
which is INT-002's. A grant table is what INT-002 can return a set from.

## Consequences

- **A-115's closed vocabulary grows to twenty-six.** `namespace.grant` is a new member, with a
  migration against `ck_role_permission_action_values` and a seed row per role. It is **not** folded
  into `prompt.grant`: whoever may share one prompt would otherwise be able to share a folder of a
  thousand, which is the escalation OQ-079 declined to create by accident and this would create on
  purpose. The cost is smallest **now**, while A-020 means no workspace holds a real matrix — the same
  timing argument OQ-149 makes for its own action question.
- **`prompt-registry` passes one more attribute.** `Subject` gains `namespace: str | None`, supplied
  from the row the caller has already read. `tests/contract/test_may_reads_no_subject.py` is unaffected
  and remains the assertion that matters: this module still reads only `access` tables.
- **Flat folders become an architectural constraint** rather than a current shape. It belongs in
  `prompt-registry.lock.yml` as a non-goal with this ADR as its reason, so that the next person who
  proposes a folder tree meets an argument instead of a shrug.
- **A prompt cannot move between namespaces, and that is now a security property.** A-021 makes the
  model name immutable once created, and `uq_prompt_property_namespace` enforces it. Under this
  decision that means a prompt's access container never changes — so there is no *"somebody moved a
  prompt and silently changed who can see it"* incident available in this design. It was free and it is
  worth naming, because it is the failure mode every folder-permission system has.
- **A leaked key can now learn a workspace's namespaces, and still not its prompt names.** A-116's
  indistinguishability holds *within* a namespace and is deliberately weakened *across* namespaces —
  see ADR-0062, which needs the weakening and pays for it. Recorded as an accepted finding in A-159
  rather than left implicit.
- **Observation gets its container**, which is what ADR-0060 could not give itself. See ADR-0062 §3:
  the key names the namespace its observations land in, and from that point SR-2's widening is closed by
  the same grant machinery as everything else, with no rule of its own.
- **`GET /api/v1/permissions` renders one more action**, which is the endpoint's job — the running
  matrix stays comparable against whatever OQ-006 signs off.
