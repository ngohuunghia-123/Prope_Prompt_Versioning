"""Offline compiler for the conversion program. Proposes; never promotes.

    uv run python -m prope.prompt_conversion.optimize --evaluate-only
    uv run python -m prope.prompt_conversion.optimize
    uv run python -m prope.prompt_conversion.optimize --publish

**This script is the reason the DSPy dependency earns its place, and it is also
the one place where Prope could most easily break its own first rule.** A DSPy
optimizer's output is a new instruction and a set of demonstrations — that is, a
new system prompt. Shipping that automatically would be an auto-release of a
prompt into production, performed by the product whose entire pitch is that
nothing reaches production without a recorded human approval.

So the split is:

    the artifact (demonstrations)   written to a file, deployed like any file,
                                    enabled only by PROMPT_CONVERSION_DSPY_PROGRAM
    the instruction                 published to Langfuse as an UNLABELLED version
                                    with --publish; a human moves `production`

`build_program()` enforces the second half at runtime by overwriting a loaded
artifact's instructions with the managed prompt, so even an operator who wires up
an artifact containing an unapproved instruction gets the approved one.

Nothing here runs in the request path, nothing here is imported by `app.py`, and
every run costs real tokens against `APP_OPENAI_API_KEY`.
"""

import argparse
import sys
from pathlib import Path

import dspy

from prope.prompt_conversion.dspy_program import (
    CanonicalConversion,
    PromptConversionProgram,
    build_lm,
)
from prope.prompt_conversion.evaluation import (
    DEFAULT_TRAINSET,
    conversion_metric,
    evaluate,
    load_examples,
    score_conversion,
)
from prope.prompt_conversion.prompting import (
    CONVERSION_PROMPT_NAME,
    load_conversion_prompt,
)
from prope.prompt_conversion.telemetry import get_langfuse

#: Below this, `MIPROv2`'s instruction proposal is fitting to noise: it spends
#: its budget on minibatches that are most of the set, and a one-example
#: difference swings a trial. `BootstrapFewShot` only collects demonstrations
#: that already score perfectly, which degrades gracefully on a small set.
MIPRO_MINIMUM_EXAMPLES = 30

#: A compiled program that scores no better than the one already in production
#: is a change with a cost and no benefit, and the cost is real: new
#: demonstrations mean more input tokens on every conversion forever.
MINIMUM_IMPROVEMENT = 1.0

DEFAULT_ARTIFACT = Path("artifacts/prompt_conversion_program.json")


def _split(examples: list[dspy.Example]) -> tuple[list[dspy.Example], list[dspy.Example]]:
    """Deterministic 2:1 train/dev split by position.

    Not shuffled, and not seeded-shuffled either. The golden set is hand-ordered
    so that its hardest cases — the injection attempt, the six-type source, the
    Vietnamese source — do not all land in one half; a shuffle would undo that
    ordering, and a seeded shuffle would hide it behind a number.
    """
    dev = [example for index, example in enumerate(examples) if index % 3 == 0]
    train = [example for index, example in enumerate(examples) if index % 3 != 0]
    return train, dev


def _report_failures(program: dspy.Module, devset: list[dspy.Example]) -> None:
    """The material's failure analysis: name the worst cases, not just the mean.

    A score is a number to put in a table; this is the part somebody acts on.
    Prints the source's shape and the deterministic reason it failed — never the
    source text, which would put golden-set content into CI logs and would put
    real content there the first time somebody points `--trainset` at a private
    file.
    """
    failures = []

    for index, example in enumerate(devset):
        try:
            prediction = program(**example.inputs())
        except Exception as error:  # a raising example is a failure, not a crash
            failures.append((index, f"raised {type(error).__name__}: {error}"))
            continue

        score = score_conversion(
            source_text=example.source_text,
            source_format=example.source_format,
            blocks=getattr(prediction, "blocks", None) or [],
            expected_block_types=tuple(example.get("expected_block_types") or ()),
        )
        if score.total < 1.0:
            failures.append((index, f"{score.total:.2f} — {score.failure}"))

    if not failures:
        print("\nfailure analysis: none — every dev example scored 1.00")
        return

    print(f"\nfailure analysis: {len(failures)} of {len(devset)} dev examples")
    for index, reason in failures:
        example = devset[index]
        print(
            f"  [{index}] format={example.source_format} "
            f"chars={len(example.source_text)} "
            f"expected={list(example.get('expected_block_types') or [])}\n"
            f"       {reason}"
        )


