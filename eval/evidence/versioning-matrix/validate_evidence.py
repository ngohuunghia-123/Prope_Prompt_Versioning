#!/usr/bin/env python3
"""Validate immutable specs and exported Prompt Versioning evidence.

The validator is deliberately offline and standard-library only. It never calls
Prope or a provider, and it never manufactures missing evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SCENARIOS = ("S2", "S3", "S5", "S6", "S10")
COMMON_RUN_FILES = (
    "baseline-run.json",
    "baseline-cases.json",
    "candidate-run.json",
    "candidate-cases.json",
    "comparison.json",
)
S10_FILES = ("gateway-v2.json", "restore-response.json", "gateway-restored-v1.json")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
PROMPT_SECTIONS = {
    "system",
    "context",
    "instructions",
    "output_format",
    "examples",
    "constraints",
}
SECRET_KEY = re.compile(
    r"(^|_)(authorization|cookie|api_?key|secret|password|credential)(_|$)", re.I
)
SECRET_VALUE = re.compile(
    r"(?i)(?:bearer\s+[a-z0-9._~+/=-]{8,}|\bsk-[a-z0-9_-]{12,})"
)


class EvidenceError(Exception):
    """A deterministic validation failure."""


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"Không đọc được JSON {path.relative_to(ROOT)}: {exc}") from exc


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def validate_specs() -> list[str]:
    lock = load_json(ROOT / "spec-lock.json")
    locked_files = lock.get("files")
    require(isinstance(locked_files, dict), "spec-lock.json thiếu object files")
    require(len(locked_files) == len(SCENARIOS), "Spec lock phải chứa đúng 5 file")

    found: set[str] = set()
    messages: list[str] = []
    for relative_name, expected_hash in locked_files.items():
        path = ROOT / relative_name
        require(path.is_file(), f"Thiếu spec đã khóa: {relative_name}")
        actual_hash = sha256(path)
        require(actual_hash == expected_hash, f"Spec hash đã thay đổi: {relative_name}")

        spec = load_json(path)
        scenario = spec.get("scenario_id")
        require(scenario in SCENARIOS, f"scenario_id không hợp lệ trong {relative_name}")
        require(scenario not in found, f"scenario_id bị trùng: {scenario}")
        found.add(scenario)

        dataset = spec.get("dataset", {})
        cases = dataset.get("cases")
        require(isinstance(cases, list) and len(cases) == 1, f"{scenario} phải có đúng 1 manual case")
        assertions = cases[0].get("assertions")
        require(isinstance(assertions, list) and assertions, f"{scenario} thiếu assertions")
        require(dataset.get("kind") in {"golden", "regression"}, f"{scenario} dataset kind không hợp lệ")

        revisions = spec.get("revisions", {})
        for revision_name in ("baseline", "candidate"):
            body = revisions.get(revision_name, {}).get("body")
            require(isinstance(body, str) and body.strip(), f"{scenario} thiếu body {revision_name}")
            try:
                root = ET.fromstring(f"<prompt>{body}</prompt>")
            except ET.ParseError as exc:
                raise EvidenceError(f"{scenario} {revision_name} không phải XML hợp lệ: {exc}") from exc
            tags = [child.tag for child in root]
            require(tags and set(tags) <= PROMPT_SECTIONS, f"{scenario} {revision_name} có XML section không được hỗ trợ")
            require(all(not child.attrib and not list(child) for child in root), f"{scenario} {revision_name} có attribute/nested XML không hợp lệ")

        binding = spec.get("runtime_binding", {})
        require(
            binding.get("binding_policy") == "same_verified_byok_for_baseline_and_candidate",
            f"{scenario} thiếu chính sách cùng BYOK provider/model",
        )
        require(isinstance(spec.get("expected_evidence"), dict), f"{scenario} thiếu expected_evidence")
        messages.append(f"{scenario}: spec lock OK ({actual_hash[:12]}…)")

    require(found == set(SCENARIOS), "Spec lock không bao phủ đủ S2/S3/S5/S6/S10")
    return messages


def scan_secrets(value: Any, location: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            child = f"{location}.{key_text}"
            if SECRET_KEY.search(key_text):
                findings.append(child)
            findings.extend(scan_secrets(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(scan_secrets(item, f"{location}[{index}]"))
    elif isinstance(value, str) and SECRET_VALUE.search(value):
        findings.append(location)
    return findings


def count_outcomes(cases: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"pass": 0, "fail": 0, "error": 0}
    for case in cases:
        outcome = case.get("outcome")
        require(outcome in counts, f"Case outcome không hợp lệ: {outcome!r}")
        counts[outcome] += 1
        require(isinstance(case.get("attempt_count"), int), "Case thiếu attempt_count")
        if outcome != "error":
            require(case.get("output_content") is not None, "Completed case thiếu actual output")
    return counts


def validate_run(run: dict[str, Any], cases: list[dict[str, Any]], label: str) -> None:
    status = run.get("status")
    require(status in {"completed", "refused"}, f"{label} chưa terminal: {status!r}")
    if status == "completed":
        counts = count_outcomes(cases)
        for outcome, field in (("pass", "pass_count"), ("fail", "fail_count"), ("error", "error_count")):
            require(run.get(field) == counts[outcome], f"{label} {field} không khớp case results")
        require(sum(counts.values()) == len(cases), f"{label} tổng outcome không khớp")
        require(cases, f"{label} completed nhưng không có case")
    else:
        require(run.get("refused_reason"), f"{label} refused nhưng thiếu refused_reason")


def comparison_block(raw: Any, suite_id: str) -> dict[str, Any]:
    require(isinstance(raw, list), "comparison.json phải là JSON array")
    matches = [item for item in raw if item.get("suite_id") == suite_id]
    require(len(matches) == 1, "Không tìm thấy đúng một comparison block cho suite")
    return matches[0]


def decimal(value: Any, label: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise EvidenceError(f"{label} không phải số hợp lệ") from exc


def scenario_context(context: dict[str, Any], scenario: str) -> dict[str, Any]:
    item = context.get("scenarios", {}).get(scenario)
    require(isinstance(item, dict), f"execution-context thiếu {scenario}")
    return item


def outcome(run: dict[str, Any], name: str) -> int:
    return int(run.get(f"{name}_count", -1))


def header(artifact: dict[str, Any], name: str) -> Any:
    headers = artifact.get("headers", {})
    require(isinstance(headers, dict), "Gateway artifact thiếu headers object")
    normalized = {str(key).lower(): value for key, value in headers.items()}
    return normalized.get(name.lower())


def validate_scenario(scenario: str, context: dict[str, Any]) -> list[str]:
    directory = ROOT / "runs" / scenario
    expected_files = COMMON_RUN_FILES + (S10_FILES if scenario == "S10" else ())
    missing = [name for name in expected_files if not (directory / name).is_file()]
    require(not missing, f"{scenario} thiếu artifact: {', '.join(missing)}")

    artifacts = {name: load_json(directory / name) for name in expected_files}
    for name, artifact in artifacts.items():
        findings = scan_secrets(artifact)
        require(not findings, f"{scenario}/{name} chứa key/value giống secret: {', '.join(findings)}")

    baseline = artifacts["baseline-run.json"]
    candidate = artifacts["candidate-run.json"]
    baseline_cases = artifacts["baseline-cases.json"]
    candidate_cases = artifacts["candidate-cases.json"]
    require(isinstance(baseline_cases, list), f"{scenario} baseline-cases phải là array")
    require(isinstance(candidate_cases, list), f"{scenario} candidate-cases phải là array")
    validate_run(baseline, baseline_cases, f"{scenario} baseline")
    validate_run(candidate, candidate_cases, f"{scenario} candidate")
    require(baseline.get("suite_id") == candidate.get("suite_id"), f"{scenario} khác suite ID")

    ctx = scenario_context(context, scenario)
    require(baseline.get("version_id") == ctx.get("baseline_version_id"), f"{scenario} baseline version sai")
    require(candidate.get("version_id") == ctx.get("candidate_version_id"), f"{scenario} candidate version sai")
    require(ctx.get("provider_config_id") == context.get("provider_config_id"), f"{scenario} provider config không đồng nhất")
    require(ctx.get("upstream_model") == context.get("upstream_model"), f"{scenario} upstream model không đồng nhất")
    require(ctx.get("human_decision") in {"released", "blocked", "not_promoted"}, f"{scenario} thiếu human_decision")

    block = comparison_block(artifacts["comparison.json"], str(candidate.get("suite_id")))
    require(block.get("candidate_run_id") == candidate.get("run_id"), f"{scenario} comparison candidate run sai")
    require(block.get("baseline_run_id") == baseline.get("run_id"), f"{scenario} comparison baseline run sai")

    if scenario == "S2":
        require(outcome(baseline, "pass") == 1 and outcome(candidate, "pass") == 1, "S2 không tái hiện pass/pass")
        require(baseline.get("cost_amount") is not None and candidate.get("cost_amount") is not None, "S2 thiếu priced cost")
        require(baseline.get("input_tokens") is not None and candidate.get("input_tokens") is not None, "S2 thiếu usage")
        base_cost = decimal(baseline["cost_amount"], "S2 baseline cost")
        require(base_cost > 0, "S2 baseline cost phải lớn hơn 0")
        actual_ratio = decimal(candidate["cost_amount"], "S2 candidate cost") / base_cost
        require(actual_ratio >= Decimal("1.20"), f"S2 cost ratio chỉ đạt {actual_ratio}")
        require(block.get("cost_warning") is True, "S2 thiếu cost_warning=true")
        require(ctx.get("human_decision") == "not_promoted", "S2 phải ghi nhận không promote")
    elif scenario == "S3":
        require(outcome(baseline, "pass") == 1 and outcome(candidate, "fail") == 1, "S3 không tái hiện pass→fail")
        require(ctx.get("acknowledgement_required_for_override") is True, "S3 chưa ghi nhận yêu cầu acknowledgement khi override")
        require(ctx.get("human_decision") == "blocked", "S3 phải ghi nhận BLOCK recommendation")
    elif scenario == "S5":
        require(outcome(baseline, "fail") == 1 and outcome(candidate, "pass") == 1, "S5 không tái hiện fail→pass")
        require(outcome(candidate, "error") == 0, "S5 candidate có error")
        require(ctx.get("human_decision") == "released", "S5 chưa chứng minh human release")
    elif scenario == "S6":
        require(outcome(baseline, "pass") == 1, "S6 baseline không pass")
        require(candidate.get("status") == "refused", "S6 candidate không refused")
        require(candidate.get("refused_reason") == "modality_mismatch", "S6 sai refusal reason")
        require(ctx.get("acknowledgement_required_for_override") is True, "S6 chưa ghi nhận yêu cầu acknowledgement khi override")
        require(ctx.get("human_decision") == "blocked", "S6 phải ghi nhận BLOCK recommendation")
    else:
        require(outcome(baseline, "pass") == 1 and outcome(candidate, "pass") == 1, "S10 eval không pass/pass")
        gateway_v2 = artifacts["gateway-v2.json"]
        gateway_v1 = artifacts["gateway-restored-v1.json"]
        restore = artifacts["restore-response.json"]
        require(header(gateway_v2, "x-prope-version-id") == ctx.get("candidate_version_id"), "S10 gateway chưa phục vụ V2")
        require(header(gateway_v1, "x-prope-version-id") == ctx.get("baseline_version_id"), "S10 gateway chưa restore V1")
        require(header(gateway_v2, "x-prope-revision") is not None, "S10 gateway V2 thiếu revision header")
        require(header(gateway_v1, "x-prope-revision") is not None, "S10 gateway V1 thiếu revision header")
        require(header(gateway_v2, "x-prope-model") == header(gateway_v1, "x-prope-model"), "S10 gateway model thay đổi")
        require(isinstance(restore.get("reason"), str) and restore["reason"].strip(), "S10 restore thiếu reason")
        require(decimal(gateway_v1.get("elapsed_seconds"), "S10 elapsed_seconds") <= Decimal("300"), "S10 restore vượt quá 5 phút")
        require(ctx.get("human_decision") == "released", "S10 chưa chứng minh human release")

    screenshots = [
        path for path in (ROOT / "screenshots").glob(f"{scenario}-*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    ]
    require(screenshots, f"{scenario} thiếu screenshot")
    return [f"{scenario}: REPRODUCED"]


def validate_runtime() -> list[str]:
    context = load_json(ROOT / "execution-context.json")
    require(context.get("status") == "EXECUTED", "execution-context vẫn PENDING_RUNTIME")
    require(context.get("provider_config_id"), "Thiếu provider_config_id")
    require(context.get("upstream_model"), "Thiếu upstream_model")
    require(context.get("actors", {}).get("author_id"), "Thiếu Author actor")
    require(context.get("actors", {}).get("reviewer_id"), "Thiếu Reviewer actor")
    require(context["actors"]["author_id"] != context["actors"]["reviewer_id"], "Author và Reviewer phải là hai actor khác nhau")

    messages: list[str] = []
    for scenario in SCENARIOS:
        messages.extend(validate_scenario(scenario, context))
    return messages


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--specs-only", action="store_true", help="Chỉ kiểm tra spec lock, không yêu cầu runtime evidence")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        messages = validate_specs()
        if not args.specs_only:
            messages.extend(validate_runtime())
    except EvidenceError as exc:
        print(f"NOT_REPRODUCED: {exc}", file=sys.stderr)
        return 1

    print("\n".join(messages))
    print("SPECS_VALID" if args.specs_only else "EVIDENCE_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
