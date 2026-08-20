"""The comparison funnel, on the cases the design document argues about.

No database, no model, no DSPy import. Every rung below the adjudicator is pure,
which is the property that makes these assertions worth writing: the rules that
decide whether somebody's prompt is called a duplicate are reproducible, and a
change to one of them fails here rather than on an import screen.
"""

import asyncio

import pytest

from prope.canonical_prompt import blocks_of
from prope.prompt_search.comparison import (
    FINDING_CODES,
    Action,
    CandidateEvidence,
    CandidateInput,
    InputContractRelation,
    OutputDescriptor,
    Severity,
    Verdict,
    compare,
    compare_input_contracts,
    compare_output_contracts,
    declared_output_text,
    facts_of,
    present,
    rank_candidates,
    recommend,
    resolve_action,
    resolve_verdict,
    summarise,
)

TRIAGE = """
<system>Bạn là trợ lý cẩn thận.</system>
<instructions>Phân loại yêu cầu hoàn tiền trong {{ticket}} thành approve, reject hoặc escalate.</instructions>
<output_format>Trả về JSON, chỉ JSON. Các khoá: decision, reason, confidence.</output_format>
""".strip()

TRANSLATE = """
<system>Bạn là trợ lý cẩn thận.</system>
<instructions>Dịch tài liệu kỹ thuật trong {{document}} từ tiếng Anh sang tiếng Việt.</instructions>
<output_format>Văn bản thuần, giữ nguyên thuật ngữ.</output_format>
""".strip()


def _run(coroutine):
    return asyncio.run(coroutine)


async def _judge(mapping):
    async def adjudicate(_incoming, briefs):
        return {label: mapping[label] for label, _, _ in briefs if label in mapping}

    return adjudicate


# --- stage 2a: the input contract ------------------------------------------


def test_requiring_fewer_variables_is_compatible():
    """`render()` ignores extras, so a subset cannot break a caller."""
    comparison = compare_input_contracts(
        candidate_body="Use {{ticket}}",
        released_body="Use {{ticket}} and {{tier}}",
    )
    assert comparison.relation is InputContractRelation.SUBSET
    assert comparison.is_compatible
    assert not any(finding.severity is Severity.HARD for finding in comparison.findings())


def test_requiring_more_variables_breaks_every_caller():
    comparison = compare_input_contracts(
        candidate_body="Use {{ticket}} and {{tier}}",
        released_body="Use {{ticket}}",
    )
    assert comparison.relation is InputContractRelation.SUPERSET
    assert comparison.is_breaking
    codes = {finding.code for finding in comparison.findings()}
    assert "similar.input_contract.requires_more" in codes


def test_a_rename_is_breaking_even_when_the_job_is_identical():
    """The one shape where breakage and sameness disagree completely."""
    comparison = compare_input_contracts(
        candidate_body="Summarise {{text}}",
        released_body="Summarise {{document}}",
    )
    assert comparison.relation is InputContractRelation.RENAMED
    findings = comparison.findings()
    assert [finding.code for finding in findings] == ["similar.input_contract.renamed"]
    assert findings[0].severity is Severity.HARD


# --- stage 2b: the declared output contract --------------------------------


def test_a_dropped_output_key_is_hard_and_an_added_one_is_soft():
    """The mirror of 2a's rule: outputs must be a SUPERSET, inputs a subset."""
    findings = compare_output_contracts(
        candidate=OutputDescriptor(modality="json", keys=("decision", "note")),
        released=OutputDescriptor(modality="json", keys=("decision", "reason")),
    )
    by_code = {finding.code: finding for finding in findings}
    assert by_code["similar.output_contract.keys_missing"].severity is Severity.HARD
    assert by_code["similar.output_contract.keys_missing"].params["keys"] == ["reason"]
    assert by_code["similar.output_contract.keys_added"].severity is Severity.SOFT


def test_dropping_only_is_a_hard_finding_of_its_own():
    """"Return JSON" and "return only JSON" are different contracts."""
    findings = compare_output_contracts(
        candidate=OutputDescriptor(modality="json", bare="unspecified"),
        released=OutputDescriptor(modality="json", bare="yes"),
    )
    assert any(
        finding.code == "similar.output_contract.bare_relaxed"
        and finding.severity is Severity.HARD
        for finding in findings
    )