def _publish_candidate(instructions: str) -> None:
    """Write the candidate to Langfuse as a new version with NO label.

    `labels=[]` is the whole point of this function. `create_prompt` with
    `labels=["production"]` is one word away and would make this script an
    auto-release mechanism; `bootstrap_prompt.py` is allowed to pass it because
    it seeds an empty project, and this is not that.
    """
    langfuse = get_langfuse()

    if langfuse is None:
        raise SystemExit(
            "--publish needs LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY. "
            "The artifact was still written; only the instruction was not published."
        )

    langfuse.create_prompt(
        name=CONVERSION_PROMPT_NAME,
        type="text",
        prompt=instructions,
        labels=[],
        tags=["dspy-optimized"],
    )
    langfuse.flush()

    print(
        f"\npublished an UNLABELLED version of {CONVERSION_PROMPT_NAME}.\n"
        "It serves no traffic. Review the diff in Langfuse and move the "
        "`production` label by hand to release it."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="prope.prompt_conversion.optimize",
        description="Compile and score the prompt-conversion DSPy program.",
    )
    parser.add_argument("--trainset", type=Path, default=DEFAULT_TRAINSET)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument(
        "--evaluate-only",
        action="store_true",
        help="Score the current production program and stop. Cheap; no compile.",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Also write the compiled instruction to Langfuse as an UNLABELLED version.",
    )
    parser.add_argument("--num-threads", type=int, default=4)
    arguments = parser.parse_args(argv)

    examples = load_examples(arguments.trainset)
    train, dev = _split(examples)

    conversion_prompt = load_conversion_prompt()
    if conversion_prompt.is_fallback:
        print(
            "warning: Langfuse served no managed prompt; scoring against "
            "FALLBACK_SYSTEM_PROMPT. A compile started here optimizes a "
            "baseline that is not what production runs.",
            file=sys.stderr,
        )

    lm = build_lm()
    dspy.configure(lm=lm)

    baseline = PromptConversionProgram(
        CanonicalConversion.with_instructions(conversion_prompt.text)
    )
    baseline.set_lm(lm)

    print(
        f"golden set: {len(examples)} examples "
        f"({len(train)} train / {len(dev)} dev)\n"
        f"baseline:   {CONVERSION_PROMPT_NAME} "
        f"v{conversion_prompt.version or '-'}"
        f"{' (FALLBACK)' if conversion_prompt.is_fallback else ''}"
    )

    baseline_score = evaluate(baseline, dev, num_threads=arguments.num_threads)
    print(f"baseline score: {baseline_score:.2f}")
    _report_failures(baseline, dev)

    if arguments.evaluate_only:
        return 0

    if len(train) >= MIPRO_MINIMUM_EXAMPLES:
        print(f"\noptimizer: MIPROv2 (train={len(train)})")
        optimizer = dspy.MIPROv2(
            metric=conversion_metric,
            auto="light",
            num_threads=arguments.num_threads,
        )
        compiled = optimizer.compile(
            baseline,
            trainset=train,
            valset=dev,
            requires_permission_to_run=False,
        )
    else:
        print(
            f"\noptimizer: BootstrapFewShot (train={len(train)} < "
            f"{MIPRO_MINIMUM_EXAMPLES}; MIPROv2 would fit to noise). "
            "It proposes demonstrations only — the instruction is unchanged, so "
            "--publish has nothing new to publish."
        )
        optimizer = dspy.BootstrapFewShot(
            metric=conversion_metric,
            max_bootstrapped_demos=4,
            max_labeled_demos=4,
        )
        compiled = optimizer.compile(baseline, trainset=train)

    compiled_score = evaluate(compiled, dev, num_threads=arguments.num_threads)
    delta = compiled_score - baseline_score
    print(f"\ncompiled score: {compiled_score:.2f} ({delta:+.2f})")
    _report_failures(compiled, dev)

    if delta < MINIMUM_IMPROVEMENT:
        print(
            f"\nnot saved: {delta:+.2f} is under the {MINIMUM_IMPROVEMENT:+.2f} "
            "threshold. More demonstrations cost input tokens on every "
            "conversion forever; a tie is a loss."
        )
        return 1

    arguments.artifact.parent.mkdir(parents=True, exist_ok=True)
    compiled.save(str(arguments.artifact), save_program=False)
    print(
        f"\nwrote {arguments.artifact}\n"
        "It serves nothing until PROMPT_CONVERSION_DSPY_PROGRAM points at it. "
        "Its instructions are ignored at runtime; only its demonstrations load."
    )

    candidate = compiled.convert.signature.instructions
    if arguments.publish:
        if candidate.strip() == conversion_prompt.text.strip():
            print("\nnothing to publish: the instruction is unchanged.")
        else:
            _publish_candidate(candidate)
    elif candidate.strip() != conversion_prompt.text.strip():
        print(
            "\nthe optimizer proposed a NEW instruction and it was not published. "
            "Re-run with --publish to put it in Langfuse for review."
        )

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
