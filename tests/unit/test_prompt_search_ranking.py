"""``prompt_search.ranking`` — the fusion, on its own, with no database.

Every assertion here is a property the previous merge did not have, and each one
corresponds to a measured failure in `eval/result/`: a common word counting as
much as a rare one, a weak vector match outranking an exact-term match by fiat,
and a lexical-only candidate being judged against a threshold calibrated for
cosine distance.

These are unit tests on purpose. The ranking seam is the part of search most
likely to regress and the part an integration test is worst at catching — a
change that reorders results still returns results, still respects permissions,
and still passes every behavioural test in the suite.
"""

import pytest

from prope.prompt_search.ranking import (
    alpha_fusion,
    fuse,
    lexical_scores,
    reciprocal_rank_fusion,
)


class TestLexicalScores:
    def test_a_rare_term_outweighs_a_common_one(self) -> None:
        """The failure that made the lexical leg noise.

        "kubernetes" appears in one prompt of a hundred; "engineer" in twenty.
        Under the previous ``matched / len(terms)`` both contributed exactly 0.5
        to a prompt matching one of them, so a prompt that merely said "engineer"
        tied with the one the person was looking for.

        Every term here is under the drop threshold and both prompts match two of
        them, so neither the frequency cap nor the corroboration rule is doing
        the work — this is IDF alone. ``prm_rare`` matched the two terms that
        appear in one prompt each; ``prm_common`` matched the two that appear in
        twenty.
        """
        crowd = {f"prm_{index}" for index in range(20)}
        scores = lexical_scores(
            {
                "kubernetes": {"prm_rare"},
                "kubeadm": {"prm_rare"},
                "engineer": crowd | {"prm_common"},
                # 5 of 100 — specific enough to anchor, so what separates the two
                # prompts below is the weighting and not the admission rules.
                "toolchain": {"prm_c1", "prm_c2", "prm_c3", "prm_c4", "prm_common"},
            },
            corpus_size=100,
        )

        assert scores["prm_rare"] > scores["prm_common"]

    def test_matching_every_distinctive_term_scores_one(self) -> None:
        scores = lexical_scores(
            {"alpha": {"prm_a"}, "beta": {"prm_a", "prm_b"}, "gamma": {"prm_a", "prm_b"}},
            corpus_size=50,
        )

        assert scores["prm_a"] == pytest.approx(1.0)
        assert 0 < scores["prm_b"] < 1.0

    def test_a_term_at_the_drop_threshold_still_scores(self) -> None:
        """The boundary is inclusive, and the smoothing holds at it.

        A term matching exactly a quarter of the corpus survives, and its weight
        is finite — ``log((N+1)/(df+1)) + 1`` cannot divide by zero however
        common the term is, which is the property that lets the cap be a policy
        choice rather than a guard against arithmetic.
        """
        scores = lexical_scores(
            {"common": {f"prm_{index}" for index in range(25)}}, corpus_size=100
        )

        assert scores["prm_0"] == pytest.approx(1.0)

    def test_no_terms_is_no_scores_rather_than_an_error(self) -> None:
        assert lexical_scores({}, corpus_size=10) == {}
        assert lexical_scores({"x": {"prm_a"}}, corpus_size=0) == {}

    def test_a_term_matching_most_of_the_corpus_is_dropped_entirely(self) -> None:
        """Down-weighting is not enough, and the adversarial set proved it.

        IDF weights are a share of ONE query's mass. A query whose every term is
        worthless still distributes 100% of that mass among worthless terms, so a
        prompt matching two of seven scores 0.3 and clears any floor. Substring
        matching over folded text manufactures exactly such terms: the Vietnamese
        for beef noodle soup folds to `pho` and `bo`, which match *phone* and
        *robot*.
        """
        common = {f"prm_{index}" for index in range(60)}
        scores = lexical_scores(
            {"pho": common, "bo": common, "knitting": {"prm_rare"}},
            corpus_size=100,
        )

        assert scores == {"prm_rare": pytest.approx(1.0)}

    def test_one_term_in_common_is_not_a_match_when_the_query_had_several(self) -> None:
        """The adversarial false positives, in one case.

        "knitting patterns for a cable sweater in worsted weight yarn" has three
        terms a developer corpus recognises at all — and `yarn` is a package
        manager. A prompt containing one of them is not an answer to the
        question; a prompt containing two might be.
        """
        scores = lexical_scores(
            {
                "yarn": {"prm_js_tooling"},
                "weight": {"prm_ml"},
                "knitting": set(),
            },
            corpus_size=200,
        )

        assert scores == {}

    def test_a_single_term_query_needs_no_corroboration(self) -> None:
        """`SQL`, `GDPR`, an error code — one word is the whole question.

        This is the case the lexical leg exists for, and the corroboration rule
        must not swallow it: there is no second term to agree with.
        """
        scores = lexical_scores({"gdpr": {"prm_privacy"}}, corpus_size=200)

        assert scores == {"prm_privacy": pytest.approx(1.0)}

    def test_two_terms_in_common_is_a_match(self) -> None:
        scores = lexical_scores(
            {"kubernetes": {"prm_k8s"}, "hardening": {"prm_k8s", "prm_sec"}},
            corpus_size=200,
        )

        assert set(scores) == {"prm_k8s"}

    def test_two_ordinary_terms_agreeing_is_not_a_match(self) -> None:
        """The adversarial case corroboration alone let through.

        "what time does the last train from Utrecht to Amsterdam leave on Sunday"
        keeps `last` and `leave` — one in five prompts and one in ten — while
        `utrecht`, `amsterdam` and `sunday` match nothing. Seven prompts contained
        both ordinary words and scored a perfect 1.0, because the share is
        computed over what survived rather than over what was asked.
        """
        both = {f"prm_{index}" for index in range(7)}
        scores = lexical_scores(
            {
                "last": both | {f"prm_x{index}" for index in range(34)},  # 41 of 200
                "leave": both | {f"prm_y{index}" for index in range(13)},  # 20 of 200
            },
            corpus_size=200,
        )

        assert scores == {}

    def test_a_three_letter_fragment_cannot_anchor_a_match(self) -> None:
        """Rarity is not enough when matching is a substring over folded text.

        `gia`, from the Vietnamese for *traditional*, matched exactly one prompt
        in two hundred — rare by every measure, and rare only because three
        letters happened to land inside a longer word. It anchored a beef-noodle-
        soup query onto a creative writing prompt.
        """
        scores = lexical_scores(
            {"gia": {"prm_accident"}, "noi": {"prm_accident"} | {f"prm_{i}" for i in range(25)}},
            corpus_size=200,
        )

        assert scores == {}

    def test_the_anchor_rule_is_optional_for_the_keyword_path(self) -> None:
        """A keyword box asserts nothing, so it may answer loosely.

        The same input the duplicate check must refuse is a reasonable keyword
        result: the person typed those words and is reading the titles.
        """
        both = {"prm_a", "prm_b"}
        hits = {
            "last": both | {f"prm_x{index}" for index in range(39)},
            "leave": both | {f"prm_y{index}" for index in range(18)},
        }

        assert lexical_scores(hits, corpus_size=200) == {}
        assert set(lexical_scores(hits, corpus_size=200, require_anchor=False)) == both

    def test_an_anchor_term_admits_the_prompts_that_share_it(self) -> None:
        """The same rule from the other side: one specific term plus one ordinary one."""
        common = {f"prm_{index}" for index in range(30)}
        scores = lexical_scores(
            {"postgres": {"prm_sql"}, "database": common | {"prm_sql"}},
            corpus_size=200,
        )

        assert set(scores) == {"prm_sql"}

    def test_a_query_of_nothing_but_common_terms_scores_nobody(self) -> None:
        """The abstention case. Nothing discriminating was asked, so nothing answers."""
        everywhere = {f"prm_{index}" for index in range(90)}

        assert lexical_scores({"patterns": everywhere, "weight": everywhere}, corpus_size=100) == {}


