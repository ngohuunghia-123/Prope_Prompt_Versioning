# ADR-0014 — Provider credentials are envelope-encrypted with a per-credential data key

**Status**: Accepted
**Date**: 2026-08-08
**Decision**: agent (A-092, and the encryption half of A-025 as amended)
**Module**: provider-access (written while locking provider-access)
**Related**: A-025, A-043, A-046, OQ-004, OQ-006, ADR-0003

## Context

OQ-004's answer made Prope a holder of third-party secrets, which it was not before. The constraints
table states the obligation without stating a mechanism: credentials are "supplied by the workspace,
encrypted at rest, never returned by a read API, and redacted in logs and audit records", and the row
is non-negotiable.

"Encrypted at rest" is the phrase that hides a decision. It is satisfied, in letter, by full-disk
encryption — and full-disk encryption protects against a stolen server. The realistic threat here is
not a stolen server. It is a `SELECT` from an application bug, a backup file copied to a laptop, a
read replica with looser access, or a query text captured in a log. Every one of those hands over the
plaintext of a disk-encrypted column.

The second unstated decision is the unit of compromise. If one key encrypts every credential in the
system, learning that key is total, and changing it means rewriting every row.

## Decision

**Envelope encryption, with the key-encryption key outside the database.**

- Each credential gets its own randomly generated 256-bit **data key** (DEK). The secret is encrypted
  with the DEK using an authenticated cipher (AES-256-GCM), and the nonce is stored beside it.
- The DEK is **wrapped** by a **key-encryption key** (KEK) supplied to the process from its
  environment or a key store, never from the database. Only `wrapped_dek` and `kek_version` are
  persisted.
- The `credential` table is **separate from `provider_config`**, so no configuration read path is
  structurally capable of returning ciphertext. "Never returned by a read API" stops depending on
  every future developer remembering to exclude a column.
- `last_four` is stored in the clear. It is what the dashboard shows and it is the only
  credential-derived value any API returns.
- **Rotating the KEK re-wraps DEKs.** It does not touch a single ciphertext and it never asks a
  workspace to re-enter its keys.
- **Rotating a credential replaces the row.** No readable history of a secret accumulates (A-025).
- Decryption happens only inside the provider-access process, into a 60-second in-memory cache
  (A-092). No other module can decrypt — including the gateway and the eval runner, which is the
  correction this ADR's sibling amendment makes to A-025's original wording.

**Where the KEK lives is `#TBD-step-4`.** An environment-supplied secret and a managed key service are
both compatible with everything above. The scheme is decided here because it is a migration to
reverse; the store is a deployment choice and step 4 owns it.

## Alternatives rejected

**One static key for every credential, column-encrypted.** Rejected on blast radius and on rotation.
Learning the key yields every workspace's provider account at once, and rotating it — the thing you
must do after learning it leaked — requires decrypting and re-encrypting every row in one migration,
during which the old key must still be present. Envelope encryption makes rotation a re-wrap of a few
small values.

**No application-level encryption; rely on database-level at-rest encryption.** Rejected because it
defends against the wrong threat. It protects a disk, not a query. A backup file, a replica, or an
ordinary `SELECT` from a bug returns plaintext, and those are the ways this credential realistically
escapes. The constraint also demands redaction in logs and audit records, which disk encryption does
nothing for.

**`pgcrypto`, passing the key as a query parameter.** Rejected specifically because of where the key
then appears: in query text, in `pg_stat_statements`, in slow-query logs, and in any query-logging
proxy. It moves the secret from the column into the telemetry, which is a worse place — telemetry is
retained longer and read more casually than the table.

**Store the credential only in an external secret manager and keep no ciphertext.** Rejected twice
over. A-012 caps operational complexity at one `docker-compose up` with no extra components to run
and debug alone, and a secret manager is a hard runtime dependency of every model call. It also puts
a network round-trip on the gateway's hot path, whose whole added-latency budget is 50 ms. The
60-second decrypted cache exists to keep cryptography off that path; a remote fetch would put a
different, slower thing back on it.

**Hash the credential.** Rejected as a category error, and it is worth stating because the reflex is
strong: a provider credential must be *presented* to the provider on every call, so it has to be
recoverable. It is not a password, and password-handling instincts produce a system that cannot make
a single call.

**Keep the ciphertext on `provider_config` as one more column.** Rejected for the reason the
separation exists: a single `SELECT *` in a handler, a serialiser that defaults to all fields, or an
ORM's eager load then carries the secret into a response body. Enforcement by structure beats
enforcement by discipline for a rule marked non-negotiable.

## Consequences

- Step 4 inherits a concrete requirement rather than a vague one: it must name where the KEK comes
  from, and the answer must survive the ProviderKekUnavailable failure mode — a missing KEK takes
  every consuming product's AI feature down, because Prope is an accepted hard dependency.
- The KEK's absence is a distinct, alerted, `/readyz`-withholding condition rather than a wave of
  errors that look like a provider outage. Confusing the two costs an hour of debugging the wrong
  seam at exactly the wrong moment.
- `kek_version` is on the row from day one. Adding it later would be the migration this ADR exists to
  avoid.
- A rotation is effective within 60 seconds everywhere, not instantly (A-092) — the same shape as
  ADR-0012's answer for the resolution cache, and for the same structural reason: there is no broker
  (A-012) and no inbound edge into this module for an invalidation message to arrive on.
- The security test is "recover the credential given the whole database and nothing else" (AC-2),
  which is a test of the property that matters rather than of the code path that implements it.