def test_an_undeclared_modality_is_breaking_not_compatible():
    findings = compare_output_contracts(
        candidate=OutputDescriptor(),
        released=OutputDescriptor(modality="json"),
    )
    assert any(
        finding.code == "similar.output_contract.modality_undeclared"
        and finding.severity is Severity.HARD
        for finding in findings
    )


def test_a_missing_descriptor_is_not_established_and_is_not_a_veto():
    """Not extracted is not the same as declaring nothing, and neither is compatible."""
    findings = compare_output_contracts(candidate=None, released=OutputDescriptor(modality="json"))
    assert [finding.code for finding in findings] == ["similar.output_contract.not_established"]
    assert findings[0].severity is Severity.SOFT


def test_the_output_contract_is_read_from_instructions_when_there_is_no_block():
    text, block = declared_output_text(
        "<instructions>Trả lời bằng JSON gồm decision.</instructions>"
    )
    assert block == "instructions"
    assert "JSON" in text

    assert declared_output_text("chỉ là văn bản dán vào") == ("", "unspecified")


def test_an_unconverted_paste_yields_a_contract_only_when_prose_is_allowed():
    """The flag the import screen passes, and the reason it has to exist.

    The duplicate check runs before conversion, so what it holds is prose. With
    the strict reading that is `unspecified` on the incoming side of every
    import ever run, which is not a strict rung — it is a rung that cannot fire.
    """
    paste = "Bạn là trợ lý phân loại. Trả về JSON gồm decision và reason."

    assert declared_output_text(paste) == ("", "unspecified")

    text, block = declared_output_text(paste, allow_prose=True)
    assert block == "whole_text"
    assert text == paste

    # The flag does not override a body that says something. A canonical prompt
    # is still read from its own block, whoever asks.
    assert declared_output_text(TRIAGE, allow_prose=True)[1] == "output_format"
    # And it does not invent one out of nothing.
    assert declared_output_text("   ", allow_prose=True) == ("", "unspecified")


def test_a_contract_read_out_of_prose_is_recorded_as_the_weakest_source():
    """Three sources, three strengths, and the sheet may not flatten them.

    `output_format` is a declaration. `instructions` is a statement in the task
    text. `whole_text` is a model's reading of unstructured prose — which is
    what every import produces until the prompt is converted, and which a reader
    weighing a hard finding has to be able to discount.
    """
    declared = OutputDescriptor(modality="json", source_block="output_format")
    from_prose = OutputDescriptor(modality="json", source_block="whole_text")
    from_task = OutputDescriptor(modality="json", source_block="instructions")

    codes = [f.code for f in compare_output_contracts(candidate=from_prose, released=declared)]
    assert "similar.output_contract.inferred_from_prose" in codes
    assert "similar.output_contract.declared_in_instructions" not in codes

    codes = [f.code for f in compare_output_contracts(candidate=from_task, released=declared)]
    assert "similar.output_contract.declared_in_instructions" in codes

    # Never a hard finding: it says how well the contract is known, not that
    # anything about it breaks.
    findings = compare_output_contracts(candidate=from_prose, released=declared)
    assert all(finding.severity is not Severity.HARD for finding in findings)


