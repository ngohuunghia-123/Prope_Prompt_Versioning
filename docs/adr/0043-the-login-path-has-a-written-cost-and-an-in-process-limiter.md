# ADR-0043 — The login path has a written cost, and the limiter that bounds it lives in the process

**Status**: Accepted
**Date**: 2026-08-09
**Decision**: user
**Module**: access-control
**Related**: A-012, A-046, A-080, A-108, A-110, A-113, A-114, A-129, A-130, ADR-0021, ADR-0022,
ADR-0026, ADR-0029, ADR-0031, ADR-0033

## Context

ADR-0021 chose argon2id for passwords and explained *why* it is slow — *"deliberately slow, and
deliberately a different primitive from the API-key hash in the same module."* It never chose the
numbers. The lock inherits that gap twice over: `sign-in p95 < 500 ms` at *"argon2id at its configured
cost"* names a budget with no configuration behind it, and a failure mode reads
*"Argon2id's cost parameter is tuned down because the login screen feels slow"* — a guard pointed at a
parameter that does not exist in writing anywhere, so there is nothing to tune down *from*.

The lock also commits twice to rate limiting — *"Login is rate-limited per email address and per source
address"* in `security_requirements`, and an `AccessControlLoginBruteForce` alert that exists
*"so the rate limit's effectiveness is visible"* — without saying where the state lives. Redis, the
reflexive answer, is unavailable: A-080 and A-114 have already forbidden its two natural jobs here, and
ADR-0033 fixed the host at seven services.

Both gaps land on the same constraint, which is why they are one decision. ADR-0033 sizes the host at
**4 vCPU / 8 GB** with `shared_buffers=1GB`, and A-130 records that argon2id is one of three things
sharing the `app` process with the gateway, *"burning tens of milliseconds of a core and tens of
megabytes per login"* — inside a p95 the constraints table states as 50 ms for a dependency it also
calls *"an accepted hard dependency of consuming products' request paths."* The rate limiter's real job
is therefore not to protect the password. **It is to bound how much argon2id the box is willing to run**,
and that only works if it rejects before the hash rather than after it.

## Decision

**argon2id runs at `memory_cost=47104` (46 MiB), `time_cost=1`, `parallelism=1`, and an in-process
sliding-window limiter rejects an over-limit attempt before the hash is computed.**

- The parameters are OWASP's first-choice argon2id configuration. On this CPU class that is roughly
  55–70 ms per verification — about 12% of the 500 ms target, and the headroom is deliberate, so the
  number is never the reason somebody reaches for the cost parameter.
- **`parallelism=1`, explicitly not `argon2-cffi`'s default of 4.** On 4 vCPU, `p=4` means one login
  occupies every core the gateway is serving from. The library defaults (`t=3, m=64 MiB, p=4`) are
  wrong for this host in two of their three terms and are never to be relied on implicitly:
  `PasswordHasher` is constructed with all three arguments named, and `argon2-cffi` is **pinned**,
  because these defaults have already changed once between releases.
- `PasswordHasher.check_needs_rehash` runs on every successful login, so raising the cost later is a
  configuration change that migrates hashes as people sign in, not a migration.
- The limiter is a bounded in-process structure keyed on `(bucket, key)` for `bucket ∈ {email,
  source_address}`, holding a short deque of attempt timestamps, capped in key count and evicted by
  age. **It is consulted before the `user` row is read and before any hash is computed**, and a rejected
  attempt returns the same generic failure as a wrong password — the lock already requires the unknown-
  email and wrong-password responses to be identical, and a distinguishable rate-limit response would
  reintroduce the enumeration oracle by a side door.
- A new counter, `prope_access_control_login_rate_limited_total`, is required rather than optional.
  Rejections now happen before the hash, so they are invisible in `login_total{result=bad_password}` —
  and that is the series `AccessControlLoginBruteForce` fires on. Without the counter, a working
  limiter makes the alert *quieter*, and the more effective it is the more it looks like nothing is
  happening.
- This is not a cache and does not touch ADR-0022. It holds no authentication result, permission
  decision, key scope, role binding or session — only counts of attempts. Nothing here can return a
  stale allow, because it can only produce a *denial*.

## Alternatives rejected

**A PostgreSQL counter table.** The only option that stays correct across processes, which matters if
A-130's gateway split happens, and it survives restarts. Rejected because it puts a **write on every
failed login** — an unauthenticated, unthrottled write path into the one resource the entire product
depends on. That is an amplifier pointed at the wrong target: an attacker who cannot guess a password
can still make Prope write rows, and PostgreSQL on this host is also serving the gateway. It also needs
a pruning job, and A-012 has priced every additional scheduled job as real cost throughout.

**Rate limiting at Caddy.** A-129 makes Caddy the single ingress, so it is the structurally correct
chokepoint and would protect the `app` process from ever seeing the request. Rejected on two concrete
costs. Caddy's `rate_limit` is a third-party module requiring an `xcaddy` build, so ADR-0031's pipeline
— *"the host pulls a published image and never builds"* — would now have to produce and maintain a
custom proxy image, for one feature. And Caddy sees the request, not the request body: **per-source is
expressible and per-email is not**, so half of the lock's stated requirement would remain unimplemented
while appearing to be handled.

**`argon2-cffi`'s library defaults, `t=3 · m=64 MiB · p=4`.** Strongest of the three on paper and
requires writing no configuration at all — which is exactly the failure, since a default that is not
written down is a default nobody defends when it changes. Rejected on hardware: `p=4` on 4 vCPU makes a
single login a full-box event inside the process A-130 already flags, and `t=3` triples the wall time
for no recognised gain at that memory level. It would put sign-in near the 500 ms target under trivial
concurrency, which is the condition that produces the tuning-down failure the lock predicted.

## Consequences

- **The 500 ms target becomes a floor-shaped ceiling with a number behind it.** The lock's tuning-down
  failure mode now cites `m=47104, t=1, p=1` and this ADR, so lowering it is a decision against a
  written one rather than an edit to an unexplained constant.
- Memory is bounded by the limiter rather than by hope: 46 MiB is transient per in-flight verification,
  realistic pilot concurrency is one to three logins, and the attack case is capped before allocation.
  The `app` container's `mem_limit` (ADR-0033) must carry that headroom explicitly.
- **The limiter is per-process, so A-130's split doubles the effective limit.** Two `app` processes mean
  two independent windows and twice the attempts admitted. Recorded as a failure mode in the lock with
  A-130's split as its trigger; the fix at that point is the counter table rejected above, which becomes
  correct once the reason to avoid it — a single process — no longer holds.
- A deploy resets the windows. Deploys are ADR-0031 pulls, not attacker-triggered, so the lost window is
  not a control an attacker can exercise; it is noted rather than mitigated.
- Prope now writes down the cost of both of its hashes and the reason each is what it is: fast and
  indexed for consumer keys, slow and memory-hard for passwords (ADR-0021). Anyone comparing the two in
  the same module has both answers.
