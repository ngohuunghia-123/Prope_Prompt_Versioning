"""The eval advisor: what to measure, and what the results said.

Two deterministic services behind the evaluation tab's agent buttons:

**Dataset suggestion** matches a prompt body against the catalogue's structured
metadata — the same ``description``/``tags``/``applicability`` fields a person
reads — and ranks sets by how well their aspect fits what the prompt does. The
matching is deliberately *not* a model call: a suggestion only proposes a tick,
the person still makes it, and a deterministic scorer cannot hallucinate a set
that does not exist or invent a reason that is not in the metadata. Universal
sets (``applicability is None``) are proposed for every prompt; conditional sets
are proposed only when a body signal trips their aspect, because proposing a
JSON-format set to a prose prompt is the exact trap ``applicability`` exists to
prevent.

**Run analysis** groups a finished run set's failing case results by suite and
assertion type, and turns each group into one finding with fixed advice text per
assertion type. The advice is a table, not a generation: "thêm giới hạn độ dài"
is what a ``max_length`` failure means, whether or not a model is available to
say it more politely. Severity reuses the improvement vocabulary (``advice`` /
``warning``, ADR-0067) — an analysis never blocks anything.
"""

import re
from dataclasses import dataclass
from typing import Final

from prope.evaluation.domain import AssertionType

__all__ = [
    "AdviceFinding",
    "DatasetSuggestion",
    "SUGGESTION_CAP",
    "analyze_runs",
    "suggest_datasets",
]

#: The tree refuses more than this per prompt; suggesting more is noise.
SUGGESTION_CAP: Final = 8

#: The Vietnamese-consistency signal: a real Vietnamese sentence carries
#: several marked characters, and an English body carries none. Same heuristic
#: the ``nhat-quan-tieng-viet`` set asserts with.
_VIETNAMESE_MARKS: Final = re.compile("[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]")

_STRUCTURED_HINTS: Final = ("json", '"type"', "schema", "có cấu trúc")
_TOOL_HINTS: Final = ("tool", "function", "công cụ", "lệnh gọi", "api call", "gọi hàm")
_ASSISTANT_HINTS: Final = ("trợ lý", "chatbot", "hội thoại", "assistant", "người dùng", "khách hàng")
_CONTEXT_HINTS: Final = ("ngữ cảnh", "tài liệu", "context", "dựa trên", "knowledge", "tra cứu")
_SENSITIVE_HINTS: Final = ("email", "số điện thoại", "điện thoại", "cá nhân", "nhạy cảm", "an toàn", "guardrail", "từ chối")
_FORMAT_HINTS: Final = ("định dạng", "format", "gạch đầu dòng", "tối đa", "không quá", "một câu", "chữ thường")


def _has_any(body: str, hints: tuple[str, ...]) -> bool:
    return any(hint in body for hint in hints)


@dataclass(frozen=True, slots=True)
class DatasetSuggestion:
    dataset_id: str
    name: str
    reason: str
    confidence: float