def test_a_missing_descriptor_is_extracted_rather_than_reported_missing():
    """`describe` fills stage 2b's gaps, and only for candidates the sheet shows.

    The stored descriptor is a per-revision property the indexer is supposed to
    have written. When it has not — the row predates the column, the extraction
    failed, or the descriptor belongs to an older revision — the rung used to
    answer `not_established` and stop. Now the funnel extracts what is missing,
    which is the difference between a contract check and a coverage complaint.

    The `different` candidate is the assertion that matters second: it is
    dropped from the sheet whatever its contract says, so extracting one would
    be spending a model call to learn something no reader will ever see.
    """
    asked: list[str] = []

    async def describe(subject_id: str, body: str):
        asked.append(subject_id)
        return OutputDescriptor(modality="json", source_block="whole_text"), "whole_text"

    async def adjudicate(incoming, briefs):
        return {
            "C1": ("same_task", ("same_action_same_object",)),
            "C2": ("different", ("different_object",)),
        }

    candidates = [
        CandidateInput(prompt_id="prm_shown", title="A", body=TRIAGE),
        CandidateInput(prompt_id="prm_dropped", title="B", body=TRANSLATE),
    ]
    sheet = asyncio.run(
        compare(
            incoming_body="Phân loại yêu cầu hoàn tiền thành approve, reject hoặc escalate.",
            candidates=candidates,
            adjudicate=adjudicate,
            describe=describe,
        )
    )

    assert "prm_shown" in asked
    assert "prm_dropped" not in asked
    assert "" in asked, "the incoming body has no stored descriptor and must be extracted too"

    codes = {finding.code for candidate in sheet.candidates for finding in candidate.findings}
    assert "similar.output_contract.not_established" not in codes


def test_an_extractor_that_answers_nothing_is_failed_and_a_silent_prompt_is_skipped():
    """Two ways to end with no descriptor, and the trace may not merge them.

    A prompt that never says what it returns is ordinary; an extractor that was
    given a contract and did not answer is an incident. Both leave the incoming
    side `None`, and a rung that paints them the same colour teaches a reader to
    ignore the colour.
    """

    async def adjudicate(incoming, briefs):
        return {"C1": ("same_task", ())}

    def run(describe):
        events: list[tuple[str, str]] = []
        asyncio.run(
            compare(
                incoming_body="anything at all",
                candidates=[CandidateInput(prompt_id="prm_a", title="A", body=TRIAGE)],
                adjudicate=adjudicate,
                describe=describe,
                on_step=lambda event: events.append((event.step.value, event.state.value)),
            )
        )
        return [state for step, state in events if step == "output_contract"]

    async def silent(subject_id: str, body: str):
        return None, "unspecified"

    async def unavailable(subject_id: str, body: str):
        return None, "whole_text"

    assert run(silent) == ["started", "skipped"]
    assert run(unavailable) == ["started", "failed"]


def test_a_stored_descriptor_is_never_re_extracted():
    """The index row is the cache, and a cache that is ignored is a cost."""
    asked: list[str] = []

    async def describe(subject_id: str, body: str):
        asked.append(subject_id)
        return OutputDescriptor(modality="json"), "whole_text"

    async def adjudicate(incoming, briefs):
        return {"C1": ("same_task", ())}

    sheet = asyncio.run(
        compare(
            incoming_body=TRIAGE,
            candidates=[
                CandidateInput(
                    prompt_id="prm_described",
                    title="A",
                    body=TRIAGE,
                    descriptor=OutputDescriptor(modality="json", source_block="output_format"),
                )
            ],
            incoming_descriptor=OutputDescriptor(modality="json", source_block="output_format"),
            adjudicate=adjudicate,
            describe=describe,
        )
    )

    assert asked == []
    assert sheet.candidates


# --- the free pre-filter ----------------------------------------------------


def test_the_prefilter_ranks_on_instructions_not_on_shared_boilerplate():
    """Both candidates share the `system` block verbatim; only one shares the job.

    This is the false-positive mechanism in miniature. A whole-document vector
    is dominated by `system` + `examples` + `constraints`; scoring per block is
    what lets `instructions` decide.
    """
    incoming = facts_of(
        "<system>Bạn là trợ lý cẩn thận.</system>"
        "<instructions>Phân loại yêu cầu hoàn tiền thành approve hoặc reject.</instructions>"
    )
    ranked = rank_candidates(
        incoming,
        [
            facts_of(TRANSLATE, prompt_id="p_translate"),
            facts_of(TRIAGE, prompt_id="p_triage"),
        ],
        limit=2,
    )
    assert [scored.facts.prompt_id for scored in ranked] == ["p_triage", "p_translate"]
    assert ranked[0].score > ranked[1].score


