---
created: 2026-08-10T12:42:42.681Z
title: Reuse a long-lived RabbitMQ for broker tests
area: testing
severity: minor
files:
  - tests/conftest.py:182-209
  - tests/conftest.py:212-237
  - tests/broker/test_declared_arguments.py
  - docker-compose.yml
---

## Problem

Every `pytest` invocation that touches the broker boots a fresh `rabbitmq:4.3-management`
container and tears it down at session end (`tests/conftest.py:182-193`, via
`with container as running:`). Across a GSD phase — where ~8 subagents each run pytest many
times for TDD red/green cycles — that boot cost repeats dozens of times.

**The obvious fix is unavailable.** testcontainers-python **4.15.0** (the pinned version) has
**no `with_reuse()` method** on `DockerContainer` and no `testcontainers_reuse_enable` config
key — verified empirically against the installed package, not assumed. The only related knob
present is `ryuk_disabled`. So the standard `TESTCONTAINERS_REUSE_ENABLE=true` + `.with_reuse()`
recipe cannot be applied here.

**Scope this to RabbitMQ only.** The Postgres fixture must stay pristine: its docstring promises
"A pristine PostgreSQL 17 with the chain applied", and this suite's assertions are largely *about*
database state — RLS tenant isolation returning zero rows, append-only privileges, the migration
chain itself. A reused Postgres would carry the prior run's rows and an already-migrated schema
into `_upgrade_to_head`, trading correctness for speed in the one place correctness is the subject.

**Expected payoff is moderate and must be measured, not assumed.** The RabbitMQ fixture is
session-scoped *and* lazy — pytest only instantiates a session fixture when something requests it,
so unit-only runs never boot a broker at all. RabbitMQ boots in roughly 10-20s. Realistic saving
is on the order of 10-25 min per phase. If a measurement shows less, close this rather than
building it.

**Not to be confused with the cold-pull cost.** Phase 2's verifier lost ~78 minutes to Docker
pulling `postgres:17` and `rabbitmq:4.3-management` for the first time. Those images are cached
now and that cost will not recur. This todo does not address it and should not be credited with it.

## Solution

Prefer an externally-run broker when one is offered; otherwise fall back to today's behavior.

1. **Env-var opt-in.** Have `amqp_url` / `management_url` (`tests/conftest.py:196-209`) read
   something like `PROPE_TEST_AMQP_URL` (plus a management counterpart, since the two ports are
   derived separately). When set, use it and never construct a container. When unset, fall back to
   the current `rabbitmq_container` fixture unchanged. The broker comes from the project's
   docker-compose, which ADR-0033 already mandates for the runtime — no new infrastructure.

   Preferred over hand-rolled container reuse (`with_name()` + `ryuk_disabled` + code to rediscover
   an existing container's mapped ports), which is ~50 lines and leaves an unowned container
   lifecycle for the developer to clean up by hand.

2. **Close the crash-leak gap.** The autouse `purge_queues` fixture (`tests/conftest.py:212-237`)
   already declares then purges both `prope.call_record` and its DLQ — but it is *teardown-only*
   (`yield` first). Within one session that is equivalent to purging up front; across sessions it
   is not. A run killed mid-test (SIGKILL, a timeout, a failed executor) leaves messages that the
   next session inherits before its first broker test runs. Add a session-scoped pre-purge, or
   purge on both sides of the yield.

3. **Keep CI on throwaway containers.** CI gets a fresh runner every time, so the external path
   buys nothing there and risks cross-job contamination if a shared broker ever appears. Ensure
   the env var is unset in CI, and assert that rather than assuming it.

4. **Re-verify the negative control.** `tests/broker/test_declared_arguments.py` asserts that a
   `quorum` redeclare is refused with `PRECONDITION_FAILED` (406). Against a long-lived broker the
   queue reliably pre-exists, which should make the assertion *stronger*, not weaker — but confirm
   it, since the whole `classic-durable` / `reject-publish-dlx` decision (a one-way user decision
   from plan 02-01) rests on that declaration being what the test says it is.

5. **Measure before and after.** Record wall-clock for a full `uv run pytest -q` under both paths.
   The 292-test suite took 240s at the end of Phase 2; if the external broker does not move that
   meaningfully, the task has failed its own premise.
