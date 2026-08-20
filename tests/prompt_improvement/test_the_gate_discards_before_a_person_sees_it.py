"""AC-4 / SR-3 — a candidate that regresses is discarded, counted, and never rendered.

**This is the control the whole module is built around, and the argument for it
is a non-negotiable.** *No prompt reaches production without a recorded human
approval.* A queue of unvalidated model-authored edits does not break that
sentence — every one of them still needs an approval — it converts it into a
stream of fast, low-information approvals. Ten plausible diffs a week, each
looking reasonable, each approved in four seconds, is a rubber stamp with a
recorded actor on it.

**So the machine goes first.** A candidate runs the prompt's OWN suite before any
person sees it; a candidate that breaks a case which used to pass is discarded,
counted on `prope_improvement_gate_rejected_total{remedy_family}`, and no row is
written. The person's approval is then spent on something that has already
cleared a bar, which is the only version of this feature that makes the approval
worth more rather than less.

**The honest limit is stated everywhere and is stated here too.** *Did not regress
on this suite* is exactly as strong as the suite — the 26/30 → 9/30 collapse.
The gate is a floor, not a proof, and the card says so in Vietnamese
(`improvement.proposal.gateLimit`, asserted in AC-11). What this file proves is
that the floor exists and is load-bearing, not that it is high.

**`None` from the gate is a rejection, not a pass.** A gate that could not run —
no binding, no cases, spend ceiling reached — returns nothing, and the sweep
treats nothing as a refusal. A falsy result read as success is the cheapest
available way to break the one control this module exists around, so it has its
own test.
"""

from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from prope.db.session import workspace_transaction
from prope.evaluation import gate as gate_module
from prope.evaluation.seams import CandidateRevision, score_body_against_suite
from prope.prompt_improvement import repository
from prope.prompt_improvement import sweep as sweep_module
from prope.prompt_improvement.domain import Anomaly, DetectorId, RemedyFamily
from prope.prompt_improvement.observability import gate_rejected_total
from prope.prompt_improvement.triage import Triaged
from prope.prompt_registry.seams import get_revision, list_released_prompts
from tests.evaluation import (
    PROMPT_ID,
    PROVIDER_CONFIG_ID,
    SUITE_ID,
    UPSTREAM_MODEL,
    WORKSPACE_A,
    StubDispatcher,
    allow_ceiling,
    completion,
    day,
    refuse_ceiling,
    seed_bound_revision,
    seed_case,
    seed_case_result,
    seed_owner,
    seed_run,
    seed_suite,
)
from tests.prompt_registry import approve, release, seed_prompt

SESSION_ID = "ses_improvement_gate_00000001"

VERSION_ID = "rev_01J00000000000000GATE001"

FINDING_ID = "fnd_01J0000000000000000GATE1"

CASE_ID = "evc_01J0000000000000000GATE1"

BASELINE_RUN = "evr_01J0000000000000000GATE1"

#: Canonical XML with an interpolation, so `remedies.apply` has a real body to
#: transform and SR-4's round trip is exercised on the way to the gate rather
#: than only in AC-10's unit file.
BODY = (
    "<system>Bạn là trợ lý hỗ trợ khách hàng của ACME.</system>"
    "<instructions>Trả lời câu hỏi {{cau_hoi}} theo đúng chính sách.</instructions>"
)

PROPOSALS = text(
    """
    SELECT id, remedy_kind, remedy_family, candidate_body, gate_run_id, gate_delta
      FROM improvement.proposal
     WHERE prompt_id = :prompt_id
    """
)


def _counter(family: RemedyFamily) -> float:
    value = gate_rejected_total.labels(remedy_family=str(family))._value.get()
    return float(value)


@pytest.fixture
async def a_gateable_prompt(migrate_engine: AsyncEngine) -> None:
    """A released prompt with a suite, one case, and a baseline run that PASSED.

    The baseline matters as much as the suite. With nothing to compare against,
    the gate counts every non-pass as a regression — the conservative direction,
    and the right one — so a test that omitted the baseline would be measuring
    that fallback rather than the comparison it means to measure.
    """
    await seed_owner(migrate_engine, SESSION_ID)
    await seed_prompt(migrate_engine)
    await seed_bound_revision(
        migrate_engine, version_id=VERSION_ID, body=BODY, status="Approved"
    )
    await approve(migrate_engine, VERSION_ID)
    await release(migrate_engine, PROMPT_ID, VERSION_ID)

    await seed_suite(migrate_engine, case_count=1)
    await seed_case(
        migrate_engine,
        CASE_ID,
        prompt="hoi-ve-chinh-sach",
        input_variables='{"cau_hoi": "toi muon hoan tien"}',
        assertions=[{"type": "substring", "value": "in policy"}],
    )
    await seed_run(migrate_engine, BASELINE_RUN, version_id=VERSION_ID, status="completed")
    await seed_case_result(
        migrate_engine,
        "evcr_01J000000000000000GATE1",
        run_id=BASELINE_RUN,
        case_id=CASE_ID,
        outcome="pass",
    )


