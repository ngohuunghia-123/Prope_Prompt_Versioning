import json
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import jsonschema
import regex
from jsonschema.exceptions import SchemaError, ValidationError

from prope.evaluation.domain import (
    ASSERTION_TYPES_BY_MODALITY,
    MAX_ASSERTION_INPUT_CHARACTERS,
    REGEX_TIMEOUT_SECONDS,
    AssertionOutcome,
    AssertionPatternInvalid,
    AssertionSpec,
    AssertionType,
    CaseErrorCode,
    ModalityMismatch,
    OutputModality,
)

__all__ = [
    "ASSET_SCHEMES",
    "AssertionTimeout",
    "AssertionUnevaluable",
    "CaseObservation",
    "check_modality",
    "compile_assertions",
    "evaluate",
    "evaluate_all",
    "parse_assertions",
    "returned_shape",
]

ASSET_SCHEMES = ("http://", "https://", "data:", "s3://", "gs://", "file://")


class AssertionTimeout(Exception):  # noqa: N818
    def __init__(self, assertion_type: AssertionType) -> None:
        super().__init__(
            f"the {assertion_type.value} assertion did not finish inside "
            f"{REGEX_TIMEOUT_SECONDS}s and was aborted"
        )
        self.assertion_type = assertion_type
        self.error_code = CaseErrorCode.ASSERTION_TIMEOUT


class AssertionUnevaluable(Exception):  # noqa: N818
    def __init__(self, assertion_type: AssertionType, detail: str) -> None:
        super().__init__(f"the {assertion_type.value} assertion could not be evaluated: {detail}")
        self.assertion_type = assertion_type
        self.detail = detail
        self.error_code = CaseErrorCode.ASSERTION_UNEVALUABLE


@dataclass(frozen=True, slots=True)
class CaseObservation:
    content: str | None
    latency_ms: int | None = None
    cost: Decimal | None = None

    @property
    def text(self) -> str:
        return self.content or ""

    @property
    def payload(self) -> Any:
        if self.content is None:
            return None
        try:
            return json.loads(self.content)
        except (TypeError, ValueError):
            return None


def returned_shape(content: str | None) -> str:
    if content is None:
        return "empty"

    stripped = content.strip()
    if not stripped:
        return "empty"

    if stripped.lower().startswith(ASSET_SCHEMES):
        return "asset_reference"

    if stripped[0] in "{[":
        try:
            json.loads(stripped)
        except ValueError:
            return "text"
        return "structured"

    return "text"


def check_modality(declared: OutputModality, content: str | None) -> None:
    shape = returned_shape(content)
    if shape == "empty":
        return

    if declared is OutputModality.TEXT and shape != "text":
        raise ModalityMismatch(declared, shape)

    if declared is OutputModality.STRUCTURED and shape == "text":
        raise ModalityMismatch(declared, shape)


def parse_assertions(raw: Sequence[Any]) -> tuple[AssertionSpec, ...]:
    specs: list[AssertionSpec] = []
    for entry in raw:
        if not isinstance(entry, dict) or "type" not in entry:
            raise ValueError(f"{entry!r} is not an assertion; every entry carries a type")
        specs.append(AssertionSpec(type=AssertionType(entry["type"]), value=entry.get("value")))
    return tuple(specs)


def compile_assertions(
    specs: Sequence[AssertionSpec], modality: OutputModality, ordinal: int
) -> tuple[AssertionSpec, ...]:
    allowed = ASSERTION_TYPES_BY_MODALITY[modality]

    for spec in specs:
        if spec.type not in allowed:
            raise AssertionPatternInvalid(
                ordinal,
                f"{spec.type.value} is not registered for output_modality={modality.value}",
            )

        if spec.type is AssertionType.REGEX:
            try:
                regex.compile(str(spec.value))
            except regex.error as error:
                raise AssertionPatternInvalid(ordinal, str(error)) from error

        if spec.type is AssertionType.JSON_SCHEMA:
            try:
                jsonschema.Draft202012Validator.check_schema(spec.value)
            except SchemaError as error:
                raise AssertionPatternInvalid(ordinal, error.message) from error

        if spec.type in (
            AssertionType.MAX_LENGTH,
            AssertionType.MAX_LATENCY,
            AssertionType.ASSET_COUNT,
        ):
            if not isinstance(spec.value, int) or isinstance(spec.value, bool) or spec.value < 0:
                raise AssertionPatternInvalid(
                    ordinal, f"{spec.type.value} takes a non-negative integer"
                )

        if spec.type is AssertionType.MAX_COST:
            try:
                Decimal(str(spec.value))
            except (ArithmeticError, TypeError, ValueError) as error:
                raise AssertionPatternInvalid(
                    ordinal, f"{spec.type.value} takes a decimal amount"
                ) from error

    return tuple(specs)


def _bounded(value: str) -> str:
    return value[:MAX_ASSERTION_INPUT_CHARACTERS]


def _exact(spec: AssertionSpec, observation: CaseObservation) -> AssertionOutcome:
    passed = observation.text == str(spec.value)
    return AssertionOutcome(spec.type, passed, None if passed else "the output is not equal")


def _substring(spec: AssertionSpec, observation: CaseObservation) -> AssertionOutcome:
    passed = str(spec.value) in observation.text
    return AssertionOutcome(spec.type, passed, None if passed else "the substring is absent")


