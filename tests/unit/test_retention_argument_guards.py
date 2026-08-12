"""WARN-1: ``delete_expired_bodies`` refuses an out-of-range bound, before it runs.

With ``chunk_size=0`` the delete statement removes nothing, the short-chunk exit
tests ``0 < 0`` and is false, and ``max_chunks`` defaults to ``None`` — so the
loop opens a transaction per iteration and never ends. Phase 1's verifier logged
it as WARN-1 and scoped the fix to "before Phase 2 wires an operator-supplied
value", which D-12's retention scheduler (plan 02-03) is.

**Both tests prove the refusal happens before any transaction opens**, and they
prove it structurally rather than by timing: the ``sessionmaker`` handed in is an
object that raises the moment anything calls it. ``workspace_transaction`` calls
``sessionmaker()`` as its first act, so a guard placed after the loop began would
surface as that ``AssertionError`` instead of the ``ValueError`` under test.

Asserting "it did not hang" is not available to a test — a test that hangs does
not fail, it stops the suite — which is why the assertion is about the argument
check rather than about the loop.
"""

import pytest

from prope.call_ledger.retention import delete_expired_bodies
from tests.unit import WORKSPACE_A, day


class _ExplodingSessionmaker:
    """Stands in for ``async_sessionmaker`` and refuses to be used.

    ``workspace_transaction`` opens with ``async with sessionmaker() as session``,
    so reaching the loop at all trips this.
    """

    def __call__(self, *args: object, **kwargs: object) -> object:
        raise AssertionError(
            "delete_expired_bodies opened a transaction before validating its arguments"
        )


@pytest.mark.parametrize("chunk_size", [0, -1, -5_000])
async def test_a_chunk_size_below_one_is_refused(chunk_size):
    """The value and the argument name are both in the message.

    An operator reading a log line needs to know which knob they turned and what
    they turned it to; "invalid argument" would send them to the source.
    """
    with pytest.raises(ValueError) as excinfo:
        await delete_expired_bodies(
            _ExplodingSessionmaker(),  # type: ignore[arg-type]
            WORKSPACE_A,
            now=day(30),
            chunk_size=chunk_size,
        )

    message = str(excinfo.value)
    assert "chunk_size" in message
    assert str(chunk_size) in message


@pytest.mark.parametrize("max_chunks", [0, -1])
async def test_a_max_chunks_below_one_is_refused(max_chunks):
    """``None`` is how a caller asks for an unbounded run. Zero is not a smaller
    version of that — it is a bound the loop cannot honour, because the first
    chunk executes before the bound is tested."""
    with pytest.raises(ValueError) as excinfo:
        await delete_expired_bodies(
            _ExplodingSessionmaker(),  # type: ignore[arg-type]
            WORKSPACE_A,
            now=day(30),
            max_chunks=max_chunks,
        )

    message = str(excinfo.value)
    assert "max_chunks" in message
    assert str(max_chunks) in message


async def test_max_chunks_none_is_not_caught_by_the_guard(app_sessionmaker):
    """The negative control: the unbounded run must still be reachable.

    A guard written as ``if max_chunks < 1`` would raise ``TypeError`` on the
    default, which is every production call site. Running the real function
    against an empty table is the cheapest proof that the default path is intact
    — it does one chunk, finds nothing, and returns 0.
    """
    assert await delete_expired_bodies(app_sessionmaker, WORKSPACE_A, now=day(30)) == 0


async def test_the_smallest_legal_bounds_are_accepted(app_sessionmaker):
    """One row per chunk and one chunk is a real, if slow, configuration.

    The boundary belongs to the accepted side, and asserting it stops the guard
    from being tightened to ``> 1`` by somebody reading ``< 1`` as "too small".
    """
    assert (
        await delete_expired_bodies(
            app_sessionmaker, WORKSPACE_A, now=day(30), chunk_size=1, max_chunks=1
        )
        == 0
    )
