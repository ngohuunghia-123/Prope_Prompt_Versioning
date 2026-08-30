# Negative surface — what the LLM-call cache must never do

The inverse of the readiness checks: each line here is a behavior the cache is designed to
refuse, and a regression that reintroduces it should fail a test named after the line.

## Never store the prompt body or title

| # | Behavior | Where refused | Test |
|---|---|---|---|
| N1 | A body or title column exists on the cache table | migration DDL (03-D1) | row-content / schema-invariant test walks the table and asserts the columns absent |
| N2 | A body or title reaches a metric label, a log line, or a cache key string | 03-D10, A-046 | `test_no_content_reaches_a_log_line_by_construction.py` covers the new log lines; metric labels are closed enums (06-D6) |
| N3 | The cache key is reversible to the body | key is a SHA-256 content hash; there is no lookup by body (02, 03-D2) | key-equality test asserts the key is a hex digest |

## Never serve an un-gated answer

| # | Behavior | Where refused | Test |
|---|---|---|---|
| N4 | A stored row is returned without re-running `_gated` | 05-D1, gate-on-read | a poisoned row (a stored prediction whose fields fail coercion) is dropped and counted `miss_stale`, never returned (01-D6) |
| N5 | A stored row bypasses the drop/cap/dedupe logic | gate is the only judge (05-D1); the cache stores raw prediction fields and re-gates | gate-on-read unit test |
| N6 | A cache hit changes the suggestion shape a person sees | a hit is byte-identical to a fresh gated answer (04-D3, 05-D2) | equivalence test: hit output == fresh-gate output |

## Never let a cache failure become a product failure

| # | Behavior | Where refused | Test |
|---|---|---|---|
| N7 | A cache read error raises to the caller | read failure = miss (shape D8, 07-D3) | fault-injection test |
| N8 | A cache write error raises to the caller | write failure = return fresh (shape D8, 07-D3) | fault-injection test |
| N9 | A cache read error opens the circuit breaker | read path is outside the breaker wrap (07-D9) | fault-injection test asserts the breaker stays closed |
| N10 | The cache retries a store | no cache-initiated retry anywhere (07-D3/D5) | code-level assertion or fault-injection |
| N11 | A serve-stale-on-error rung exists | D11 written as a refusal (07-D11) | source walk refuses the pattern |

## Never cross a tenant boundary

| # | Behavior | Where refused | Test |
|---|---|---|---|
| N12 | A row is readable without the owning workspace's GUC | RLS `current_setting('app.workspace_id', true)` predicate + `WITH CHECK` (03-D3) | tenant-coverage test walks the table; a cross-workspace read returns zero rows |
| N13 | A prompt id appears in the cache key or row | the key is a content hash; the row carries `workspace_id` only (03-D4) | schema test asserts the columns |
| N14 | A body-derived value is used as a cross-workspace pivot | no prompt-id column (N13) | — |

## Never store unbounded content

| # | Behavior | Where refused | Test |
|---|---|---|---|
| N15 | A non-array `findings` value is stored | JSON-array CHECK (03-D6) | migration/constraint test |
| N16 | A cache row lives forever | TTL 24h enforced at read (03-D7); retention sweep is a recorded follow-up (00-D13) | TTL-at-read test |

## Never spend money the caller did not ask to spend

| # | Behavior | Where refused | Test |
|---|---|---|---|
| N17 | A cache hit triggers a model call | a hit is one SELECT, cost = 0 (00, 07-D15) | hit test asserts zero calls |
| N18 | A cache miss spends more than the pre-existing one call | the cache adds no call (07-D15) | — |
| N19 | Cost-saved is claimed without stored token counts | computed from stored `input_tokens`/`output_tokens` (06-D11/D12) | metric test |
| N20 | Cost-saved appears in a workspace cost delta | it is on Prope's meter, never a `ledger.call_record` (06-D11) | code-level assertion mirrors the other app-agent cost metrics |
