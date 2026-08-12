"""A-144's login limiter: 5 per email, 20 per source address, rolling 15 minutes.

**Its real job is not to protect the password.** ADR-0043 says so plainly: it
exists to bound *how much argon2id this box is willing to run*. One verification
allocates 46 MiB and a core for 55–70 ms, inside a process A-130 says also serves
the gateway on a 4-vCPU host. An unthrottled login endpoint is therefore a memory
and CPU amplifier pointed at the one process every request in Prope passes
through — and that only gets fixed if the limiter **rejects before the hash**,
which is why :func:`check` takes no password and knows nothing about accounts.

**In-process, not Redis and not a table.** A-080 and A-114 already forbid Redis
its two natural jobs here and ADR-0033 fixed the host at seven services; a
PostgreSQL counter table would put an **unauthenticated, unthrottled write** into
the one resource the whole product depends on, which is the amplifier again
wearing a different hat. ADR-0043 rejected both by name.

**Not a cache, and ADR-0022 is untouched.** Nothing here holds an authentication
result, a permission decision, a key scope, a role binding or a session — only
counts of attempts. It can produce a *denial* and can never produce a stale
allow, which is the only direction ADR-0022 cares about.

**It counts per process, so A-130's gateway split doubles it.** Two `app`
services mean two independent windows and twice the attempts admitted, and no
metric shows it — `login_rate_limited_total` keeps counting normally per process
and the aggregate simply permits more. **The second `app` service appearing in
the compose file IS the detection.** ADR-0043 names the fix and it is the option
ADR-0043 itself rejected: the counter table becomes correct at exactly the moment
its reason for rejection stops holding. Recorded here so the split is not taken
without also moving this file.

A deploy resets the windows. Deploys are ADR-0031 pulls rather than
attacker-triggered, so the lost window is not a control an attacker can exercise.
"""

import time
from collections import OrderedDict, deque
from enum import StrEnum

from prope.access_control.observability import login_rate_limited_total

__all__ = [
    "MAX_TRACKED_KEYS",
    "PER_EMAIL_FAILURES",
    "PER_SOURCE_FAILURES",
    "WINDOW_SECONDS",
    "LoginLimiter",
    "LimiterBucket",
    "limiter",
]


class LimiterBucket(StrEnum):
    """The two things a window is keyed on. A-144 names both and no third.

    They bound different attacks and that is why there are two: `EMAIL` bounds a
    search against one account from anywhere, `SOURCE_ADDRESS` bounds a spray
    across many accounts from one place. A single combined key would let either
    attack run at the other's budget.
    """

    EMAIL = "email"
    SOURCE_ADDRESS = "source_address"


#: A-144, decided by the user on 2026-08-09. Before that date this module's spec
#: committed to a limiter twice and named no number anywhere in the repository,
#: which is a blank an implementer fills.
PER_EMAIL_FAILURES = 5
PER_SOURCE_FAILURES = 20

#: Rolling, not fixed. A fixed 15-minute bucket lets an attacker spend the whole
#: allowance at 14:59 and the whole next allowance at 15:01 — twice the rate at
#: the boundary, which is the one moment a script is most likely to be running.
WINDOW_SECONDS = 15 * 60

#: The bound that makes "bounded in-process structure" true rather than aspirational
#: (ADR-0043). Without it, an attacker spraying unique source addresses or unique
#: email strings grows this dict without limit — turning a defence against a memory
#: amplifier into a memory amplifier. Eviction is least-recently-touched, and the
#: number is generous relative to the pilot's population precisely so that eviction
#: is an attack response rather than an everyday event.
MAX_TRACKED_KEYS = 4096


