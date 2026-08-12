"""A-015's diff, at the scope of one function. No database, no route.

The one test here that is not about output shape is
:func:`test_autojunk_is_disabled_and_it_changes_the_answer`, and it is the reason
this file exists. ``SequenceMatcher``'s ``autojunk`` heuristic silently discards
lines appearing in more than 1% of a sequence longer than 200 elements — which,
on a prompt body full of blank lines or ``- `` bullets, is exactly the lines a
reviewer is looking at. The result is a diff that looks WRONG rather than slow,
and a reviewer who approves a change they did not see is the failure the whole
review screen exists to prevent.

That test drives the two settings side by side and asserts they DISAGREE. A test
that merely checked ``autojunk=False`` appeared in the source would pass over a
version of the library where the flag stopped meaning anything.
"""

from datetime import UTC, datetime
from difflib import SequenceMatcher

from prope.prompt_registry.diff import COMPARED_FIELDS, compute_diff, render_value
from prope.prompt_registry.domain import LineOp, RevisionRead, RevisionStatus


def _revision(body: str, **overrides: object) -> RevisionRead:
    values: dict[str, object] = {
        "version_id": "rev_01J000000000000000000001",
        "prompt_id": "prm_01J000000000000000000001",
        "workspace_id": "wsp_01J000000000000000000001",
        "revision_number": 1,
        "body": body,
        "provider_config_id": None,
        "upstream_model": None,
        "parameters": {},
        "fallback_answer": None,
        "change_summary": "a summary",
        "author_id": "usr_01J000000000000000000001",
        "status": RevisionStatus.DRAFT,
        "created_at": datetime(2026, 8, 1, tzinfo=UTC),
    }
    values.update(overrides)
    return RevisionRead(**values)  # type: ignore[arg-type]


def test_an_unchanged_body_is_all_equal_lines() -> None:
    result = compute_diff(_revision("one\ntwo"), _revision("one\ntwo"))

    assert [line.op for line in result.lines] == [LineOp.EQUAL, LineOp.EQUAL]
    assert [line.from_line for line in result.lines] == [1, 2]
    assert [line.to_line for line in result.lines] == [1, 2]


def test_a_replaced_line_is_a_removal_and_an_addition() -> None:
    """Not a single ``changed`` op, because a reviewer reads both texts.

    ``difflib`` calls it ``replace``; the renderer splits it, so the screen can
    show the old line struck through above the new one rather than asking the
    reader to diff two strings in their head.
    """
    result = compute_diff(_revision("one\ntwo"), _revision("one\ndeux"))

    assert [line.op for line in result.lines] == [LineOp.EQUAL, LineOp.REMOVED, LineOp.ADDED]
    assert result.lines[1].text == "two"
    assert result.lines[1].to_line is None
    assert result.lines[2].text == "deux"
    assert result.lines[2].from_line is None


def test_line_numbers_are_one_based_on_the_side_they_exist_on() -> None:
    """An added line has a ``to_line`` and no ``from_line``, and vice versa.

    Both numbers on both sides would be a lie about a line that exists in one
    document, and neither would make the diff unrenderable beside a body.
    """
    result = compute_diff(_revision("a\nb\nc"), _revision("a\nc"))

    removed = [line for line in result.lines if line.op is LineOp.REMOVED]
    assert [line.text for line in removed] == ["b"]
    assert removed[0].from_line == 2
    assert removed[0].to_line is None


def test_windows_and_unix_line_endings_are_not_a_change() -> None:
    """``splitlines`` rather than ``split('\\n')``.

    A prompt body is human-authored text pasted from somewhere else, so it
    arrives with whatever line endings that somewhere used. ``split`` would
    render every line of a Windows-authored body as changed against a
    Unix-authored one, on a screen whose whole job is to show what changed.
    """
    result = compute_diff(_revision("one\r\ntwo"), _revision("one\ntwo"))

    assert {line.op for line in result.lines} == {LineOp.EQUAL}


def test_autojunk_is_disabled_and_it_changes_the_answer() -> None:
    """The library-level claim, driven rather than read off the source.

    A 300-line body of repeated bullets with **one line inserted in the middle** —
    a prompt with a long list of examples, which is most long prompts. Every line
    is "popular" by the heuristic's definition, so with ``autojunk`` on the
    matcher declares HALF THE DOCUMENT replaced; with it off it reports one
    inserted line and 299 unchanged ones.

    That is the whole argument, and the numbers are asserted rather than the
    flag: 150 changed lines against 1 is not a slower diff, it is a diff that
    would make a reviewer approve a change they could not see.
    """
    before = ["- an example"] * 300
    after = list(before)
    after.insert(150, "- a new example")

    honest = SequenceMatcher(a=before, b=after, autojunk=False).get_opcodes()
    heuristic = SequenceMatcher(a=before, b=after, autojunk=True).get_opcodes()

    assert honest != heuristic
    assert [tag for tag, *_ in honest] == ["equal", "insert", "equal"]
    assert "replace" in [tag for tag, *_ in heuristic]

    result = compute_diff(_revision("\n".join(before)), _revision("\n".join(after)))

    assert len([line for line in result.lines if line.op is LineOp.EQUAL]) == 300
    assert len([line for line in result.lines if line.op is LineOp.ADDED]) == 1
    assert [line for line in result.lines if line.op is LineOp.REMOVED] == []


