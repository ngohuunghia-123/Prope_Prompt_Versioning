# ADR-0021 — Consumer API keys are hashed; provider credentials are encrypted. The difference is the direction of use

**Status**: Accepted
**Date**: 2026-08-08
**Decision**: agent (A-113)
**Module**: access-control (written while locking access-control)
**Related**: A-046, A-081, ADR-0003, ADR-0014, ADR-0022, OQ-006

## Context

Prope now holds two kinds of secret, and ADR-0014 decided the wrong answer for one of them on purpose.

A **provider credential** is a secret Prope must *present* to somebody else. It has to come back out in
plaintext at dispatch time, so ADR-0014 chose envelope encryption and explicitly rejected hashing as a
category error: "the credential must be presented".

A **consumer API key** is the opposite. A consuming product presents it to Prope; Prope only ever needs
to answer "is this the key I issued". Nothing in the system ever needs to read one back. A-081 puts the
`api_key` table in access-control and makes a key default-deny, scoped to an explicit list of model
names — but says nothing about how the secret is stored.

The storage choice is constrained by where the check runs. `authenticate_api_key` sits on the gateway's
50 ms path, on every single request. That rules out the reflex answer for anything password-shaped: a
per-request bcrypt or argon2 verification costs tens of milliseconds by design, and it also cannot be
looked up, because a salted password hash is not indexable — you would have to try every key in the
table.

## Decision

**A consumer API key is stored as a SHA-256 hash of a high-entropy secret, is displayed exactly once at
creation, and carries its own id in the presented string so the lookup is a primary-key read.**

The wire format is `prope_<key_id>_<secret>`:

- `key_id` is the ULID of the row (prefix `key_`), so verification is one indexed read, not a table
  scan.
- `secret` is 256 bits from a cryptographically secure source. **Because the secret is high-entropy and
  machine-generated, a fast hash is the correct primitive** — the slow-KDF argument exists to make
  guessing a human-chosen password expensive, and there is nothing to guess here.
- Comparison is constant-time. The stored row keeps `last_four` for display and `last_used_at` for
  finding keys nobody is using, and nothing else that could reconstruct the secret.
- The plaintext is returned in exactly one response body, the creation one, and is never recoverable.
  Losing it means issuing a new key, which is a two-click operation and the correct outcome.
- **Human passwords are hashed with argon2id**, slow on purpose, in the same module. The two hashes are
  deliberately different primitives, and the reason is written on both.

## Alternatives rejected

**Encrypt consumer keys the way ADR-0014 encrypts provider credentials.** Rejected, and it is the
tempting one because the code already exists. It creates a decryptable copy of a secret that never needs
decrypting — the one design property worth having here is that a database dump does not yield working
keys, and encryption at rest with a KEK the application can reach gives that up in exchange for
consistency with a case that is not analogous.

**Store the key in plaintext so it can be shown again in the dashboard.** Rejected. "Show me my key
again" is a real request with a real answer — issue a new one — and the feature that satisfies it turns
a database read into credential disclosure. It also contradicts the non-negotiable constraint's spirit
for the neighbouring secret ("never returned by a read API"), and having one secret readable and one not
is how the wrong one gets copied into a log line.

**Hash with bcrypt or argon2id, like passwords.** Rejected on two independent grounds. It puts tens of
milliseconds on a 50 ms budget, on every request; and a salted hash cannot be indexed, so
authentication becomes a scan of every key in the table. The embedded `key_id` plus a fast hash gets
both properties, and the entropy of the secret is what makes it safe — which is a claim about the
secret, so it is enforced by generating it rather than by hoping.

**A JWT or other signed token, verified with no database read at all.** Rejected because it cannot be
revoked. A leaked key that stays valid until it expires is the failure this whole surface exists to
prevent, and ADR-0022 makes immediate revocation an explicit property. Statelessness is worth less than
a kill switch when the credential belongs to somebody else's production system.

**One key per workspace, no scope.** Rejected by A-081 already, and repeated here because the storage
decision makes it tempting: fewer keys is fewer rows. Default-deny scoping is what bounds the blast
radius of the leak this ADR assumes will eventually happen.

**Derive the key from the workspace id so it never needs storing.** Rejected — a derived key cannot be
rotated without rotating whatever it is derived from, and it makes every key in the system recoverable
from one secret.

## Consequences

- A database dump yields no working consumer key. It does yield wrapped provider credentials, whose
  protection is the KEK held outside the database (ADR-0014). The two secrets fail differently on
  purpose, and the reason is documented on both.
- Authentication is one primary-key read plus one hash, which is what makes the p95 target for
  `authenticate_api_key` credible rather than aspirational.
- The dashboard can never show a key again. That has to be obvious at creation time — a copy-once
  screen, not a toast — or the first support ticket is a user who closed the tab.
- `last_used_at` is the only signal available for spotting a key that is being used from somewhere it
  should not be. It is weak, and stating it is weak is the point: real detection needs the per-key call
  volume the call ledger already records, and that is a later screen, not a claim this ADR makes.
- Human passwords and machine keys use different hashes in the same module. Anyone reading that code
  will assume it is a mistake, so the reason lives here and is cited from the lock file.
- **Extended 2026-08-09 by ADR-0043.** This ADR chose argon2id and explained why it is slow, but never
  set its parameters — which left the lock's *"the cost parameter is tuned down because the login screen
  feels slow"* failure mode guarding a number that existed nowhere in writing. ADR-0043 sets
  **`m=47104` KiB, `t=1`, `p=1`**, pins `argon2-cffi`, and requires all three arguments to be named
  rather than inherited from library defaults that have already changed once between releases. It also
  settles where the login rate limiter's state lives, since that limiter exists to bound argon2id's
  aggregate cost on ADR-0033's 4-vCPU host rather than to protect the password.