def suggest_datasets(
    prompt_body: str,
    catalogue: list[tuple[str, str, str | None, str]],
) -> tuple[DatasetSuggestion, ...]:
    """Rank catalogue sets for this body.

    ``catalogue`` rows are ``(dataset_id, name, applicability, description)``.
    A set with no ``applicability`` is universal and proposed for every prompt;
    a conditional set is proposed only when its slug's body signal trips, and
    the reason names the signal so the person can judge the proposal in one
    glance. Unknown slugs fall through to the metadata itself.
    """
    body = prompt_body.lower()
    vietnamese = len(set(_VIETNAMESE_MARKS.findall(prompt_body))) >= 4

    scores: dict[str, tuple[float, str]] = {
        "chong-tiem-prompt": (0.9, "Mọi prompt nhận đầu vào người dùng đều cần bằng chứng chống ghi đè chỉ thị."),
        "chong-jailbreak": (0.8, "Mọi prompt đều có thể bị lái ra khỏi vai trò bằng khung truyện; bộ này đo điều đó."),
        "guardrail-noi-dung": (0.75, "Đo khả năng từ chối yêu cầu nhạy cảm — thuộc tính đúng của mọi trợ lý."),
        "ro-ri-prompt-he-thong": (0.85, "Prompt có phần hệ thống thì đều có thể bị hỏi ngược; bộ này bắt hiện tượng rò rỉ."),
        "bien-chua-thay-the": (0.8, "Bắt placeholder chưa thay — lỗi rẻ nhất và thường gặp nhất sau mỗi lần sửa prompt."),
        "dau-vao-bien": (0.7, "Độ bền với đầu vào rỗng, dài, dị dạng: mạng lưới hồi quy cho mọi prompt."),
        "hanh-vi-tro-ly": (0.8 if _has_any(body, _ASSISTANT_HINTS) else 0.0,
                           "Prompt vận hành như trợ lý hội thoại, nên hành vi từ chối sáo màn và lộ danh tính cần được đo."),
        "nho-da-luot": (0.75 if _has_any(body, _ASSISTANT_HINTS) else 0.0,
                        "Prompt chạy trong hội thoại, nên khả năng giữ bối cảnh giữa các lượt cần được đo."),
        "nhat-quan-tieng-viet": (0.85 if vietnamese else 0.0,
                                 "Prompt được viết bằng tiếng Việt, nên nhất quán ngôn ngữ của câu trả lời cần được đo."),
        "tuan-thu-dinh-dang": (0.7 if _has_any(body, _FORMAT_HINTS) else 0.5,
                               "Prompt có ràng buộc về hình thức trả lời, hoặc chưa từng bị đo về khả năng làm theo chỉ thị định dạng."),
        "dinh-dang-json": (0.85 if _has_any(body, _STRUCTURED_HINTS) else 0.0,
                           "Prompt yêu cầu đầu ra JSON, nên cấu trúc đối tượng trả về cần được xác minh."),
        "schema-goi-cong-cu": (0.9 if _has_any(body, _TOOL_HINTS) else 0.0,
                               "Prompt phát lệnh gọi công cụ, nên mẫu (schema) của lệnh gọi cần được xác minh."),
        "kiem-chung-ngu-canh": (0.8 if _has_any(body, _CONTEXT_HINTS) else 0.0,
                                "Prompt trả lời dựa trên ngữ cảnh được cấp, nên khả năng bám tài liệu và từ chối ngoài tài liệu cần được đo."),
        "khong-lo-lo-pii": (0.7 if _has_any(body, _SENSITIVE_HINTS) else 0.5,
                            "Đảm bảo câu trả lời không mang hình thức dữ liệu cá nhân — tính chất đúng của mọi trợ lý."),
    }

    suggestions: list[DatasetSuggestion] = []
    for dataset_id, name, applicability, description in catalogue:
        slug = dataset_id.split(":")[-1].split("@")[0]
        if slug in scores:
            confidence, reason = scores[slug]
        elif applicability is None:
            confidence, reason = 0.5, description[:160]
        else:
            continue
        if confidence <= 0.0:
            continue
        suggestions.append(DatasetSuggestion(dataset_id, name, reason, round(confidence, 2)))

    suggestions.sort(key=lambda item: item.confidence, reverse=True)
    return tuple(suggestions[:SUGGESTION_CAP])


@dataclass(frozen=True, slots=True)
class AdviceFinding:
    suite_name: str
    assertion_type: str
    failed: int
    total: int
    issue: str
    advice: str
    severity: str


