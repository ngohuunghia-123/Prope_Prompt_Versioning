"""argon2id at ADR-0043's written cost, and a verify that always runs.

**The parameters are named, never inherited, and the library is pinned.**
`argon2-cffi`'s defaults are `t=3, m=64 MiB, p=4`; two of those three terms are
wrong for ADR-0033's 4 vCPU / 8 GB host, and they have already changed once
between releases. So :data:`HASHER` is constructed with all three arguments
spelled out, and `pyproject.toml` pins the version — a default that is not
written down is a default nobody defends when it moves.

**`parallelism=1` is the load-bearing one.** On four cores, `p=4` makes a single
login a full-box event inside the process A-130 says also serves the gateway.
The other two follow OWASP's first-choice argon2id configuration and land at
roughly 55–70 ms per verification, about 12% of the 500 ms sign-in target. That
headroom is deliberate: the number must never be the reason somebody reaches for
the cost parameter, and the failure mode the lock file predicts —
*"argon2id's cost parameter is tuned down because the login screen feels slow"* —
now points at a written decision rather than at an unexplained constant.

**Verification always runs, even when there is nothing to verify.** That is this
module's second job and the harder one to keep. A-144 and ADR-0043 require an
unknown email, a wrong password and a **tombstoned** account to be
indistinguishable — byte-identical *and* timing-identical. A `if user is None:
return False` before the hash would leak account existence through a 60 ms
difference that any client can measure, so :func:`verify` takes an *optional*
hash and burns the same work against :data:`_ABSENT_ACCOUNT_HASH` when it is
`None`. There is deliberately no fast path, and
`tests/security/test_login_responses_are_indistinguishable.py` asserts there is
none.

A-151 makes the tombstone rely on exactly that: it sets `password_hash` to NULL,
and a NULL hash is *"a no-match that STILL RUNS THE HASH COMPARISON"*.
"""

import argon2
from argon2.exceptions import InvalidHashError, VerifyMismatchError

__all__ = [
    "MEMORY_COST_KIB",
    "PARALLELISM",
    "TIME_COST",
    "hash_password",
    "needs_rehash",
    "verify",
]

#: 46 MiB. OWASP's first-choice argon2id memory parameter, and the term that does
#: the actual work — argon2's resistance is bought with memory, not with time.
MEMORY_COST_KIB = 47104

#: One pass. Raising it multiplies wall time for no recognised gain at this
#: memory level, and would put sign-in near the 500 ms target under trivial
#: concurrency — which is the condition that produces the tuning-down failure.
TIME_COST = 1

#: One lane, explicitly **not** the library's default of four. See the module
#: docstring: A-130 puts the gateway in this process and ADR-0033 gives it four
#: cores.
PARALLELISM = 1

#: Constructed once at import, with every argument named. A module-level hasher
#: rather than one per call because the object is stateless and a per-login
#: construction would be a per-login opportunity to pass different numbers.
HASHER = argon2.PasswordHasher(
    memory_cost=MEMORY_COST_KIB,
    time_cost=TIME_COST,
    parallelism=PARALLELISM,
)

#: The hash :func:`verify` burns against when there is no account, or when the
#: account is tombstoned and its `password_hash` is NULL.
#:
#: Computed at import from a value no login can present — the empty string is not
#: a password any route accepts — so the work is done once at startup rather than
#: on the first unknown-email attempt. Computing it lazily would make the FIRST
#: such attempt slower than the rest, which is the timing oracle this constant
#: exists to close, arriving by a side door.
#:
#: It is a real argon2id hash at the same cost as every other one in the system,
#: because a cheaper stand-in would be a shorter code path and the whole point is
#: that the two paths cost the same.
_ABSENT_ACCOUNT_HASH = HASHER.hash("")


def hash_password(password: str) -> str:
    """The stored form. Never logged, never returned by any read API (A-046)."""
    return HASHER.hash(password)


def verify(stored_hash: str | None, password: str) -> bool:
    """Whether `password` matches. **Runs the same work whichever way it answers.**

    `stored_hash` is `None` for an account that does not exist and for one that
    has been tombstoned (A-151). Both cases verify against
    :data:`_ABSENT_ACCOUNT_HASH` and return `False` — the comparison is performed
    rather than skipped, so an attacker timing the endpoint learns nothing about
    which of the three failures they hit.

    `InvalidHashError` is caught for the same reason rather than allowed to
    propagate: a corrupt or truncated hash in the column would otherwise be a
    500 where every neighbouring failure is a 401, which is an oracle for
    "this row exists and is damaged".

    Returns a plain `bool`. Whether to rehash is :func:`needs_rehash`'s question
    and is asked only after a success, so a failed login never touches the row.
    """
    if stored_hash is None:
        # The result is discarded; the CPU time is the point.
        try:
            HASHER.verify(_ABSENT_ACCOUNT_HASH, password)
        except (VerifyMismatchError, InvalidHashError):
            pass
        return False

    try:
        return HASHER.verify(stored_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    """Whether this hash was made at a cost below the current one (ADR-0043).

    Called on **every successful** login, so raising the cost later migrates
    hashes as people sign in — a configuration change rather than a migration,
    and the reason the parameters above can be revised at all.

    A malformed hash answers `True`: it cannot be verified against and the
    caller has just proved the password, so re-writing it is both safe and the
    only way the row ever becomes usable again.
    """
    try:
        return HASHER.check_needs_rehash(stored_hash)
    except InvalidHashError:
        return True
