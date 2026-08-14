"""Offline evaluation for the conversion program. The metric `optimize.py` compiles against.

**Every check here is deterministic, and that is a choice with a cost.** The
obvious design is an LLM-as-judge scoring "did the conversion preserve meaning",
and it is refused for three reasons in descending order of weight: it would send
a second copy of a corporate prompt body to a model (A-020, and the same reason
`service.py` sends no bodies to Langfuse); it would drift under the judge model
without anyone noticing, so a score that fell could mean the converter got worse
OR the judge changed; and it costs money per evaluation run, which is what makes
people stop running evaluations.

What is given up is real: nothing below can tell a faithful conversion from one
that classified an instruction as a constraint. `expected_block_types` on a
golden example is the hand-written substitute, and it only covers the examples
somebody wrote. The honest summary is that this metric proves the converter did
not BREAK anything, and only samples whether it did the right thing.

The four checks and what each one is for:

    structural   AgentOutput + serialize_agent_output accept it.  Hard gate.
    variables    every {{placeholder}} survives, exactly.          In `structural`.
    coverage     classified characters over source characters.     Catches summarizing.
    typing       block types match the golden example's.           Catches misclassifying.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import dspy
from pydantic import ValidationError

from prope.prompt_conversion.domain import (
    AgentOutput,
    InvalidAgentOutputError,
    content_coverage,
    normalize_source,
    serialize_agent_output,
)
from prope.prompt_conversion.dspy_program import normalize_blocks

#: The golden set ships with the module rather than living in a notebook,
#: because an evaluation nobody can run from a checkout is an evaluation that
#: gets run once.
DEFAULT_TRAINSET = Path(__file__).parent / "datasets" / "conversion_golden.jsonl"

#: A faithful conversion strips format syntax — Markdown hashes, YAML keys — and
#: nothing else, so it lands just under 1.0. Below the floor is summarizing;
#: above the ceiling is duplicating content across blocks. Both are failures of
#: the same instruction ("do not improve, rewrite, summarize"), which is why one
#: band scores both.
COVERAGE_FLOOR = 0.80
COVERAGE_CEILING = 1.10


@dataclass(frozen=True, slots=True)
class ConversionScore:
    """A scored attempt. `total` is what the optimizer maximizes."""

    structural: float
    coverage: float
    typing: float
    total: float
    failure: str | None = None


def _typing_score(
    produced: list[str],
    expected: tuple[str, ...],
) -> float:
    """Jaccard over block types, or a free pass when the example declares none.

    Jaccard rather than exact-set-equality because the two ways of being wrong
    are not equally wrong: splitting `instructions` into `instructions` +
    `constraints` is a defensible reading of an ambiguous source and should cost
    a fraction, while returning `system` where the source was all procedure
    should cost nearly everything. An exact match would score those the same.
    """
    if not expected:
        return 1.0

    produced_set = set(produced)
    expected_set = set(expected)
    union = produced_set | expected_set

    return len(produced_set & expected_set) / len(union) if union else 1.0


def score_conversion(
    *,
    source_text: str,
    blocks: list[Any],
    source_format: str = "txt",
    expected_block_types: tuple[str, ...] = (),
) -> ConversionScore:
    """Score one conversion. Pure, no model, no I/O.

    Weighted 0.5 / 0.2 / 0.3. Structural carries half because it is the only
    check that maps to a user-visible failure — a conversion that fails it
    returns 502 and the author gets nothing. Typing carries more than coverage
    because a misclassified block is wrong in a way a human has to notice,
    whereas a coverage dip is visible in the diff the author reviews before
    saving.
    """
    try:
        output = AgentOutput(blocks=normalize_blocks(blocks))
    except (ValidationError, TypeError) as error:
        return ConversionScore(0.0, 0.0, 0.0, 0.0, failure=f"shape: {error}")

    try:
        serialize_agent_output(output, source_text=source_text)
    except InvalidAgentOutputError as error:
        return ConversionScore(0.0, 0.0, 0.0, 0.0, failure=str(error))

    ratio = content_coverage(
        output, source_text=source_text, source_format=source_format
    )
    coverage = 1.0 if COVERAGE_FLOOR <= ratio <= COVERAGE_CEILING else 0.0
    typing = _typing_score([block.type for block in output.blocks], expected_block_types)

    failure = None
    if not coverage:
        failure = f"coverage {ratio:.2f} outside [{COVERAGE_FLOOR}, {COVERAGE_CEILING}]"
    elif typing < 1.0:
        failure = f"block types {sorted(b.type for b in output.blocks)} != {sorted(expected_block_types)}"

    return ConversionScore(
        structural=1.0,
        coverage=coverage,
        typing=typing,
        total=0.5 + 0.2 * coverage + 0.3 * typing,
        failure=failure,
    )


def conversion_metric(
    example: dspy.Example,
    prediction: Any,
    trace: Any = None,
) -> float:
    """The `dspy.Evaluate` / optimizer metric.

    Returns a bool when `trace` is set, which is DSPy's convention for
    bootstrapping: during demo collection only a PERFECT trace may become a
    few-shot example, because a demonstration that models a 0.7 conversion
    teaches the model to produce 0.7 conversions.
    """
    score = score_conversion(
        source_text=example.source_text,
        source_format=example.get("source_format") or "txt",
        blocks=getattr(prediction, "blocks", None) or [],
        expected_block_types=tuple(example.get("expected_block_types") or ()),
    )

    if trace is not None:
        return score.total >= 1.0

    return score.total


def load_examples(path: Path | str = DEFAULT_TRAINSET) -> list[dspy.Example]:
    """Read the golden set. Every record is validated the way a request would be.

    `normalize_source` runs here so that a malformed golden example fails at
    load with a filename and a line, rather than at compile time as an opaque
    zero from one of forty trials.
    """
    examples: list[dspy.Example] = []
    source_path = Path(path)

    for number, line in enumerate(
        source_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue

        try:
            record = json.loads(line)
            normalized = normalize_source(
                record["source_text"], record["source_format"]
            )
        except Exception as error:
            raise ValueError(f"{source_path}:{number}: {error}") from error

        examples.append(
            dspy.Example(
                source_format=normalized.format,
                source_text=normalized.text,
                repair_feedback="",
                expected_block_types=tuple(record.get("expected_block_types") or ()),
            ).with_inputs("source_format", "source_text", "repair_feedback")
        )

    if not examples:
        raise ValueError(f"{source_path} contains no examples")

    return examples


def evaluate(
    program: dspy.Module,
    devset: list[dspy.Example],
    *,
    num_threads: int = 4,
) -> float:
    """Mean metric over `devset`, as a percentage. Thin wrapper; kept for one reason.

    `failure_score=0.0` rather than the exception default: an example that makes
    the program raise is a zero, not a crashed evaluation run. A benchmark that
    aborts on its hardest case reports the average of the easy ones.
    """
    evaluator = dspy.Evaluate(
        devset=devset,
        metric=conversion_metric,
        num_threads=num_threads,
        display_progress=True,
        failure_score=0.0,
        provide_traceback=False,
    )
    result = evaluator(program)

    return float(getattr(result, "score", result))


__all__ = [
    "COVERAGE_CEILING",
    "COVERAGE_FLOOR",
    "DEFAULT_TRAINSET",
    "ConversionScore",
    "conversion_metric",
    "evaluate",
    "load_examples",
    "score_conversion",
]
