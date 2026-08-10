"""RESEARCH Pitfall 8: the month is one function, and it answers in UTC.

``write_records`` files a record under the first day of its own ``created_at``'s
month; ``check_spend_ceiling`` (plan 02-04) has no record and must pick a month
for itself. If those two ever derived it differently they would disagree for up
to a day at every month boundary — and invisibly, because each side would be
internally consistent while reading a different row of
``ledger.workspace_spend``, whose key is ``(workspace_id, period_month)``.

**This file pins the helper, not the callers.** A test that wrote a record and
then read the ceiling would pass for either of two reasons — the helper is
correct, or both callers are wrong in the same direction — and only one of those
is the property. Pinning ``period_month`` itself means a second implementation
appearing anywhere is a change to a function with a test on it.

The two cases that matter are the ones where a local month and the UTC month
disagree: the last instant of a month in a positive offset (already the next
month locally, still this month in UTC) and the last instant in a negative offset
(still this month locally, already the next in UTC). Both must answer by UTC.
"""

from datetime import UTC, date, datetime, timedelta, timezone

from prope.call_ledger.writer import period_month

#: Indochina Time. Chosen rather than invented: ADR-0053 ships a Vietnamese-only
#: interface, so +07:00 is the offset this project's operators actually live in
#: and the one a wall-clock mistake would be made in.
ICT = timezone(timedelta(hours=7))

#: A negative offset, for the mirror case. UTC-05:00.
EST = timezone(timedelta(hours=-5))


def test_a_plain_utc_instant_resolves_to_the_first_of_its_own_month():
    """The ordinary case, so the boundary cases below have a control."""
    assert period_month(datetime(2026, 9, 17, 13, 45, tzinfo=UTC)) == date(2026, 9, 1)


def test_the_first_instant_of_a_utc_month_belongs_to_that_month():
    """Midnight on the first is inside the month it opens, not the one it closes."""
    assert period_month(datetime(2026, 9, 1, 0, 0, tzinfo=UTC)) == date(2026, 9, 1)


def test_the_last_instant_of_a_utc_month_belongs_to_that_month():
    assert period_month(datetime(2026, 8, 31, 23, 59, 59, 999999, tzinfo=UTC)) == date(2026, 8, 1)


def test_the_last_day_of_a_month_in_a_positive_offset_files_by_utc():
    """01 September 2026, 05:00 in +07:00 is 31 August 2026, 22:00 UTC.

    Locally this is September. The record files under August, because that is
    when it happened in the time zone every stored ``timestamptz`` is compared
    in. A helper that relabelled the instant instead of converting it would
    answer September here, and the ceiling read would then look at a row the
    writer never touched.
    """
    assert period_month(datetime(2026, 9, 1, 5, 0, tzinfo=ICT)) == date(2026, 8, 1)


def test_the_last_day_of_a_month_in_a_negative_offset_files_by_utc():
    """31 August 2026, 21:00 in -05:00 is 01 September 2026, 02:00 UTC.

    The mirror of the case above, and the reason both are written: a helper that
    happened to be correct for one offset and wrong for the other would pass a
    single-direction test.
    """
    assert period_month(datetime(2026, 8, 31, 21, 0, tzinfo=EST)) == date(2026, 9, 1)


def test_two_instants_that_are_the_same_moment_in_different_offsets_agree():
    """The property stated directly: the answer is a function of the instant.

    Not of how the instant was spelled. This is what makes "the writer and the
    ceiling read file into the same month" a fact about ``period_month`` rather
    than about the callers happening to construct their datetimes alike.
    """
    same_moment = (
        datetime(2026, 8, 31, 22, 0, tzinfo=UTC),
        datetime(2026, 9, 1, 5, 0, tzinfo=ICT),
        datetime(2026, 8, 31, 17, 0, tzinfo=EST),
    )

    answers = {period_month(instant) for instant in same_moment}

    assert answers == {date(2026, 8, 1)}


def test_january_first_in_a_positive_offset_files_under_the_previous_december():
    """The year rolls with the month, which a naive ``date(at.year, ...)`` on an
    unconverted value would get wrong in exactly one direction once a year."""
    assert period_month(datetime(2027, 1, 1, 3, 0, tzinfo=ICT)) == date(2026, 12, 1)