@pytest.fixture
async def a_finding(app_sessionmaker: async_sessionmaker[AsyncSession]) -> str:
    """One open finding for a detector whose remedy kind is `edit`."""
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        finding_id, _ = await repository.open_or_bump_finding(
            db,
            workspace_id=WORKSPACE_A,
            prompt_id=PROMPT_ID,
            anomaly=Anomaly(
                detector_id=DetectorId.TRUNCATION_RISING,
                params={"share": 0.31, "prior_share": 0.02},
            ),
            evidence_line=None,
            now=day(3),
        )
    return finding_id


def _entry(finding_id: str) -> list[tuple[Triaged, str]]:
    return [
        (
            Triaged(
                anomaly=Anomaly(
                    detector_id=DetectorId.TRUNCATION_RISING,
                    params={"share": 0.31, "prior_share": 0.02},
                ),
                rank=1,
                family=RemedyFamily.ADD_LENGTH_RULE,
            ),
            finding_id,
        )
    ]


async def _propose(
    app_sessionmaker: async_sessionmaker[AsyncSession], finding_id: str
) -> None:
    """Drive the proposal step for one prompt, with the triage result handed in.

    `_propose` rather than `sweep_workspace`, deliberately. The subject here is
    the gate, and reaching it through a full sweep would mean seeding ledger
    traffic to make a detector fire — so a failure in the SQL that summarises a
    window would read as a failure in the control this file is about.

    The prompt row and the revision come from the real seams, not from a stub:
    `remedies.apply` transforms `revision.body`, and a hand-built revision would
    let this file pass against a body no registry would ever have stored.
    """
    async with workspace_transaction(app_sessionmaker, WORKSPACE_A) as db:
        prompts = await list_released_prompts(db, WORKSPACE_A)
        revision = await get_revision(db, VERSION_ID)

    assert len(prompts) == 1, prompts

    await sweep_module._propose(
        app_sessionmaker, WORKSPACE_A, prompts[0], revision, _entry(finding_id), day(3)
    )


async def _proposals(migrate_engine: AsyncEngine) -> list[Any]:
    async with migrate_engine.begin() as connection:
        return (
            (await connection.execute(PROPOSALS, {"prompt_id": PROMPT_ID})).mappings().all()
        )


async def test_a_candidate_that_breaks_a_passing_case_never_reaches_a_row(
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    a_gateable_prompt: None,
    a_finding: str,
) -> None:
    """**The whole control, in one assertion: no row.**

    The suite's one case asserts a substring the candidate's answer does not
    contain, and the baseline said that case passed. So the candidate regressed,
    and a regression is not a proposal a person is asked about — it is discarded
    before it becomes an inbox row, which is what keeps the queue's contents
    worth reading.
    """
    monkeypatch.setattr(gate_module, "dispatch", StubDispatcher(default=completion("nope")))
    monkeypatch.setattr(gate_module, "check_spend_ceiling", allow_ceiling)
    before = _counter(RemedyFamily.ADD_LENGTH_RULE)

    await _propose(app_sessionmaker, a_finding)

    assert await _proposals(migrate_engine) == []
    assert _counter(RemedyFamily.ADD_LENGTH_RULE) == before + 1


async def test_a_candidate_that_holds_the_line_is_offered_with_its_evidence(
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    a_gateable_prompt: None,
    a_finding: str,
) -> None:
    """The other direction, so the test above is not passing because nothing works.

    A gate that rejected everything would satisfy the assertion above perfectly
    and would be the implementation this test exists to reject. The proposal that
    does get written carries a body, a family and a gate delta — the evidence
    card ADR-0068 §4 puts in front of a reviewer INSTEAD of a model-written
    rationale about why its own edit is good.
    """
    monkeypatch.setattr(
        gate_module, "dispatch", StubDispatcher(default=completion("this is in policy"))
    )
    monkeypatch.setattr(gate_module, "check_spend_ceiling", allow_ceiling)

    await _propose(app_sessionmaker, a_finding)

    rows = await _proposals(migrate_engine)
    assert len(rows) == 1
    row = rows[0]
    assert row["remedy_kind"] == "edit"
    assert row["remedy_family"] == "add_length_rule"
    assert row["candidate_body"], "an edit with no body cannot be what a person opens"
    assert row["gate_run_id"] == BASELINE_RUN
    assert row["gate_delta"]["case_count"] == 1
    assert row["gate_delta"]["candidate_pass"] == 1
    # The clause the transform inserted, on the row a person will read.
    assert "output_format" in row["candidate_body"]


