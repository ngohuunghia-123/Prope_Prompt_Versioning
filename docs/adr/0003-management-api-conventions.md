# ADR-0003 — Management API conventions and identifier format

**Status**: Accepted
**Date**: 2026-08-08
**Scope**: Global — cited by every module lock file
**Related**: A-003, A-026, A-045, A-046

## Context

Roughly forty fields per lock file, times eight modules, contain the same handful of cross-cutting
shapes: how an id looks, what an error body contains, how a list is paginated, what a health endpoint
is called, how a metric is named. Deciding these per module produces eight dialects inside one product
and eight versions of the same question. Deciding them once, here, means every later lock file cites a
line instead of inventing one.

## Decision

**Identifiers.** ULIDs with a typed prefix — `prm_`, `rev_`, `rel_`, `evr_`, `usr_`, `prv_`. Lexically
sortable, generatable without a round-trip, and a mistyped id is wrong in a way a human can see. The
`rev_` id is the **version ID** the glossary already defines and the gateway already exposes.

**Timestamps.** RFC 3339 UTC everywhere, in storage and on the wire (A-003).

**Errors.** One envelope on the management API: `{error: {code, message, details?, request_id}}`, with a
stable machine `code` and a human `message`. **The gateway is exempt** — it returns OpenAI-shaped errors,
because wire compatibility is a non-negotiable constraint and a near-miss breaks every client SDK
(A-026, `00_context.md#constraints`).

**Pagination.** Opaque cursor, `?limit=&cursor=`, `limit` default 50 and max 200. Not offset: the
registry list is sorted by recency and offset paging over a list that changes underneath the reader
skips rows silently.

**Health.** `/healthz` (process alive) and `/readyz` (dependencies reachable) on every service, distinct
because a system that is an accepted hard dependency must be able to say "up but not ready" rather than
accepting traffic it cannot serve.

**Not-found vs forbidden.** A subject the actor may not see returns not-found, never forbidden.
Private-by-default is the top adoption barrier in the survey, and a 403 leaks the existence of the
thing it is protecting.

**Observability naming.** `prope_<module>_<name>_<unit>` for metrics; structured JSON logs with a fixed
field set; prompt bodies, fallback answers, request/response bodies, and credentials never appear in
logs or history events (A-046).

## Alternatives rejected

**UUIDv4.** Rejected for lexical unsortability — every listing then needs a separate sort column, and
index locality suffers on the registry's hottest table. **Auto-increment integers**: rejected because
they leak volume, and because a version ID appearing in a customer's API call should not disclose how
many prompts the workspace has.

**RFC 7807 `application/problem+json`.** Rejected as a poor fit next to the OpenAI error shape the same
product must also serve; two spec-shaped error formats in one codebase invites clients to guess. A
small explicit envelope, plus one documented exemption, is easier to hold.

**Offset pagination.** Rejected as above — silent row-skipping on a recency-sorted list.

**One combined `/health`.** Rejected: liveness and readiness answer different questions, and conflating
them means a restart loop during a dependency blip.

## Consequences

- Every module lock file cites A-045 and A-046 rather than restating these.
- The gateway carries a documented exemption from the error envelope. That exemption is the single
  place where "OpenAI compatibility" wins over internal consistency, and it is deliberate.
- Reversing the id format after data exists is a migration, which is why this is an ADR.