_ADVICE: Final[dict[str, tuple[str, str]]] = {
    AssertionType.REGEX.value: (
        "Câu trả lời vi phạm mẫu kiểm tra (regex).",
        "Rà lại phần chỉ thị chi phối hình thức câu trả lời: nêu rõ điều không được làm và cách từ chối tường minh khi case thuộc bộ red-team.",
    ),
    AssertionType.FORBIDDEN_PHRASE.value: (
        "Câu trả lời chứa cụm bị cấm.",
        "Liệt kê tường minh trong prompt những cụm/ký hiệu không được xuất hiện và hướng dẫn cách xử lý thay thế.",
    ),
    AssertionType.REQUIRED_PHRASE.value: (
        "Câu trả lời thiếu thành phần bắt buộc.",
        "Yêu cầu tường minh trong prompt về thông tin hoặc thành phần phải có trong mọi câu trả lời.",
    ),
    AssertionType.JSON_SCHEMA.value: (
        "Đầu ra lệch schema.",
        "Siết phần <output_format>: liệt kê các trường bắt buộc, kiểu dữ liệu và cấm văn xuôi bọc ngoài JSON.",
    ),
    AssertionType.MAX_LENGTH.value: (
        "Câu trả lời vượt độ dài cho phép.",
        "Thêm giới hạn độ dài hoặc số câu tường minh, và yêu cầu bỏ phần lan man không cần thiết.",
    ),
    AssertionType.MAX_LATENCY.value: (
        "Vượt trần độ trễ.",
        "Xem lại cấu hình provider/model và độ dài đầu vào thay vì nội dung prompt — độ trễ hiếm khi do văn bản.",
    ),
    AssertionType.MAX_COST.value: (
        "Vượt trần chi phí.",
        "Rà lại model được gắn và số token đầu vào; cân nhắc rút gọn ngữ cảnh tĩnh trong prompt.",
    ),
}
_GENERIC_ADVICE: Final = (
    "Case không đạt.",
    "Đọc chi tiết case trong lần chạy để xác định đúng điều kiện bị trượt, rồi siết chỉ thị tương ứng trong prompt.",
)
_ERROR_ADVICE: Final = (
    "Case lỗi thực thi thay vì trượt điều kiện.",
    "Kiểm tra provider binding và dạng đầu ra (modality) của prompt với bộ dữ liệu trước khi đọc tiếp kết quả.",
)


def _advice_for(assertion_type: str, errored: bool) -> tuple[str, str]:
    if errored:
        return _ERROR_ADVICE
    return _ADVICE.get(assertion_type, _GENERIC_ADVICE)


def analyze_runs(
    runs: list[tuple[str, str, int, int, int]],
    case_results: list[tuple[str, list[tuple[bool, str, bool]]]],
) -> tuple[str, tuple[AdviceFinding, ...]]:
    """Turn terminal runs into a brief and per-group findings.

    ``runs`` rows are ``(suite_name, status, passed, failed, errors)``; each
    ``case_results`` row is ``(suite_name, [(passed, assertion_type, errored), ...])``
    — one entry per assertion result of the run's cases. Grouping is by suite and
    assertion type, because that is the level a prompt edit can act on.
    """
    if not runs:
        return (
            "Chưa có lần chạy hoàn thành nào cho revision này. Hãy gắn bộ dữ liệu và chạy thử trước.",
            (),
        )

    total_cases = sum(passed + failed + errors for _, _, passed, failed, errors in runs)
    total_failed = sum(failed + errors for _, _, passed, failed, errors in runs)
    worst = max(runs, key=lambda run: run[2] + run[3] + run[4])

    groups: dict[tuple[str, str], list[tuple[bool, str, bool]]] = {}
    for suite_name, results in case_results:
        for passed, assertion_type, errored in results:
            if passed:
                continue
            groups.setdefault((suite_name, assertion_type), []).append((passed, assertion_type, errored))

    findings: list[AdviceFinding] = []
    for (suite_name, assertion_type), entries in groups.items():
        issue, advice = _advice_for(assertion_type, any(errored for _, _, errored in entries))
        share = len(entries) / total_cases if total_cases else 0.0
        findings.append(
            AdviceFinding(
                suite_name=suite_name,
                assertion_type=assertion_type,
                failed=len(entries),
                total=total_cases,
                issue=issue,
                advice=advice,
                severity="warning" if share >= 0.1 else "advice",
            )
        )
    findings.sort(key=lambda item: item.failed, reverse=True)

    if total_failed == 0:
        brief = (
            f"{len(runs)} lần chạy đã hoàn thành với {total_cases} case, không có case nào trượt. "
            "Không có gợi ý chỉnh sửa nào cần thiết tại thời điểm này."
        )
    else:
        brief = (
            f"{total_failed}/{total_cases} case chưa đạt qua {len(runs)} lần chạy; bộ nặng nhất là "
            f"“{worst[0]}”. {len(findings)} nhóm vấn đề được gộp theo điều kiện kiểm tra — xử lý nhóm "
            "nhiều case trượt nhất trước, mỗi nhóm gợi ý một sửa đổi cụ thể cho prompt."
        )
    return brief, tuple(findings)