class TestReciprocalRankFusion:
    def test_agreement_across_legs_beats_depth_in_one(self) -> None:
        """The whole reason to fuse ranks instead of scores.

        ``prm_both`` is second in each leg and first in neither. It wins, because
        two independent retrievers pointing at the same document is stronger
        evidence than one retriever being very confident.
        """
        fused = reciprocal_rank_fusion(
            [
                ["prm_vector_only", "prm_both", "prm_c"],
                ["prm_lexical_only", "prm_both", "prm_d"],
            ]
        )

        assert max(fused, key=lambda key: fused[key]) == "prm_both"

    def test_a_leg_that_returned_nothing_contributes_nothing(self) -> None:
        fused = reciprocal_rank_fusion([["prm_a", "prm_b"], []])

        assert list(sorted(fused, key=lambda key: -fused[key])) == ["prm_a", "prm_b"]

    def test_leg_weights_let_one_retriever_count_for_more(self) -> None:
        fused = reciprocal_rank_fusion([["prm_dense"], ["prm_sparse"]], weights=[1.0, 0.5])

        assert fused["prm_dense"] == pytest.approx(2 * fused["prm_sparse"])


class TestAlphaFusion:
    def test_it_weights_the_vector_leg_by_alpha(self) -> None:
        fused = alpha_fusion({"prm_a": 1.0}, {"prm_a": 0.0}, alpha=0.7)

        assert fused["prm_a"] == pytest.approx(0.7)

    def test_a_candidate_missing_from_one_leg_keeps_the_other_leg_s_share(self) -> None:
        fused = alpha_fusion({}, {"prm_lexical": 1.0}, alpha=0.7)

        assert fused["prm_lexical"] == pytest.approx(0.3)