def _regex(spec: AssertionSpec, observation: CaseObservation) -> AssertionOutcome:
    subject = _bounded(observation.text)
    try:
        pattern = regex.compile(str(spec.value))
    except regex.error as error:
        raise AssertionUnevaluable(spec.type, str(error)) from error

    try:
        found = pattern.search(subject, timeout=REGEX_TIMEOUT_SECONDS)
    except TimeoutError as error:
        raise AssertionTimeout(spec.type) from error

    passed = found is not None
    return AssertionOutcome(spec.type, passed, None if passed else "the pattern did not match")


def _json_schema(spec: AssertionSpec, observation: CaseObservation) -> AssertionOutcome:
    payload = observation.payload
    if payload is None:
        return AssertionOutcome(spec.type, False, "the output is not JSON")

    try:
        jsonschema.validate(payload, spec.value)
    except ValidationError as error:
        return AssertionOutcome(spec.type, False, error.message)
    except SchemaError as error:
        raise AssertionUnevaluable(spec.type, error.message) from error

    return AssertionOutcome(spec.type, True, None)


def _required_phrase(spec: AssertionSpec, observation: CaseObservation) -> AssertionOutcome:
    phrases = spec.value if isinstance(spec.value, list) else [spec.value]
    missing = [str(phrase) for phrase in phrases if str(phrase) not in observation.text]
    return AssertionOutcome(
        spec.type, not missing, None if not missing else f"{len(missing)} required phrase(s) absent"
    )


def _forbidden_phrase(spec: AssertionSpec, observation: CaseObservation) -> AssertionOutcome:
    phrases = spec.value if isinstance(spec.value, list) else [spec.value]
    present = [str(phrase) for phrase in phrases if str(phrase) in observation.text]
    return AssertionOutcome(
        spec.type, not present, None if not present else f"{len(present)} forbidden phrase(s) present"
    )


def _max_length(spec: AssertionSpec, observation: CaseObservation) -> AssertionOutcome:
    length = len(observation.text)
    passed = length <= int(spec.value)
    return AssertionOutcome(
        spec.type, passed, None if passed else f"{length} characters exceeds {spec.value}"
    )


def _max_latency(spec: AssertionSpec, observation: CaseObservation) -> AssertionOutcome:
    if observation.latency_ms is None:
        raise AssertionUnevaluable(spec.type, "the case recorded no latency")
    passed = observation.latency_ms <= int(spec.value)
    return AssertionOutcome(
        spec.type, passed, None if passed else f"{observation.latency_ms} ms exceeds {spec.value} ms"
    )


def _max_cost(spec: AssertionSpec, observation: CaseObservation) -> AssertionOutcome:
    if observation.cost is None:
        raise AssertionUnevaluable(spec.type, "the case has no priced cost")
    limit = Decimal(str(spec.value))
    passed = observation.cost <= limit
    return AssertionOutcome(spec.type, passed, None if passed else f"cost exceeds {limit}")


def _asset_count(spec: AssertionSpec, observation: CaseObservation) -> AssertionOutcome:
    payload = observation.payload
    if isinstance(payload, list):
        count = len(payload)
    elif payload is None:
        count = 1 if returned_shape(observation.content) == "asset_reference" else 0
    else:
        count = 1
    passed = count == int(spec.value)
    return AssertionOutcome(
        spec.type, passed, None if passed else f"{count} asset(s), expected {spec.value}"
    )


def _asset_type(spec: AssertionSpec, observation: CaseObservation) -> AssertionOutcome:
    expected = str(spec.value).lower()
    payload = observation.payload
    declared: str | None = None
    if isinstance(payload, dict):
        for key in ("type", "content_type", "mime_type"):
            if isinstance(payload.get(key), str):
                declared = payload[key].lower()
                break
    if declared is None:
        declared = observation.text.strip().lower()

    passed = expected in declared
    return AssertionOutcome(
        spec.type, passed, None if passed else f"the returned asset is not {expected}"
    )


EVALUATORS = {
    AssertionType.EXACT: _exact,
    AssertionType.SUBSTRING: _substring,
    AssertionType.REGEX: _regex,
    AssertionType.JSON_SCHEMA: _json_schema,
    AssertionType.REQUIRED_PHRASE: _required_phrase,
    AssertionType.FORBIDDEN_PHRASE: _forbidden_phrase,
    AssertionType.MAX_LENGTH: _max_length,
    AssertionType.MAX_LATENCY: _max_latency,
    AssertionType.MAX_COST: _max_cost,
    AssertionType.ASSET_COUNT: _asset_count,
    AssertionType.ASSET_TYPE: _asset_type,
}


def evaluate(
    spec: AssertionSpec, observation: CaseObservation, modality: OutputModality
) -> AssertionOutcome:
    if spec.type not in ASSERTION_TYPES_BY_MODALITY[modality]:
        raise AssertionUnevaluable(
            spec.type, f"not registered for output_modality={modality.value}"
        )
    return EVALUATORS[spec.type](spec, observation)


def evaluate_all(
    specs: Sequence[AssertionSpec], observation: CaseObservation, modality: OutputModality
) -> tuple[AssertionOutcome, ...]:
    return tuple(evaluate(spec, observation, modality) for spec in specs)