def test_the_adjudicator_is_shown_the_job_and_not_the_persona():
    """`system` and `examples` are excluded from the presentation on purpose."""
    presented = present(facts_of(TRIAGE))
    assert "[instructions]" in presented
    assert "[output_format]" in presented
    assert "trợ lý cẩn thận" not in presented


def test_a_non_canonical_body_is_still_comparable():
    """The import screen's normal case: text that has not been converted yet."""
    incoming = facts_of("Phân loại yêu cầu hoàn tiền thành approve hoặc reject")
    assert not incoming.is_canonical
    ranked = rank_candidates(incoming, [facts_of(TRIAGE, prompt_id="p_triage")], limit=1)
    assert ranked[0].score > 0


# --- the overlap evidence the dialog renders --------------------------------


def test_the_overlap_names_the_words_the_two_prompts_share():
    """A verdict alone is an assertion; this is the part a reader can contradict."""
    adjudicate = _run(_judge({"C1": ("same_task", ("same_action_same_object",))}))
    sheet = _run(
        compare(
            incoming_body=TRIAGE.replace("escalate", "reject"),
            candidates=[CandidateInput(prompt_id="p_triage", title="Hoàn tiền", body=TRIAGE)],
            adjudicate=adjudicate,
        )
    )
    overlap = sheet.candidates[0].overlap
    assert overlap is not None
    blocks = {block.block: block for block in overlap.blocks}
    assert "instructions" in blocks
    assert "approve" in blocks["instructions"].shared_terms
    assert overlap.shared_variables == ("ticket",)
    assert overlap.variable_overlap == 1.0


def test_the_overlap_leads_with_the_job_even_when_the_persona_scores_higher():
    """Two prompts from one library share their `system` block almost verbatim.

    Ordering that agreement first would reproduce the whole-document embedding's
    mistake in the interface, so blocks arrive weighted by how much they count.
    """
    incoming = "<system>Bạn là trợ lý cẩn thận.</system><instructions>Phân loại hoàn tiền trong {{ticket}}.</instructions>"
    adjudicate = _run(_judge({"C1": ("same_task", ())}))
    sheet = _run(
        compare(
            incoming_body=incoming,
            candidates=[CandidateInput(prompt_id="p_triage", title="Hoàn tiền", body=TRIAGE)],
            adjudicate=adjudicate,
        )
    )
    blocks = [block.block for block in sheet.candidates[0].overlap.blocks]
    assert blocks.index("instructions") < blocks.index("system")


def test_a_block_that_shares_nothing_is_absent_rather_than_listed_at_zero():
    # `match_floor=0` because this is about the shape of the overlap and not
    # about what the screen lists: at the shipping floor these two prompts are
    # nowhere near each other, which is the subject of its own tests below.
    adjudicate = _run(_judge({"C1": ("same_domain", ())}))
    sheet = _run(
        compare(
            incoming_body=TRIAGE,
            candidates=[CandidateInput(prompt_id="p_translate", title="Dịch", body=TRANSLATE)],
            adjudicate=adjudicate,
            match_floor=0.0,
        )
    )
    overlap = sheet.candidates[0].overlap
    assert all(block.score > 0.0 for block in overlap.blocks)


def test_a_pasted_body_reports_whole_text_and_never_a_block_it_did_not_parse():
    adjudicate = _run(_judge({"C1": ("same_task", ())}))
    sheet = _run(
        compare(
            incoming_body="Phân loại yêu cầu hoàn tiền thành approve hoặc reject",
            candidates=[CandidateInput(prompt_id="p_triage", title="Hoàn tiền", body=TRIAGE)],
            adjudicate=adjudicate,
        )
    )
    assert [block.block for block in sheet.candidates[0].overlap.blocks] == ["whole_text"]


def test_the_reason_codes_survive_to_the_evidence():
    adjudicate = _run(
        _judge({"C1": ("candidate_broader", ("candidate_covers_more_cases",))})
    )
    sheet = _run(
        compare(
            incoming_body=TRIAGE,
            candidates=[CandidateInput(prompt_id="p_triage", title="Hoàn tiền", body=TRIAGE)],
            adjudicate=adjudicate,
        )
    )
    assert sheet.candidates[0].reasons == ("candidate_covers_more_cases",)
    assert sheet.candidates[0].verdict is Verdict.SUPERSEDES


