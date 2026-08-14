"""Compile a better extraction program against the golden set. Offline, never automatic.

    uv run python -m prope.prompt_search.agent.optimize --evaluate-only
    uv run python -m prope.prompt_search.agent.optimize --artifact build/extraction.json
    uv run python -m prope.prompt_search.agent.optimize --artifact build/extraction.json --publish

**This is the file where Prope's first non-negotiable could most easily be
broken, so read this before changing it.** DSPy optimizers produce two things: a
set of bootstrapped demonstrations, and — for MIPROv2 — a rewritten INSTRUCTION.
The demonstrations are a reviewable artifact and ship as a file. The instruction
is a prompt that no human has read, and Prope's product promise is that no
prompt reaches production without a recorded human approval. Prope applying that
rule to its customers' prompts while exempting its own would be the promise
broken inside the product.

So `--publish` writes the candidate instruction to Langfuse as an **unlabelled**
version. Somebody opens Langfuse, reads the diff against the live `production`
text, and moves the label by hand. `_publish_candidate` passing `labels=[]` is
the line that enforces it and
`tests/unit/test_prompt_search_dspy.py::test_optimize_never_publishes_a_labelled_prompt`
is the test that keeps it enforced.

The artifact is likewise not picked up by accident: `dspy_program` reads
`PROMPT_SEARCH_DSPY_PROGRAM`, which is unset by default and set deliberately by
an operator on a host, on a file that went through review like any other.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from prope.prompt_search.agent.evaluation import (
    evaluate,
    extraction_metric,
    load_examples,
)
from prope.prompt_search.agent.prompting import (
    EXTRACTION_PROMPT_NAME,
    FALLBACK_EXTRACTION_PROMPT,
    load_extraction_prompt,
)

#: MIPROv2 proposes instructions by inspecting the data; below roughly this many
#: examples it is proposing from noise. The golden set is deliberately small and
#: hand-written, so the default path is `BootstrapFewShot` — which only selects
#: demonstrations and never rewrites the instruction, and is therefore also the
#: path that cannot produce an unreviewed prompt at all.
MIPRO_MINIMUM_EXAMPLES = 30

#: Percentage points. A compile that moves the score by less than this is noise
#: on a twelve-row set, and shipping it would mean an artifact in the repository
#: that nobody can justify in six months.
MINIMUM_IMPROVEMENT = 1.0


def _build_baseline() -> Any:
    """The program as production runs it: the `production` instruction, no artifact."""
    from prope.prompt_search.agent.dspy_program import build_program

    prompt = load_extraction_prompt()
    if prompt.is_fallback:
        print(
            "warning: Langfuse did not resolve `production`; optimizing against "
            "the in-code fallback instruction",
            file=sys.stderr,
        )
    # `compiled_path=""` so that an artifact already deployed in this shell's
    # environment cannot quietly become the baseline it is measured against.
    return build_program(prompt.text, compiled_path="")


def _compile(program: Any, examples: list[Any], *, num_threads: int) -> Any:
    import dspy

    if len(examples) >= MIPRO_MINIMUM_EXAMPLES:
        print(f"compiling with MIPROv2 over {len(examples)} examples")
        optimizer = dspy.MIPROv2(
            metric=extraction_metric,
            auto="light",
            num_threads=num_threads,
        )
        return optimizer.compile(
            program,
            trainset=examples,
            requires_permission_to_run=False,
        )

    print(
        f"compiling with BootstrapFewShot over {len(examples)} examples "
        f"(MIPROv2 needs {MIPRO_MINIMUM_EXAMPLES}+); "
        "demonstrations only, the instruction is untouched"
    )
    optimizer = dspy.BootstrapFewShot(
        metric=extraction_metric,
        max_bootstrapped_demos=4,
        max_labeled_demos=4,
    )
    return optimizer.compile(program, trainset=examples)


def _candidate_instruction(program: Any) -> str | None:
    """The compiled program's instruction, when the optimizer rewrote it."""
    signature = getattr(getattr(program, "extract", None), "signature", None)
    return getattr(signature, "instructions", None)


def _publish_candidate(instruction: str) -> None:
    """Write the candidate to Langfuse UNLABELLED. A person moves the label.

    `labels=[]` is not a default being accepted — it is the governance decision
    of this whole file, stated as an argument so that removing it is a visible
    diff rather than an omission.
    """
    from prope.app_agent.telemetry import get_langfuse

    langfuse = get_langfuse()
    if langfuse is None:
        raise RuntimeError(
            "Langfuse is not configured: set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY"
        )

    langfuse.create_prompt(
        name=EXTRACTION_PROMPT_NAME,
        type="text",
        prompt=instruction,
        labels=[],
    )
    langfuse.flush()

    print(
        f"published an UNLABELLED version of {EXTRACTION_PROMPT_NAME}.\n"
        "It is not live. Open Langfuse, diff it against the current "
        "`production` version, and move the label by hand if you accept it."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--trainset",
        type=Path,
        default=None,
        help="JSONL golden set. Defaults to datasets/extraction_golden.jsonl.",
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        default=None,
        help="Where to write the compiled program. Omit to compile and discard.",
    )
    parser.add_argument(
        "--evaluate-only",
        action="store_true",
        help="Score the current program against the golden set and stop.",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Also write the candidate instruction to Langfuse, UNLABELLED.",
    )
    parser.add_argument("--num-threads", type=int, default=4)
    args = parser.parse_args(argv)

    examples = load_examples(args.trainset)
    if not examples:
        print("golden set is empty", file=sys.stderr)
        return 1

    baseline = _build_baseline()
    before = evaluate(baseline, examples=examples, num_threads=args.num_threads)
    print(f"baseline: {before:.2f}")

    if args.evaluate_only:
        return 0

    compiled = _compile(baseline, examples, num_threads=args.num_threads)
    after = evaluate(compiled, examples=examples, num_threads=args.num_threads)
    print(f"compiled: {after:.2f}  (delta {after - before:+.2f})")

    if after - before < MINIMUM_IMPROVEMENT:
        print(
            f"improvement below {MINIMUM_IMPROVEMENT:.1f} points — "
            "nothing written, nothing published"
        )
        return 0

    if args.artifact is not None:
        args.artifact.parent.mkdir(parents=True, exist_ok=True)
        compiled.save(str(args.artifact))
        print(f"wrote {args.artifact}")
        print(
            "It is inert until an operator sets PROMPT_SEARCH_DSPY_PROGRAM to "
            "this path. Review it like any other deployed file."
        )

    if args.publish:
        candidate = _candidate_instruction(compiled)
        if not candidate or candidate.strip() == FALLBACK_EXTRACTION_PROMPT.strip():
            print("optimizer did not propose a new instruction; nothing to publish")
        else:
            _publish_candidate(candidate)

    return 0


if __name__ == "__main__":
    # Surfaced here rather than swallowed: running the optimizer against a host's
    # deployed artifact would measure that artifact, not the baseline, and the
    # number would be quietly wrong.
    if os.getenv("PROMPT_SEARCH_DSPY_PROGRAM"):
        print(
            "note: PROMPT_SEARCH_DSPY_PROGRAM is set in this shell. "
            "The baseline ignores it on purpose.",
            file=sys.stderr,
        )
    raise SystemExit(main())