class TestFuse:
    def test_a_lexical_only_match_is_a_candidate(self) -> None:
        """The index is an accelerator, not a gate — and the gate is per leg.

        A prompt nobody indexed has no vector at all. It must still be reachable
        through the registry's trigram document, which is the property the import
        screen's duplicate check depends on.
        """
        results = fuse(vector={}, lexical={"prm_unindexed": 0.9})

        assert [result.prompt_id for result in results] == ["prm_unindexed"]
        assert results[0].matched_fields == ("lexical",)
        assert results[0].vector_similarity is None
        # And no reported similarity: there is no cosine, and the lexical share
        # is not one. See `FusedResult.similarity`.
        assert results[0].similarity is None
        assert results[0].lexical_similarity == pytest.approx(0.9)

    def test_a_weak_vector_match_does_not_automatically_outrank_a_strong_lexical_one(self) -> None:
        """What "the vector always wins" cost, in one assertion.

        On a corpus of documents written in the same genre every cosine lands in
        a narrow band, so *any* vector hit used to precede *every* lexical hit.
        Here the lexical candidate matches all of the query's distinctive terms
        and the vector candidate is barely over its floor.

        The vector leg carries twice the weight, so this is not free: the lexical
        candidate has to be alone at the top of its leg while the vector's best is
        barely over its floor. That is the shape of a query naming an exact
        identifier the embedding never learned.
        """
        results = fuse(
            vector={"prm_barely": 0.26, "prm_second": 0.25},
            lexical={"prm_exact": 1.0, "prm_barely": 0.2},
        )

        assert [result.prompt_id for result in results][0] == "prm_barely"

    def test_the_vector_leg_outweighs_the_lexical_leg(self) -> None:
        """Half weight, and this is what it buys.

        A prompt the vector leg ranks second still precedes one the lexical leg
        ranks first — the old ceiling's intent, without a constant multiplying a
        score. Plain unweighted RRF measured *worse* than the ranker it replaced
        on cluster-discrimination queries, where meaning is the only thing that
        separates two documents in the same genre.
        """
        results = fuse(
            vector={"prm_best": 0.7, "prm_runner_up": 0.6},
            lexical={"prm_words": 1.0},
        )

        assert [result.prompt_id for result in results] == ["prm_best", "prm_runner_up", "prm_words"]

    def test_a_candidate_below_both_floors_is_dropped(self) -> None:
        """Abstention. Cosine answers for every row, so something must say no."""
        results = fuse(vector={"prm_noise": 0.11}, lexical={"prm_noise2": 0.02})

        assert results == []

    def test_a_prompt_in_both_legs_reports_both_and_shows_its_cosine(self) -> None:
        """`similarity` stays the number that means *similar*.

        RRF orders the list; it is not a quantity anybody can read. The interface
        shows a percentage, so the reported score remains the cosine whenever
        there is one — with `matched_fields` naming what actually fired.
        """
        results = fuse(
            vector={"prm_a": 0.62},
            lexical={"prm_a": 0.44},
            keyword_matches={"prm_a"},
        )

        assert results[0].similarity == pytest.approx(0.62)
        assert results[0].matched_fields == ("semantic", "keyword", "lexical")

    def test_ties_break_deterministically(self) -> None:
        """A cursor over an unstable order pages the same prompt twice."""
        first = fuse(vector={"prm_b": 0.5, "prm_a": 0.5}, lexical={})
        second = fuse(vector={"prm_a": 0.5, "prm_b": 0.5}, lexical={})

        assert [result.prompt_id for result in first] == [result.prompt_id for result in second]

    def test_alpha_and_rrf_agree_when_one_leg_is_empty(self) -> None:
        """A sanity property: with nothing to fuse, both rankers are the vector leg."""
        vector = {"prm_a": 0.9, "prm_b": 0.5, "prm_c": 0.3}

        by_rrf = [result.prompt_id for result in fuse(vector=vector, lexical={}, ranker="rrf")]
        by_alpha = [result.prompt_id for result in fuse(vector=vector, lexical={}, ranker="alpha")]

        assert by_rrf == by_alpha == ["prm_a", "prm_b", "prm_c"]