# --- verdicts and actions ---------------------------------------------------


def test_a_hard_finding_demotes_same_to_variant():
    breaking = (compare_input_contracts(candidate_body="{{a}} {{b}}", released_body="{{a}}"),)
    findings = breaking[0].findings()
    assert resolve_verdict(relation="same_task", findings=findings) is Verdict.VARIANT
    assert resolve_verdict(relation="same_task", findings=()) is Verdict.SAME


def test_contract_findings_can_only_demote_never_promote():
    """Sharing an input contract is not doing the same work."""
    assert resolve_verdict(relation="same_domain", findings=()) is Verdict.RELATED


def test_supersedes_never_offers_a_revision():
    """Attaching the narrower prompt as a revision would silently drop coverage."""
    assert resolve_action(Verdict.SUPERSEDES) is Action.CREATE_NEW
    assert resolve_action(Verdict.SAME) is Action.ADD_REVISION
    assert resolve_action(Verdict.VARIANT) is Action.CREATE_NEW


def test_use_existing_is_never_recommended_without_measurement():
    """The one irrecoverable error in the table, and the reason for the gate."""
    same = CandidateEvidence(
        prompt_id="p_1", verdict=Verdict.SAME, action=Action.ADD_REVISION
    )
    action, prompt_id = recommend((same,))
    assert action is Action.ADD_REVISION
    assert prompt_id == "p_1"
    assert Action.USE_EXISTING not in {action}


def test_two_same_candidates_recommend_nothing():
    """Not a stronger signal — an unresolved question, and position must not answer it."""
    candidates = tuple(
        CandidateEvidence(prompt_id=f"p_{index}", verdict=Verdict.SAME, action=Action.ADD_REVISION)
        for index in range(2)
    )
    assert recommend(candidates) == (Action.CREATE_NEW, None)


def test_unrelated_candidates_are_not_on_the_sheet_at_all():
    sheet = summarise(
        (
            CandidateEvidence(prompt_id="p_1", verdict=Verdict.UNRELATED, action=Action.CREATE_NEW),
            CandidateEvidence(prompt_id="p_2", verdict=Verdict.RELATED, action=Action.CREATE_NEW),
        ),
        retrieved=20,
        adjudicated=5,
        match_floor=0.0,
    )
    assert [candidate.prompt_id for candidate in sheet.candidates] == ["p_2"]
    assert sheet.retrieved == 20 and sheet.adjudicated == 5


def test_a_candidate_under_the_match_floor_is_not_listed_and_is_counted():
    """The floor removes rows; `below_floor` is what stops it removing the fact.

    A row that is absent because of a threshold and a row that was never found
    look identical on screen, and the difference is the whole of whether *"no
    duplicates"* can be believed.
    """
    sheet = summarise(
        (
            CandidateEvidence(
                prompt_id="p_near",
                verdict=Verdict.RELATED,
                action=Action.CREATE_NEW,
                match_score=0.93,
            ),
            CandidateEvidence(
                prompt_id="p_far",
                verdict=Verdict.RELATED,
                action=Action.CREATE_NEW,
                match_score=0.62,
            ),
        ),
        retrieved=20,
        adjudicated=5,
        match_floor=0.9,
    )
    assert [candidate.prompt_id for candidate in sheet.candidates] == ["p_near"]
    assert sheet.below_floor == 1
    assert sheet.match_floor == 0.9
    assert any(
        finding.code == "similar.coverage.below_match_floor" and finding.params["floor"] == 90
        for finding in sheet.coverage
    )