async def test_a_gate_that_could_not_run_is_a_rejection_and_not_a_pass(
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    a_gateable_prompt: None,
    a_finding: str,
) -> None:
    """**The cheapest way to break this module, closed deliberately.**

    The workspace is at its spend ceiling, so the gate refuses before dispatching
    anything. No result comes back at all — and *no result* must mean *no
    proposal*, never *nothing objected*. An implementation that wrote the row
    when the gate was skipped would look identical in every log and would put an
    ungated model-influenced body in front of a person.
    """
    dispatcher = StubDispatcher(default=completion("this is in policy"))
    monkeypatch.setattr(gate_module, "dispatch", dispatcher)
    monkeypatch.setattr(gate_module, "check_spend_ceiling", refuse_ceiling)

    await _propose(app_sessionmaker, a_finding)

    assert await _proposals(migrate_engine) == []
    assert dispatcher.calls == [], "refused after spending is not a control"


async def test_the_gate_writes_no_eval_run_and_no_case_result(
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    a_gateable_prompt: None,
) -> None:
    """ADR-0067 §3's rule, one step later: a GATE is not an eval run either.

    A row here would enter release-control's cost delta and make a revision look
    more expensive because a sweep ran overnight — and it would attach a
    `version_id` to a run whose body is not that version's. The candidate is not
    a revision and must not leave a trace shaped like one.
    """
    monkeypatch.setattr(
        gate_module, "dispatch", StubDispatcher(default=completion("this is in policy"))
    )
    monkeypatch.setattr(gate_module, "check_spend_ceiling", allow_ceiling)

    async with migrate_engine.begin() as connection:
        before = (
            (await connection.execute(text("SELECT count(*) FROM evaluation.eval_run"))).scalar_one(),
            (
                await connection.execute(text("SELECT count(*) FROM evaluation.case_result"))
            ).scalar_one(),
        )

    result = await score_body_against_suite(
        app_sessionmaker,
        workspace_id=WORKSPACE_A,
        prompt_id=PROMPT_ID,
        version_id=VERSION_ID,
        suite_id=SUITE_ID,
        candidate=CandidateRevision(
            body=BODY + "<output_format>Tối đa 300 từ.</output_format>",
            provider_config_id=PROVIDER_CONFIG_ID,
            upstream_model=UPSTREAM_MODEL,
            parameters={},
        ),
        now=day(3),
    )

    assert result is not None and not result.regressed

    async with migrate_engine.begin() as connection:
        after = (
            (await connection.execute(text("SELECT count(*) FROM evaluation.eval_run"))).scalar_one(),
            (
                await connection.execute(text("SELECT count(*) FROM evaluation.case_result"))
            ).scalar_one(),
        )

    assert after == before


async def test_the_gate_s_spend_lands_under_source_probe(
    app_sessionmaker: async_sessionmaker[AsyncSession],
    migrate_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    a_gateable_prompt: None,
    a_finding: str,
) -> None:
    """The price of the separation, paid where the workspace can see it.

    `source='probe'` rather than a new fifth source, and the migration's own
    constraint carries the rest: a probe row cannot name a run, a case or a
    consumer key, which is structurally why a gate's spend can never be mistaken
    for an eval's.
    """
    monkeypatch.setattr(
        gate_module, "dispatch", StubDispatcher(default=completion("this is in policy"))
    )
    monkeypatch.setattr(gate_module, "check_spend_ceiling", allow_ceiling)

    await _propose(app_sessionmaker, a_finding)

    async with migrate_engine.begin() as connection:
        rows = (
            (
                await connection.execute(
                    text(
                        "SELECT prompt_id, version_id, run_id, case_id, consumer_key_id "
                        "FROM ledger.call_record WHERE source = 'probe'"
                    )
                )
            )
            .mappings()
            .all()
        )

    assert rows, "a gate that dispatched and left no ledger row is worse than one that wrote a run"
    for row in rows:
        assert row["prompt_id"] == PROMPT_ID
        assert row["run_id"] is None
        assert row["case_id"] is None
        assert row["consumer_key_id"] is None