class LoginLimiter:
    """Sliding windows over `(bucket, key)`, with a cap on how many keys are kept.

    A class rather than module-level dicts so a test can hold its own instance
    and so the process-wide one below is a deliberate singleton rather than an
    accident of import. Not thread-safe and does not need to be: uvicorn runs one
    event loop per process, and every method here is synchronous and completes
    without awaiting — so no two attempts interleave inside one.

    **Time is a parameter, never a call to `time.monotonic()` inside a branch.**
    Every method takes `now`, and :func:`_now` is the one default. A limiter that
    read the clock in three places would be a limiter whose window edges could
    not be tested without sleeping, and a test that sleeps for fifteen minutes is
    a test nobody runs.
    """

    __slots__ = ("_limits", "_max_keys", "_window", "_windows")

    def __init__(
        self,
        *,
        per_email: int = PER_EMAIL_FAILURES,
        per_source: int = PER_SOURCE_FAILURES,
        window_seconds: float = WINDOW_SECONDS,
        max_keys: int = MAX_TRACKED_KEYS,
    ) -> None:
        self._limits = {
            LimiterBucket.EMAIL: per_email,
            LimiterBucket.SOURCE_ADDRESS: per_source,
        }
        self._window = window_seconds
        self._max_keys = max_keys
        #: Insertion-ordered so eviction is O(1) at the cold end. The value is a
        #: deque of failure timestamps, trimmed from the left as it ages.
        self._windows: OrderedDict[tuple[LimiterBucket, str], deque[float]] = OrderedDict()

    def check(
        self, *, email: str, source_address: str, now: float | None = None
    ) -> LimiterBucket | None:
        """The bucket that is over its limit, or `None` to proceed. **Reads only.**

        Called **before the user row is read and before any hash is computed**
        (ADR-0043). It therefore takes the email as an opaque string and never
        asks whether an account exists — which is also what keeps a rate-limited
        attempt timing-identical to an unknown one, since neither path reaches
        the hasher.

        Recording the attempt is :meth:`record_failure`'s job and happens only
        once the outcome is known. Counting here instead would make a *successful*
        login consume budget, so a person with a slow typing finger and one
        correct attempt would still be locked out.

        Returns which bucket refused, so the caller can label
        `login_rate_limited_total` — the counter exists because the limiter
        rejects before the hash, and rejections that precede the hash never reach
        `login_total`, which is the series `AccessControlLoginBruteForce` fires
        on. Without it a working limiter makes that alert *quieter*.
        """
        moment = _now() if now is None else now
        for bucket, key in ((LimiterBucket.EMAIL, email), (LimiterBucket.SOURCE_ADDRESS, source_address)):
            attempts = self._windows.get((bucket, key))
            if attempts is None:
                continue
            self._trim(attempts, moment)
            if len(attempts) >= self._limits[bucket]:
                login_rate_limited_total.labels(bucket=bucket.value).inc()
                return bucket
        return None

    def record_failure(self, *, email: str, source_address: str, now: float | None = None) -> None:
        """Count one failed attempt against both windows.

        Both, always. A failure that only counted against the email would let a
        spray across many accounts from one address run forever; one that only
        counted against the address would let a distributed search on one account
        do the same.
        """
        moment = _now() if now is None else now
        for bucket, key in ((LimiterBucket.EMAIL, email), (LimiterBucket.SOURCE_ADDRESS, source_address)):
            attempts = self._windows.get((bucket, key))
            if attempts is None:
                attempts = deque()
                self._windows[(bucket, key)] = attempts
                self._evict_if_full()
            else:
                self._windows.move_to_end((bucket, key))
            self._trim(attempts, moment)
            attempts.append(moment)

    def record_source_failure(self, *, source_address: str, now: float | None = None) -> None:
        """Count one failed attempt against the **source address only**.

        `POST /api/v1/auth/register` is the caller, and using
        :meth:`record_failure` there would be a vulnerability rather than a
        stricter setting: registration takes an email from an unauthenticated
        stranger, so five attempts to register `someone@a-real-company.com` would
        fill that email's window and lock the person who **owns** it out of
        signing in. An account-lockout primitive handed to anybody who can reach
        the port is worse than the bulk-probing this bounds.

        The source-address window is shared with sign-in on purpose. Both routes
        are unauthenticated doors on the same process, and an attacker who has
        spent their twenty guesses on one has not earned twenty more on the other.
        """
        moment = _now() if now is None else now
        key = (LimiterBucket.SOURCE_ADDRESS, source_address)
        attempts = self._windows.get(key)
        if attempts is None:
            attempts = deque()
            self._windows[key] = attempts
            self._evict_if_full()
        else:
            self._windows.move_to_end(key)
        self._trim(attempts, moment)
        attempts.append(moment)

    def clear_email(self, email: str) -> None:
        """Forget an email's window. Called on a **successful** sign-in (A-144).

        The source-address window is deliberately **not** cleared. One correct
        password proves the person at this address knows one account's
        credentials; it does not license the next nineteen guesses from the same
        place, and an attacker who owns one valid account would otherwise hold a
        reset button for the spray budget.
        """
        self._windows.pop((LimiterBucket.EMAIL, email), None)

    def _trim(self, attempts: deque[float], now: float) -> None:
        """Drop timestamps older than the window. This is the "rolling" part."""
        cutoff = now - self._window
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()

    def _evict_if_full(self) -> None:
        """Drop least-recently-touched keys until the cap holds.

        Eviction *forgets failures*, so it is an allow-direction operation and
        worth being honest about: an attacker who can force eviction by spraying
        unique keys can reset a victim's window. The trade is deliberate and it
        is the one ADR-0043's "bounded" requires — the alternative is unbounded
        growth, which hands the same attacker the memory exhaustion the limiter
        exists to prevent, against the same process. `MAX_TRACKED_KEYS` is set
        far above any real population so that reaching it is itself the signal.
        """
        while len(self._windows) > self._max_keys:
            self._windows.popitem(last=False)


def _now() -> float:
    """Monotonic, never wall-clock.

    A window measured on `time.time()` shortens or lengthens when NTP steps the
    clock, and a step backwards would make every recorded attempt appear to be in
    the future — which trims nothing and locks an account out for as long as the
    step. `monotonic()` cannot go backwards and is not comparable across
    processes, which costs nothing here because the limiter is already per
    process.
    """
    return time.monotonic()


#: The process-wide limiter. One per process, which is the whole of A-130's
#: consequence — see the module docstring.
limiter = LoginLimiter()