def test_a_verdict_of_same_outranks_the_floor_however_little_wording_it_shares():
    """A wording threshold may not overrule the adjudicator. Measured, not argued.

    The floor asks how much of the incoming prompt's *wording* a candidate
    carries. A duplicate that was rewritten rather than copied carries very
    little of it and is still a duplicate — that is the entire case the redesign
    exists to catch. Across the ten labelled triplets in
    `eval/retrieval/similarity.py` every confirmed duplicate scores under 0.90
    and the best manages 0.472, so applied here the floor was not strict, it was
    a guarantee that the funnel's own conclusion never reached the screen.

    `related` stays governed by it: that is context, and thinning context is the
    job the floor was actually added to do.
    """
    sheet = summarise(
        (
            CandidateEvidence(
                prompt_id="p_rewritten",
                verdict=Verdict.SAME,
                action=Action.ADD_REVISION,
                match_score=0.10,
            ),
            CandidateEvidence(
                prompt_id="p_context",
                verdict=Verdict.RELATED,
                action=Action.CREATE_NEW,
                match_score=0.10,
            ),
        ),
        retrieved=20,
        adjudicated=5,
        match_floor=0.9,
    )
    assert [candidate.prompt_id for candidate in sheet.candidates] == ["p_rewritten"]
    # Only the row the floor actually removed is counted. A `same` that bypassed
    # it was never withheld, and counting it would report a suppression that did
    # not happen — on the very field the screen uses to say so.
    assert sheet.below_floor == 1
    assert sheet.recommended_prompt_id == "p_rewritten"
    assert sheet.recommended_action is Action.ADD_REVISION


def test_a_variant_is_listed_too_because_it_is_the_expensive_row():
    """`variant` means *does your job, breaks your callers*. It may not be hidden.

    It is the outcome a reader is least likely to go looking for and most needs
    told: the adjudicator found the same job and a HARD contract finding demoted
    it. Suppressing that for thin wording overlap would hide the one row whose
    absence costs a production incident.
    """
    sheet = summarise(
        (
            CandidateEvidence(
                prompt_id="p_incompatible",
                verdict=Verdict.VARIANT,
                action=Action.CREATE_NEW,
                match_score=0.05,
            ),
        ),
        retrieved=20,
        adjudicated=5,
        match_floor=0.9,
    )
    assert [candidate.prompt_id for candidate in sheet.candidates] == ["p_incompatible"]
    assert sheet.below_floor == 0


def test_the_match_score_is_a_share_and_reaches_one_for_an_identical_body():
    """The floor is a percentage, so the number under it has to be one.

    `structural_score` is a sum of weighted containments whose ceiling moves
    with the incoming prompt; 0.9 of it means five different things for five
    different prompts. `match_score` divides by what was attainable, so an
    identical body scores 1.0 and "90%" is a sentence about coverage.
    """
    ranked = rank_candidates(
        facts_of(TRIAGE),
        [facts_of(TRIAGE, prompt_id="p_same"), facts_of(TRANSLATE, prompt_id="p_other")],
        limit=5,
    )
    identical = next(item for item in ranked if item.facts.prompt_id == "p_same")
    other = next(item for item in ranked if item.facts.prompt_id == "p_other")
    assert identical.match == pytest.approx(1.0)
    assert other.match < 0.9
    # And it cannot reorder anything: the divisor is a property of the incoming
    # body, so it is the same for every candidate in the run.
    assert [item.facts.prompt_id for item in ranked] == sorted(
        [item.facts.prompt_id for item in ranked],
        key=lambda name: -next(i.match for i in ranked if i.facts.prompt_id == name),
    )


# --- the funnel end to end --------------------------------------------------


def test_an_unrelated_prompt_is_dropped_even_when_it_ranked():
    """The reported bug: three prompts shown as duplicates that shared nothing."""
    adjudicate = _run(_judge({"C1": ("different", ("different_action",))}))
    sheet = _run(
        compare(
            incoming_body=TRIAGE,
            candidates=[CandidateInput(prompt_id="p_translate", title="Dịch", body=TRANSLATE)],
            adjudicate=adjudicate,
        )
    )
    assert sheet.candidates == ()
    assert sheet.recommended_action is Action.CREATE_NEW
    assert sheet.retrieved == 1


