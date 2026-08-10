# ADR-0045 — Every table in a module schema is tenant-scoped unless it is declared global

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: global — replaces the enumeration rule in ADR-0035 and the second clause in ADR-0042
**Related**: A-109, A-121, BR-01, ADR-0025, ADR-0027, ADR-0035, ADR-0038, ADR-0039, ADR-0040,
ADR-0042, OQ-007, OQ-013

## Context

ADR-0035 enabled row-level security on *"every table carrying `workspace_id`"* and protected that with
a CI test that *"enumerates tables carrying `workspace_id` and asserts each has row-level security
enabled with a policy."* The rule and its test share one property: **a table is in scope only if it
already has the column.**

Three consecutive step-4 module passes each found a table that did not:

| Pass | Table | What the test would have skipped |
|---|---|---|
| call-ledger (ADR-0040) | `ledger.call_body` | Raw end-user request and response bodies — the material OQ-013 is open about |
| access-control (ADR-0042) | `access.prompt_grant` | The table implementing BR-01's *"prompts are private by default"* |
| provider-access (this ADR) | `provider.credential` | **Every provider credential in Prope**, and the highest-liability table in the system |

Plus `provider.model_catalogue` in the same pass, and `access.workspace`, which escaped for the opposite
reason — it has no `workspace_id` column because its **primary key is** the workspace id. ADR-0042
handled that with a second clause bolted onto the test's query, which worked and did not generalise.

Every one of these is the same shape: a **child table carrying only a parent foreign key**. The
denormalised column looks redundant to whoever designs the table, so it is left out, and leaving it out
is exactly what removes the table from the test's field of view. Three for three is not three
oversights. It is the rule selecting for its own blind spot — a table is invisible to the check
precisely when somebody decided the tenant column was unnecessary, which is the decision most worth
reviewing.

Five modules are still unlocked at the time of writing, three of them own child tables, and each would
have hit this independently.

## Decision

**The CI test enumerates every table in the eight module schemas. Each must either carry `workspace_id`
with row-level security enabled and a policy, or appear in an explicit `GLOBAL_TABLES` map with a
written reason.**

```python
GLOBAL_TABLES = {
    'access.user':                     "a person is not a tenant's property; unique(email) is global",
    'access.role_permission':          "the (role, action) matrix is one table for the whole install",
    'history.history_action_registry': "30 seeded actions, immutable, ADR-0024 and ADR-0038",
    'access.workspace':                "IS the tenancy root — policied on id, not on workspace_id",
}

for table in all_tables_in_module_schemas():
    if table in GLOBAL_TABLES:
        assert rls_state_matches_declaration(table)
        continue
    assert has_workspace_id(table) and rls_enabled(table) and has_policy(table)
```

- **The default inverts.** A new table is covered unless somebody states in writing that it is not,
  rather than uncovered until somebody remembers to add a column. That is the same inversion ADR-0035
  made for query results — a missing filter returns zero rows instead of another tenant's data — applied
  one level up, to the schema itself.
- **`access.workspace` becomes an ordinary entry** rather than a clause inside the test's query.
  ADR-0042's second clause is retired; the declaration says what is true about the table, and the
  assertion checks that the policy exists on `id`.
- **The reason string is not decoration.** Adding a table to `GLOBAL_TABLES` means writing why it is
  global, in a file that appears in the diff, which is the review moment this whole chain of decisions
  keeps trying to create.
- Three tables gain `workspace_id` under this ADR's authority as part of provider-access's pass:
  `provider.credential` and `provider.model_catalogue`. `ledger.call_body` and `access.prompt_grant`
  already gained theirs under ADR-0040 and ADR-0042 and are unaffected.
- **ADR-0042's two `SECURITY DEFINER` functions remain the only sanctioned policy bypass**, and are
  unaffected by this change. This ADR governs which tables are checked; that one governs the two reads
  that must run before a tenant is known.

## Alternatives rejected

**Fix `credential` and `model_catalogue` and leave the rule alone.** The cheapest option and consistent
with the two precedents already set — ADR-0040 and ADR-0042 both did exactly this. Rejected because
doing it a third time is the evidence that it does not work. The next child table is invisible again,
and prompt-registry, evaluation, release-control and gateway are all still unlocked, all own child
tables, and all get their passes after this one. Fixing instances found by inspection also means the
guarantee is *"a careful reader looked at each module"*, which is precisely the enforcement model BR-03,
ADR-0025, ADR-0027 and ADR-0035 each declined for weaker stakes.

**Write the policy as a subquery against the parent** —
`USING (EXISTS (SELECT 1 FROM provider.provider_config p WHERE p.id = provider_config_id AND
p.workspace_id = current_setting('app.workspace_id')::uuid))`. Genuinely attractive: no denormalisation,
no backfill migration, and the tenant fact stays in exactly one place, which is the normalised-design
argument the missing columns were following in the first place. Rejected on two counts. It puts a
correlated subquery on every read of the credential path, which is inside the 10 ms dispatch-overhead
budget and behind a cache whose misses are the ones that matter. More decisively, **it does not solve
the problem this ADR exists for**: the test would still have to know which tables have parents and which
are genuinely global, so the enumeration gap moves rather than closes.

**Require `workspace_id` on every table with no exception list at all.** Rejected because three
legitimately global tables exist and inventing a synthetic workspace for `access.user` would be worse
than the disease — a person belongs to several workspaces (`workspace_member`), so a tenant column on
that table would be a lie the policy then enforces.

## Consequences

- **Adding a table to a module schema now fails CI until a decision is recorded**, one way or the
  other. That is a small friction on every migration and it is the point: the failure arrives at the
  moment the table is designed, not three passes later during an unrelated review.
- The denormalised `workspace_id` on child tables is accepted across the board. It can disagree with the
  parent, in principle; in practice every writer already knows the workspace because ADR-0020 makes the
  caller supply the subject, and a `WITH CHECK` policy on the child rejects a mismatch against the
  session variable, which is the disagreement that would matter.
- `GLOBAL_TABLES` is now a security-relevant file. It is short by design — four entries — and an entry
  added to it should be read the way a new `SECURITY DEFINER` object is read under ADR-0042.
- **This does not retroactively re-audit the three tables already fixed.** ADR-0040 and ADR-0042 stand
  as written; this ADR is why there will not be a fourth of them found the same way.
- ADR-0035's core decision — the policy, the session variable, the `SET LOCAL` per transaction, the
  failure inverting to zero rows — is unchanged. Only the question *"which tables"* is answered
  differently.

> **Confirmed one pass later, 2026-08-09, while locking prompt-registry's stack.** The claim above —
> *"this ADR is why there will not be a fourth of them found the same way"* — was tested immediately,
> and held. `registry.revision` carries `version_id, prompt_id, revision_number, body, …` and **no
> tenant column**: a child table reachable only through its parent, on **the table holding every prompt
> body in Prope**. Under ADR-0035's enumeration it would have been the fourth consecutive module pass to
> discover one of these by hand.
>
> Under this rule it was neither a discovery nor a decision. It is a coverage-test failure on day one
> and a one-line migration adding `workspace_id` with a policy. **No ADR was written for it, because
> none was required** — which is the whole of what this decision bought. The pattern is now confirmed
> four for four: `ledger.call_body`, `access.prompt_grant`, `provider.credential`, `registry.revision`,
> every one of them a child carrying only a parent FK, and every one of them a table whose tenant column
> looked redundant to whoever left it out.
>
> `GLOBAL_TABLES` is unchanged at four entries. `registry.revision` is not one of them and never could
> be.