def test_trimming_the_common_ends_does_not_change_the_answer() -> None:
    """The optimisation that makes ``autojunk=False`` affordable, checked for loss.

    Equal leading and trailing lines are peeled off before ``SequenceMatcher``
    sees anything, which turns the 1.2 s case into 5 ms. It is only sound if it
    is invisible, so the invariants are asserted rather than the timing: every
    line of the ``from`` body appears exactly once as equal or removed, every
    line of the ``to`` body exactly once as equal or added, and every line number
    points at the text it claims.
    """
    before = ["- an example"] * 400
    after = list(before)
    after[200] = "- a different example"
    after.insert(0, "a new opening")

    result = compute_diff(_revision("\n".join(before)), _revision("\n".join(after)))

    equal = [line for line in result.lines if line.op is LineOp.EQUAL]
    removed = [line for line in result.lines if line.op is LineOp.REMOVED]
    added = [line for line in result.lines if line.op is LineOp.ADDED]

    assert len(equal) + len(removed) == len(before)
    assert len(equal) + len(added) == len(after)

    for line in result.lines:
        if line.op is LineOp.EQUAL:
            assert before[line.from_line - 1] == line.text == after[line.to_line - 1]
        elif line.op is LineOp.REMOVED:
            assert before[line.from_line - 1] == line.text
            assert line.to_line is None
        else:
            assert after[line.to_line - 1] == line.text
            assert line.from_line is None


def test_a_body_that_is_entirely_one_repeated_line_is_not_counted_twice() -> None:
    """The trim's own edge: the prefix and the suffix would overlap.

    Without the bound, a body equal to itself would have every line counted once
    as a common prefix and again as a common suffix, and the review screen would
    show a document twice as long as either revision.
    """
    body = "\n".join(["- an example"] * 9)

    result = compute_diff(_revision(body), _revision(body))

    assert len(result.lines) == 9
    assert {line.op for line in result.lines} == {LineOp.EQUAL}
    assert [line.from_line for line in result.lines] == list(range(1, 10))


def test_an_empty_body_on_either_side_is_all_added_or_all_removed() -> None:
    """The first revision of a prompt has nothing before it, and the diff runs anyway."""
    added = compute_diff(_revision(""), _revision("one\ntwo"))
    removed = compute_diff(_revision("one\ntwo"), _revision(""))

    assert [line.op for line in added.lines] == [LineOp.ADDED, LineOp.ADDED]
    assert [line.op for line in removed.lines] == [LineOp.REMOVED, LineOp.REMOVED]


def test_the_field_comparison_covers_exactly_the_four_a_015_names() -> None:
    """Provider, upstream model, parameters, fallback answer — in that order.

    A tuple rather than a set because the order is part of the contract: a
    reviewer who reads the same screen twice should read it the same way.
    """
    result = compute_diff(_revision("x"), _revision("x"))

    assert [change.field for change in result.fields] == list(COMPARED_FIELDS)
    assert COMPARED_FIELDS == (
        "provider_config_id",
        "upstream_model",
        "parameters",
        "fallback_answer",
    )
    assert all(not change.changed for change in result.fields)


def test_parameters_render_with_sorted_keys() -> None:
    """Two revisions that set the same parameters in a different order are the same.

    Python preserves insertion order in a dict and JSON does not care, so an
    unsorted render would show a change nobody made — on the one field where a
    reviewer is least able to tell a real difference from a cosmetic one.
    """
    before = _revision("x", parameters={"temperature": 0.2, "top_p": 1})
    after = _revision("x", parameters={"top_p": 1, "temperature": 0.2})

    changed = [change for change in compute_diff(before, after).fields if change.changed]

    assert changed == []


def test_a_none_value_renders_as_none_and_not_as_the_string() -> None:
    """``"None"`` in a response is a value the SPA would render as text.

    The absence of a fallback answer is not the four characters ``None``, and a
    reviewer seeing that on a screen has been told something false.
    """
    assert render_value(None) is None
    assert render_value("") == ""
    assert render_value(0) == "0"
