"""The documentation corpus and its retrieval.

The property that matters most is the one deck 4 (p35) describes: a pipeline
that returns nothing must not look like a pipeline with nothing to return. So
these tests assert the *lexical floor* — retrieval works with the embedding
provider unreachable, reports that it did, and still answers the questions the
corpus covers.

Every test runs with `allow_dense=False`. That is not a shortcut around the
network; it is the degraded mode being the thing under test.
"""

import pytest

from prope.chat_orchestrator import knowledge


@pytest.fixture(autouse=True)
def _fresh_corpus():
    knowledge.reset_corpus()
    yield
    knowledge.reset_corpus()


def test_the_corpus_ships_with_the_package() -> None:
    """`docs/` is dockerignored, so a corpus there would exist in every test run
    and in no deployment — the worst possible split."""
    corpus = knowledge.load_corpus()

    assert len(corpus) >= 20
    assert len({chunk.document for chunk in corpus}) >= 5


def test_a_chunk_is_a_heading_and_its_section() -> None:
    """Chunking by heading rather than by character count (deck 4, p19): cutting
    mid-clause makes the agent quote half a rule, still with a citation."""
    corpus = knowledge.load_corpus()

    for chunk in corpus:
        assert chunk.heading
        assert chunk.text
        assert "\n## " not in chunk.text
        assert chunk.id.startswith(chunk.document)


def test_the_title_block_before_the_first_heading_is_not_a_chunk() -> None:
    """It is a heading and a sentence of framing; a chunk made of it would win
    generic questions and cite nothing useful."""
    corpus = knowledge.load_corpus()

    assert not any(chunk.heading.startswith("Prope là gì") for chunk in corpus)


@pytest.mark.parametrize(
    ("question", "expected_document"),
    [
        ("Quy trình duyệt và phát hành hoạt động thế nào?", "02-vong-doi-prompt"),
        ("Break-glass là gì?", "02-vong-doi-prompt"),
        ("Vì sao prompt của tôi hiện không tìm thấy?", "03-phan-quyen"),
        ("Nhập prompt gồm những bước nào?", "04-import-va-tim-kiem"),
        ("Gateway phục vụ bản revision nào?", "05-gateway"),
        ("Trợ lý có tự lưu prompt không?", "06-tro-ly"),
    ],
)
async def test_the_lexical_leg_alone_answers_the_questions_the_corpus_covers(
    question: str, expected_document: str
) -> None:
    outcome = await knowledge.retrieve(question, allow_dense=False)

    assert outcome.lexical_ran
    assert not outcome.dense_ran
    assert outcome.chunks, question
    assert expected_document in {scored.chunk.document for scored in outcome.chunks}


async def test_diacritics_do_not_have_to_match() -> None:
    """Vietnamese is typed both ways and searched both ways. ADR-0048 settled
    this for prompt search; the same decision applies one layer up."""
    with_marks = await knowledge.retrieve("phát hành", allow_dense=False)
    without = await knowledge.retrieve("phat hanh", allow_dense=False)

    assert {c.chunk.id for c in with_marks.chunks} == {c.chunk.id for c in without.chunks}
    assert with_marks.chunks


async def test_a_question_the_corpus_does_not_cover_returns_nothing() -> None:
    """An empty retrieval is the honest answer, and the responder's grounding
    rule turns it into "the documentation does not cover this" rather than into
    a confident paragraph about some other product."""
    outcome = await knowledge.retrieve("cách nướng bánh mì men tự nhiên", allow_dense=False)

    assert outcome.chunks == ()


async def test_the_outcome_says_which_leg_ran() -> None:
    """`dense_ran` is what lets the turn report a degradation instead of silently
    answering worse."""
    outcome = await knowledge.retrieve("phân quyền", allow_dense=False)

    assert outcome.dense_ran is False
    assert outcome.lexical_ran is True


async def test_retrieval_order_is_stable_across_identical_questions() -> None:
    """A cited answer that reorders between two identical questions reads as the
    system being unsure of itself."""
    first = await knowledge.retrieve("phát hành", allow_dense=False)
    second = await knowledge.retrieve("phát hành", allow_dense=False)

    assert [c.chunk.id for c in first.chunks] == [c.chunk.id for c in second.chunks]


async def test_the_limit_is_honoured() -> None:
    outcome = await knowledge.retrieve("prompt", limit=2, allow_dense=False)

    assert len(outcome.chunks) <= 2


def test_a_term_appearing_everywhere_is_downweighted_and_not_deleted() -> None:
    """No document-frequency CAP here, unlike `prompt_search.ranking`.

    That module ranks 375 documents where a term in a quarter of them is noise.
    This ranks thirty chunks that are all about one product, where "prompt"
    appearing in a third of them is the corpus being coherent — deleting it would
    make the corpus unsearchable by its own subject.
    """
    corpus = knowledge.load_corpus()

    scores = knowledge.lexical_scores("revision", corpus)

    assert scores, "a term the corpus genuinely uses must still score"


def test_the_fingerprint_reports_counts_rather_than_a_hash() -> None:
    """It is logged, and a hash is a value nobody can act on."""
    fingerprint = knowledge.corpus_fingerprint()

    assert "docs/" in fingerprint and "chunks" in fingerprint