def test_the_same_job_with_a_clean_contract_recommends_a_revision():
    adjudicate = _run(_judge({"C1": ("same_task", ("same_action_same_object",))}))
    sheet = _run(
        compare(
            incoming_body=TRIAGE,
            candidates=[
                CandidateInput(prompt_id="p_triage", title="Hoàn tiền", body=TRIAGE),
                CandidateInput(prompt_id="p_translate", title="Dịch", body=TRANSLATE),
            ],
            adjudicate=adjudicate,
        )
    )
    assert sheet.recommended_action is Action.ADD_REVISION
    assert sheet.recommended_prompt_id == "p_triage"
    assert any(
        finding.code == "similar.coverage.use_existing_requires_measurement"
        for finding in sheet.coverage
    )


def test_an_unavailable_adjudicator_claims_nothing():
    """Fail soft, and never upgrade structural overlap into a duplicate verdict."""

    async def adjudicate(_incoming, _briefs):
        return {}

    sheet = _run(
        compare(
            incoming_body=TRIAGE,
            candidates=[CandidateInput(prompt_id="p_triage", title="Hoàn tiền", body=TRIAGE)],
            adjudicate=adjudicate,
        )
    )
    assert sheet.recommended_action is Action.CREATE_NEW
    assert [candidate.verdict for candidate in sheet.candidates] == [Verdict.RELATED]
    assert not sheet.candidates[0].adjudicated
    assert any(
        finding.code == "similar.coverage.adjudication_unavailable"
        for finding in sheet.coverage
    )


def test_no_candidates_produces_an_empty_sheet_and_no_recommendation():
    sheet = _run(compare(incoming_body=TRIAGE, candidates=[]))
    assert sheet.candidates == ()
    assert sheet.recommended_action is Action.CREATE_NEW
    assert sheet.retrieved == 0


def test_every_emitted_code_is_in_the_closed_catalogue():
    """The guard behind the contract test that checks the interface catalogue."""
    emitted = set()
    emitted |= {
        finding.code
        for body_pair in (
            ("{{a}} {{b}}", "{{a}}"),
            ("{{a}}", "{{a}} {{b}}"),
            ("{{x}}", "{{y}}"),
            ("{{a}}", "{{a}}"),
        )
        for finding in compare_input_contracts(
            candidate_body=body_pair[0], released_body=body_pair[1]
        ).findings()
    }
    emitted |= {
        finding.code
        for pair in (
            (OutputDescriptor(), OutputDescriptor(modality="json", keys=("a",))),
            (None, OutputDescriptor(modality="json")),
            (
                OutputDescriptor(modality="json", keys=("a", "b"), enums={"a": ("x",)}),
                OutputDescriptor(
                    modality="markdown",
                    keys=("a",),
                    enums={"a": ("x", "y"), "b": ("z",)},
                    bare="yes",
                    cardinality="list",
                    language="vi",
                    length="brief",
                    source_block="instructions",
                ),
            ),
            (
                OutputDescriptor(modality="json", source_block="output_format"),
                OutputDescriptor(modality="json", source_block="output_format"),
            ),
        )
        for finding in compare_output_contracts(candidate=pair[0], released=pair[1])
    }
    unknown = sorted(emitted - set(FINDING_CODES))
    assert unknown == [], f"{unknown} are emitted but not declared in FINDING_CODES"


@pytest.mark.parametrize(
    "body,expected",
    [
        ("<instructions>a</instructions>", {"instructions"}),
        ("plain pasted text", set()),
        ("<instructions>a</instructions><notablock>b</notablock>", {"instructions"}),
    ],
)
def test_block_parsing_is_tolerant_of_what_the_registry_would_refuse(body, expected):
    """The import screen holds text that has not been through validation yet."""
    assert set(blocks_of(body)) == expected


# --- the trace the screen renders -------------------------------------------


def test_the_funnel_narrates_every_rung_in_the_order_it_runs():
    """The bottom sheet is a view of these events and nothing else.

    Asserted as a sequence rather than a set: the value of the trace is that a
    reader can see which rung the candidates were lost at, and a rung reported
    out of order tells them the wrong one.
    """
    events = []
    adjudicate = _run(_judge({"C1": ("same_task", ())}))
    _run(
        compare(
            incoming_body=TRIAGE,
            candidates=[CandidateInput(prompt_id="p_triage", title="Hoàn tiền", body=TRIAGE)],
            adjudicate=adjudicate,
            on_step=events.append,
        )
    )
    assert [(event.step.value, event.state.value) for event in events] == [
        ("prefilter", "started"),
        ("prefilter", "done"),
        ("adjudication", "started"),
        ("adjudication", "done"),
        ("contracts", "done"),
        ("verdict", "done"),
    ]