class TestSmallCorpus:
    """Every rule that reads a share of the corpus, in a workspace that has five prompts.

    Document frequency is evidence about language, and it needs a corpus to be
    evidence about anything. Under a certain size the shares are facts about the
    sample: with four prompts the rarest possible term is in 25% of them. These
    thresholds were tuned against 200 documents, and applied unguarded to four
    they do not become strict — they become unsatisfiable, which is the one
    failure mode a 200-prompt evaluation structurally cannot show. A new
    workspace is every workspace on its first day.
    """

    def test_the_frequency_cap_does_not_fire_in_a_small_workspace(self) -> None:
        """Half of four prompts is not a stop word.

        Caught by an integration test over four seeded rows: searching `sql` in a
        library of four returned NOTHING, because two hits out of four is a 50%
        share, the cap deleted the only term, and there was nothing left to rank.
        """
        scores = lexical_scores(
            {"sql": {"prm_sql", "prm_writer"}},
            corpus_size=4,
            require_anchor=False,
        )

        assert set(scores) == {"prm_sql", "prm_writer"}

    def test_the_frequency_cap_still_fires_once_the_corpus_is_real(self) -> None:
        """The guard is about sample size, not a retreat from the rule.

        The same 50% share, measured over two hundred prompts, is the word being
        genuinely useless — and dropping it is what holds adversarial abstention
        at 100%.
        """
        scores = lexical_scores(
            {"about": {f"prm_{index}" for index in range(100)}},
            corpus_size=200,
            require_anchor=False,
        )

        assert scores == {}

    def test_an_anchor_in_a_small_workspace_is_judged_on_length_alone(self) -> None:
        """The rarity half of the anchor test is unsatisfiable here.

        Five prompts cannot produce a term in 5% of them, so requiring one would
        refuse every multi-word duplicate check until the workspace grew to
        twenty prompts — silently, and on the path whose whole job is to warn.
        """
        scores = lexical_scores(
            {"kubernetes": {"prm_k8s"}, "cluster": {"prm_k8s", "prm_other"}},
            corpus_size=5,
            require_anchor=True,
        )

        assert set(scores) == {"prm_k8s"}

    def test_a_short_fragment_still_cannot_anchor_in_a_small_workspace(self) -> None:
        """The half of the test that a small corpus CAN answer stays on.

        `gia` matching one document is an accident of substring matching whether
        the library holds five prompts or five hundred, and suspending the rarity
        test must not quietly suspend this one with it.
        """
        scores = lexical_scores(
            {"gia": {"prm_writing"}, "pho": {"prm_writing", "prm_phone"}},
            corpus_size=5,
            require_anchor=True,
        )

        assert scores == {}

    def test_a_query_of_entirely_common_words_is_refused_on_both_paths(self) -> None:
        """When the cap empties the query, the honest answer is an empty list.

        The tempting alternative is to rank by the dropped terms rather than
        return nothing — but that would mean the cap could never drop the LAST
        term a query has, which is exactly the adversarial case it exists to
        stop: one ordinary word matching half the library, returned as eighty
        suggestions. A query this corpus finds entirely unremarkable has no
        lexical signal in it, and both callers are better served by saying so.
        """
        common = {f"prm_{index}" for index in range(80)}
        term_hits = {"prompt": common, "agent": common | {"prm_extra"}}

        assert lexical_scores(term_hits, corpus_size=200, require_anchor=False) == {}
        assert lexical_scores(term_hits, corpus_size=200, require_anchor=True) == {}

    def test_the_vector_leg_is_what_answers_such_a_query(self) -> None:
        """Refusing lexically is not refusing — the legs fail independently.

        This is the property that makes the paragraph above affordable. The
        lexical leg abstaining costs a query nothing when its meaning is still
        retrievable, which is the entire argument for hybrid retrieval rather
        than a better single ranker.
        """
        results = fuse(vector={"prm_agent": 0.71}, lexical={})

        assert [result.prompt_id for result in results] == ["prm_agent"]

    def test_a_workspace_of_one_prompt_can_still_find_it(self) -> None:
        """The degenerate case of IDF, and it returned nothing at all.

        `log((N + 1) / (df + 1))` is exactly ZERO when a term is in every prompt,
        and this ranker drops the customary `+ 1` floor on purpose — it is worth
        2.6x against 1.95x in separating a 1% term from a 20% one. In a workspace
        holding one prompt every term is in every prompt, so the query weighed
        zero and search answered "no match" for a phrase printed in the only
        document there was.

        Uniform weights are the honest fallback: when rarity cannot separate two
        documents, the count of matched terms is the only signal left.
        """
        scores = lexical_scores(
            {"refund": {"prm_only"}, "request": {"prm_only"}},
            corpus_size=1,
            require_anchor=True,
        )

        assert scores == {"prm_only": pytest.approx(1.0)}

    def test_the_degenerate_fallback_ties_rather_than_orders(self) -> None:
        """And it can only ever tie, which is why returning them is the whole fix.

        The fallback fires when the summed IDF is zero, and that happens only if
        every surviving term matches every prompt — in which case every prompt
        matched the same terms and no ordering between them exists to recover.
        There is nothing here to rank; the bug was answering "nothing found" to a
        question every document answers equally.
        """
        both = {"prm_a", "prm_b"}
        scores = lexical_scores(
            {"refund": both, "policy": both}, corpus_size=2, require_anchor=False
        )

        assert scores == {"prm_a": pytest.approx(1.0), "prm_b": pytest.approx(1.0)}
