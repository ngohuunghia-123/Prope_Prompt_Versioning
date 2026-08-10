# ADR-0032 — Secrets live in one `.env` file on the host, and the KEK is one of them

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: global — the KEK belongs to provider-access's encryption scheme
**Related**: A-020, A-025, A-046, A-092, A-113, ADR-0014, ADR-0021, ADR-0030, ADR-0031, ADR-0033, OQ-013

## Context

ADR-0014 chose envelope encryption for workspace provider credentials and **deferred the key-encryption
key's store to step 4 by name**. This is that decision.

Two classes of secret exist and only one was open. Workspace provider credentials are *data*, already
settled: envelope-encrypted in the `credential` table, held in its own table so no configuration read
path can return it, decryptable **only inside provider-access**, into a 60-second process-local cache
(ADR-0014, A-092, A-025). The non-negotiable constraint reads:

> "Provider credentials are supplied by the workspace, encrypted at rest, never returned by a read API,
> and redacted in logs and audit records"

The open class is **deployment secrets**: the PostgreSQL password, the RabbitMQ credentials, the session
signing key, and the KEK that wraps every data key.

The threat model was set by ADR-0021, which hashed consumer API keys rather than encrypting them so that
*"a database dump yields no working key"*. The realistic leak for a small pilot is the same one: a
`pg_dump`, a backup copied somewhere convenient, a disk snapshot handed to somebody. **A KEK held
anywhere outside the database defeats that completely**, and every option considered here does so. What
separates the options is much narrower than it first appears: only a cloud KMS additionally survives a
stolen disk image, and nothing on this list survives a live root compromise of the VM for longer than it
takes the attacker to use the application's own identity.

## Decision

**One `.env` file on the VM, mode `0600`, owned by the deploy account, git-ignored, loaded by
docker-compose's `env_file:`. It holds the KEK, the PostgreSQL password, the RabbitMQ credentials and
the session signing key.**

- **`.env` never enters CI.** ADR-0031 deploys over SSH, so the tempting shape is for the pipeline to
  template `.env` from GitHub Actions secrets. That is refused: it would place the KEK in GitHub as well
  as on the host, turning one copy into two. The file is hand-placed once; the deploy script only runs
  compose against it.
- **The KEK loads as a `pydantic-settings` `SecretStr`**, so its `repr` renders as asterisks and a
  configuration-validation error cannot echo it. This matters more than it would have this morning:
  ADR-0030 ships every container's stdout to the log stream, so a startup traceback is no longer
  something only the operator sees.
- Nothing reads `os.environ` wholesale into a log line, an error report, or a metric label. This is the
  same rule A-046 already applies to bodies and credentials, extended to the process environment, and it
  is the specific mitigation for the one real weakness of environment variables over file mounts.
- `.env.example` stays in the repository with every key present and every value empty, so a new
  environment fails loudly on a missing key rather than silently on a wrong one.
- Rotation of the KEK is a **re-wrap of the data keys**, not a re-encryption of the credentials. That is
  what ADR-0014 bought and it is what makes this decision genuinely deferrable rather than merely
  deferred.

## Alternatives rejected

**Docker-compose `secrets:` file mounts at `/run/secrets`.** This was the recommendation and it lost to
the user's decision. Its advantage is real but narrow: environment variables are visible in
`docker inspect`, are inherited by every child process, and are captured by anything that serialises the
process environment. Against the dominant threat — a database dump or backup leak — it is exactly
equivalent, because in both cases the key is outside the database. The residual gap is closed in
practice by the `SecretStr` rule and the no-`os.environ`-logging rule above, and the file mount costs a
per-service block in compose that the pilot does not otherwise need.

**A cloud KMS holding the KEK, with provider-access calling `Decrypt` on the wrapped data key.** Rejected
for the pilot and named as the upgrade path. It is the only option that survives a stolen disk image, and
the 60-second credential cache (A-092) means the call frequency is trivially low. It costs a cloud
account and identity that nobody has named, and it adds an external dependency to the one module that
already owns Prope's only outbound egress. The trigger for adopting it is explicit: **A-020's security
baseline sign-off, at the point real corporate credentials enter the system.**

**Self-hosted HashiCorp Vault.** Rejected as the worst ratio on the list. It is proper secret management
with rotation and audit, and it adds a service with its own storage, upgrade path and unseal procedure to
a VM already running seven things — while protecting no better than a `0600` file against a live host
compromise, because both live on the same host.

**Storing the KEK in the database beside the ciphertext.** Rejected outright, and recorded because it is
the mistake that makes envelope encryption decorative. A dump would then contain both the wrapped data
keys and the key that unwraps them, which is precisely the outcome ADR-0021 rejected for consumer keys.

## Consequences

- The KEK exists in exactly one place: `.env` on the VM. Losing it loses every stored provider
  credential — they are unrecoverable and the workspaces re-enter them. That is the intended failure
  mode of encryption at rest, and it makes the `.env` file itself the thing worth backing up separately
  from the database, and never into the same archive as a `pg_dump`.
- OQ-013's residency half is unaffected: nothing leaves the host.
- A future move to a KMS supersedes this ADR and changes ADR-0014's key handling, not the `credential`
  table, not provider-access's decrypt boundary, and not A-092's cache.
- The one weakness that remains after the mitigations is `docker inspect` on the host, which requires
  access to the Docker socket — and anyone with that has root-equivalent access to every mounted file
  as well. The gap between the chosen option and the recommended one is therefore smaller than the
  earlier framing suggested, which is why this decision is recorded without qualification.
- **Extended 2026-08-09 by A-135.** This ADR treated the KEK as one value, but `credential.kek_version`
  has existed since provider-access was locked and a column named for a version implies more than one.
  The convention: `.env` may hold several `PROPE_KEK_V<n>`, **the highest present is the wrapping key**,
  and unwrapping selects by the row's own recorded version. A rotation is *add V2 → re-wrap every
  `wrapped_dek` → remove V1 once no row references it*, which touches no plaintext credential and needs
  no downtime — cheap only because ADR-0014 chose envelope encryption. Without this, rotating the KEK
  would be an all-or-nothing rewrite designed during whatever incident prompted it.
- **Confirmed 2026-08-09 during provider-access's pass.** The separate-destination rule for `.env`
  versus the `pg_dump` (ADR-0036) is what makes AC-2 — *"the entire database and no other material
  yields nothing"* — hold through the backup channel rather than only against a live database. A-131's
  fallback, where no second machine exists and the dump is copied by hand, is the case where that rule
  is most likely to be broken by convenience.