def test_an_unavailable_adjudicator_is_a_failed_rung_and_never_a_quiet_zero():
    """`skipped` and `done, judged=0` are different facts about the answer."""
    events = []
    _run(
        compare(
            incoming_body=TRIAGE,
            candidates=[CandidateInput(prompt_id="p_triage", title="Hoàn tiền", body=TRIAGE)],
            adjudicate=_run(_judge({})),
            on_step=events.append,
        )
    )
    adjudication = [event for event in events if event.step.value == "adjudication"]
    assert [event.state.value for event in adjudication] == ["started", "failed"]


def test_no_trace_event_carries_a_word_of_either_prompt():
    """A-046, on the one path in this module that streams.

    These frames go out over a long-lived connection and are the easiest place
    in the system to leak a body by accident. The whole payload of every event
    is checked against the words of both prompts rather than the fields being
    listed, so a field added later is covered without anybody remembering to
    add it here.
    """
    events = []
    adjudicate = _run(_judge({"C1": ("same_task", ())}))
    _run(
        compare(
            incoming_body=TRIAGE,
            candidates=[CandidateInput(prompt_id="p_triage", title="Hoàn tiền", body=TRIAGE)],
            adjudicate=adjudicate,
            on_step=events.append,
        )
    )
    words = {
        token.lower()
        for body in (TRIAGE, TRANSLATE)
        for token in body.replace("<", " ").replace(">", " ").split()
        if len(token) > 3
    }
    for event in events:
        rendered = repr(event.to_dict()).lower()
        assert not [word for word in words if word in rendered]


def test_a_compared_block_that_shared_nothing_is_distinguishable_from_an_absent_one():
    """The grid of metrics has a cell per axis, so silence must not read as zero.

    `blocks` lists what overlapped and `compared_blocks` lists what was looked
    at, and the difference is the difference between *these two share no output
    contract* — evidence — and *neither declares one* — silence. Reporting the
    second as `0%` is the same error `output_contract.not_established` exists to
    refuse, one layer up.
    """
    incoming = (
        "<instructions>Phân loại yêu cầu hoàn tiền trong {{ticket}}.</instructions>"
        "<output_format>Trả về JSON: decision.</output_format>"
    )
    adjudicate = _run(_judge({"C1": ("same_task", ())}))
    sheet = _run(
        compare(
            incoming_body=incoming,
            # Shares the job, declares a completely different output contract.
            candidates=[CandidateInput(prompt_id="p_other", title="Khác", body=TRANSLATE)],
            adjudicate=adjudicate,
            match_floor=0.0,
        )
    )
    overlap = sheet.candidates[0].overlap
    assert "output_format" in overlap.compared_blocks
    assert "output_format" not in {block.block for block in overlap.blocks}


def test_the_variable_denominator_travels_so_none_is_not_reported_as_zero_shared():
    """`variable_overlap == 0` means two different things and only one is a finding."""
    adjudicate = _run(_judge({"C1": ("same_task", ())}))

    takes_none = _run(
        compare(
            incoming_body="<instructions>Phân loại yêu cầu hoàn tiền.</instructions>",
            candidates=[CandidateInput(prompt_id="p_triage", title="Hoàn tiền", body=TRIAGE)],
            adjudicate=adjudicate,
            match_floor=0.0,
        )
    )
    assert takes_none.candidates[0].overlap.variables_required == 0

    takes_one = _run(
        compare(
            incoming_body="<instructions>Phân loại {{ticket}} thành approve.</instructions>",
            candidates=[CandidateInput(prompt_id="p_triage", title="Hoàn tiền", body=TRIAGE)],
            adjudicate=adjudicate,
            match_floor=0.0,
        )
    )
    overlap = takes_one.candidates[0].overlap
    assert overlap.variables_required == 1
    assert overlap.shared_variables == ("ticket",)
