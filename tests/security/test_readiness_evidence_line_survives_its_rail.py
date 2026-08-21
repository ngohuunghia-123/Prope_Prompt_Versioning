"""AC-5 / SR-7 — the one generated line, and the rail it passes before storage.

**This module's normal operating input is other people's prompt bodies, and one
of them may be an attacker's.** That is not a hypothetical risk profile: it is
what the module reads on every card. Almost everything it emits is a closed
``rule_id`` that a hostile body cannot influence — the ``vi`` catalogue supplies
the sentence and Prope supplies the code. The one exception is the generated
evidence line (D-09), and it is therefore the one place a body could steer text
onto a colleague's screen.

**The rail runs before STORAGE, not before render**, and the distinction is the
test's subject as much as the patterns are. A rail applied at render is a rail
somebody bypasses with a different client — and this product's API is the
contract, not its SPA. Storing the redacted form means every reader gets the same
string and there is no code path left where the raw one is still available.

The database carries a second, looser bound
(``ck_readiness_probe_case_result_detail_is_bounded`` at 2000 characters against
the rail's 400). Deliberately looser: a backstop that fires at the same threshold
as the rail can never tell you the rail was skipped.
"""

import pytest

from prope.prompt_readiness.domain import MAX_EVIDENCE_CHARACTERS, redact_evidence


@pytest.mark.parametrize(
    "hostile",
    [
        "Xem thêm tại https://attacker.example/steal?c=1",
        "Chi tiết [ở đây](https://attacker.example/phish)",
        "Ảnh ![logo](http://attacker.example/pixel.gif)",
        "Gửi tới ftp://attacker.example/drop",
        "Dữ liệu data:text/html;base64,PHNjcmlwdD4=",
    ],
)
def test_no_url_or_link_survives(hostile: str) -> None:
    """A finding is read on a screen. A clickable one is an exfiltration channel."""
    cleaned = redact_evidence(hostile)
    for marker in ("http://", "https://", "ftp://", "data:", "](" ):
        assert marker not in cleaned, f"{marker!r} survived: {cleaned!r}"


@pytest.mark.parametrize(
    "secret",
    [
        "prope_key_01M0D06CT10HD2G7DJK8TVXT9Q_Ffr8bvLBDRMe7MJwb92ZXSZjXvy47PVb8suk31",
        "sk-proj-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "ghp_1234567890abcdefghijklmnopqrstuvwxyzABCD",
    ],
)
def test_credential_shapes_are_redacted(secret: str) -> None:
    """Matched on SHAPE and not against a list — the list is always one provider out of date.

    A prompt body can legitimately contain a key by mistake, and a readiness
    finding quoting it would take a secret that was in one workspace's prompt and
    put it on a card, in a report, and into a frozen row that is never deleted.
    """
    cleaned = redact_evidence(f"Tìm thấy khoá {secret} trong phần thân prompt.")
    assert secret not in cleaned
    assert "đã ẩn" in cleaned


def test_markup_cannot_survive_into_the_line() -> None:
    """The card renders plain text; the rail is what makes that assumption safe."""
    cleaned = redact_evidence("<script>alert(1)</script><img src=x onerror=y>")
    assert "<" not in cleaned
    assert ">" not in cleaned


def test_the_line_is_capped_and_flattened() -> None:
    """A body supplying fifty newlines would push every other finding off the card."""
    cleaned = redact_evidence("dòng\n" * 500)
    assert "\n" not in cleaned
    assert len(cleaned) <= MAX_EVIDENCE_CHARACTERS


def test_an_ordinary_vietnamese_sentence_passes_through_intact() -> None:
    """The rail must not be so blunt that the feature stops working.

    A test that only proved things are removed would pass against
    ``return ""`` — which is safe, useless, and exactly the implementation
    somebody reaches for when a rail is hard to get right.
    """
    sentence = "Biến {{cau_hoi}} nằm trong khối instructions, dòng 4."
    assert redact_evidence(sentence) == sentence
