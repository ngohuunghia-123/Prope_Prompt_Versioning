"""The DSPy layer, and the governance rules that constrain it.

Nothing here touches a network. The tests that matter most are the two marked
`governance`: they assert that Prope's own agent cannot promote its own prompt,
which is the product's first non-negotiable applied to the product's insides.
"""

import ast
import sys
import tomllib
from pathlib import Path

import dspy
import pytest

from prope.prompt_conversion import optimize
from prope.prompt_conversion.domain import ConversionBlock
from prope.prompt_conversion.dspy_program import (
    CanonicalConversion,
    PromptConversionProgram,
    build_lm,
    build_program,
    cost_usd,
    normalize_blocks,
    reset_programs,
    usage_of,
)
from prope.prompt_conversion.evaluation import (
    DEFAULT_TRAINSET,
    conversion_metric,
    load_examples,
    score_conversion,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _clean_program_cache() -> None:
    reset_programs()


# --- the signature ---------------------------------------------------------


def test_the_signature_takes_the_source_and_returns_typed_blocks() -> None:
    assert list(CanonicalConversion.input_fields) == [
        "source_format",
        "source_text",
        "repair_feedback",
    ]
    assert list(CanonicalConversion.output_fields) == ["blocks"]
    assert CanonicalConversion.model_fields["blocks"].annotation == list[ConversionBlock]


def test_the_lm_never_caches_prompt_bodies_to_disk() -> None:
    """A-020, not a performance setting.

    DSPy caches completions on disk by default. Every cache entry for this
    program would be a corporate prompt body written to `~/.dspy_cache` on the
    host, outside the database, outside RLS, and outside every retention rule
    Prope has.
    """
    lm = build_lm()

    assert lm.cache is False
    assert lm.kwargs["temperature"] == 0.0
    assert lm.model.startswith("openai/")


# --- governance ------------------------------------------------------------


def test_the_managed_instruction_is_what_the_program_runs() -> None:
    program = build_program("the approved instruction")

    assert program.convert.signature.instructions == "the approved instruction"


def test_a_compiled_artifact_cannot_replace_the_approved_instruction(
    tmp_path: Path,
) -> None:
    """GOVERNANCE. The load order in `build_program` is the whole test.

    An optimizer's artifact carries both demonstrations and an instruction.
    Letting the instruction through would mean a file on disk silently
    becoming the system prompt — an auto-release of a prompt into production,
    performed by the product that sells the opposite. Demonstrations are fine:
    they change how well the agent does the job, not what the job is.
    """
    compiled = PromptConversionProgram(
        CanonicalConversion.with_instructions("AN UNAPPROVED INSTRUCTION")
    )
    compiled.convert.demos = [
        dspy.Example(
            source_format="txt",
            source_text="Be brief.",
            repair_feedback="",
            blocks=[{"type": "instructions", "content": "Be brief."}],
        ).toDict()
    ]

    artifact = tmp_path / "compiled.json"
    compiled.save(str(artifact), save_program=False)

    loaded = build_program(
        "the approved instruction", compiled_path=str(artifact)
    )

    assert loaded.convert.signature.instructions == "the approved instruction"
    assert "UNAPPROVED" not in loaded.convert.signature.instructions
    assert len(loaded.convert.demos) == 1


def test_the_optimizer_publishes_without_the_production_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GOVERNANCE. `optimize.py --publish` proposes; a human promotes.

    `labels=["production"]` is one word away from `labels=[]` and would turn
    this script into the auto-release mechanism ADR-0010 forbids.
    """
    recorded: dict[str, object] = {}

    class _FakeLangfuse:
        def create_prompt(self, **kwargs: object) -> None:
            recorded.update(kwargs)

        def flush(self) -> None:
            recorded["flushed"] = True

    monkeypatch.setattr(optimize, "get_langfuse", _FakeLangfuse)

    optimize._publish_candidate("a candidate instruction")

    assert recorded["labels"] == []
    assert recorded["prompt"] == "a candidate instruction"
    assert recorded["flushed"] is True


def test_no_source_module_publishes_a_labelled_prompt_except_the_bootstrap() -> None:
    """The rule above, enforced across `src/` rather than at one call site.

    `bootstrap_prompt.py` is the sanctioned exception: it seeds an empty
    Langfuse project with the fallback text, which is the text the code would
    have used anyway, so labelling it releases nothing new.
    """
    sanctioned = {"prompt_conversion/bootstrap_prompt.py"}
    offenders = []

    for module in (REPOSITORY_ROOT / "src" / "prope").rglob("*.py"):
        relative = module.relative_to(REPOSITORY_ROOT / "src" / "prope").as_posix()
        if relative in sanctioned:
            continue

        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            if not (
                isinstance(function, ast.Attribute)
                and function.attr == "create_prompt"
            ):
                continue
            for keyword in node.keywords:
                if keyword.arg == "labels" and ast.literal_eval(keyword.value):
                    offenders.append(f"{relative}:{node.lineno}")

    assert not offenders, (
        f"{offenders} call create_prompt with a non-empty label set. Only "
        "bootstrap_prompt.py may, and only because it seeds an empty project."
    )


# --- usage and cost --------------------------------------------------------


def test_usage_sums_across_whatever_model_name_the_provider_echoes() -> None:
    prediction = dspy.Prediction(blocks=[])
    prediction.set_lm_usage(
        {
            "gpt-4o-mini-2024-07-18": {
                "prompt_tokens": 1200,
                "completion_tokens": 300,
            }
        }
    )

    assert usage_of(prediction) == {"input": 1200, "output": 300}


def test_usage_is_empty_when_nothing_tracked_it() -> None:
    assert usage_of(dspy.Prediction(blocks=[])) == {}


def test_cost_prices_output_above_input() -> None:
    balanced = cost_usd({"input": 1_000_000, "output": 1_000_000})
    input_only = cost_usd({"input": 1_000_000, "output": 0})

    assert balanced > input_only * 2
    assert cost_usd({}) == 0.0


def test_blocks_are_accepted_as_models_or_as_dicts() -> None:
    from_model = normalize_blocks([ConversionBlock(type="system", content="x")])
    from_dict = normalize_blocks([{"type": "system", "content": "x"}])

    assert from_model == from_dict


# --- the metric ------------------------------------------------------------


def test_a_faithful_conversion_scores_one() -> None:
    score = score_conversion(
        source_text="# Role\nYou are an editor.\n\n# Task\nEdit the draft.",
        source_format="markdown",
        blocks=[
            {"type": "system", "content": "You are an editor."},
            {"type": "instructions", "content": "Edit the draft."},
        ],
        expected_block_types=("system", "instructions"),
    )

    assert score.total == pytest.approx(1.0)
    assert score.failure is None


def test_a_dropped_variable_scores_zero_and_says_why() -> None:
    score = score_conversion(
        source_text="Greet {{name}}",
        blocks=[{"type": "instructions", "content": "Greet the user"}],
    )

    assert score.total == 0.0
    assert score.structural == 0.0
    assert "{{name}}" in (score.failure or "")


def test_a_summary_loses_the_coverage_component_but_keeps_the_rest() -> None:
    score = score_conversion(
        source_text="You are an editor. " * 40,
        blocks=[{"type": "system", "content": "Editor persona."}],
        expected_block_types=("system",),
    )

    assert score.structural == 1.0
    assert score.coverage == 0.0
    assert score.typing == 1.0
    assert score.total == pytest.approx(0.8)


def test_a_misclassified_block_costs_the_typing_component() -> None:
    score = score_conversion(
        source_text="Edit the draft.",
        blocks=[{"type": "system", "content": "Edit the draft."}],
        expected_block_types=("instructions",),
    )

    assert score.typing == 0.0
    assert score.total < 1.0


def test_the_metric_is_a_strict_boolean_while_bootstrapping() -> None:
    """DSPy's convention: with a trace, only a perfect run may become a demo.

    A demonstration that models a 0.8 conversion teaches the model to produce
    0.8 conversions.
    """
    example = dspy.Example(
        source_text="Edit the draft.",
        expected_block_types=("instructions",),
    )
    perfect = dspy.Prediction(
        blocks=[{"type": "instructions", "content": "Edit the draft."}]
    )
    imperfect = dspy.Prediction(
        blocks=[{"type": "system", "content": "Edit the draft."}]
    )

    assert conversion_metric(example, perfect, trace=[]) is True
    assert conversion_metric(example, imperfect, trace=[]) is False
    assert 0.0 < conversion_metric(example, imperfect) < 1.0


# --- the golden set --------------------------------------------------------


def test_the_shipped_golden_set_loads_and_every_record_is_a_valid_source() -> None:
    examples = load_examples()

    assert len(examples) >= 10
    assert {example.source_format for example in examples} == {
        "txt",
        "markdown",
        "json",
        "yaml",
    }
    for example in examples:
        assert set(example.inputs().keys()) == {
            "source_format",
            "source_text",
            "repair_feedback",
        }


def test_every_expected_block_type_in_the_golden_set_is_a_real_block_type() -> None:
    """A typo in the golden set would silently cap the metric below 1.0 forever."""
    legal = set(ConversionBlock.model_fields["type"].annotation.__args__)

    for example in load_examples():
        assert set(example.expected_block_types) <= legal


def test_the_golden_set_holds_no_real_corporate_prompt_by_declaration() -> None:
    """A-020 is a policy, so this test can only check the marker, not the content.

    What it does check is that the file has not silently grown a pipeline of
    scraped sources: every record is a hand-written object with a `note` saying
    why it is in the set, and a bulk import would not have one.
    """
    import json

    for number, line in enumerate(
        DEFAULT_TRAINSET.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        record = json.loads(line)
        assert record.get("note"), (
            f"{DEFAULT_TRAINSET}:{number} has no `note`. Every golden example is "
            "hand-written for a stated reason; A-020 forbids adding real ones."
        )


# --- the dependency that was missing --------------------------------------


def test_every_module_scope_third_party_import_is_a_declared_dependency() -> None:
    """The bug this whole change started from.

    `prompt_conversion.telemetry` imported `langfuse` at module scope while
    `pyproject.toml` declared no such dependency, and `app.py` imports the
    conversion router — so a clean `uv sync` produced an application that could
    not import itself. It only ever ran because the package had been installed
    into `.venv` by hand.
    """
    manifest = tomllib.loads(
        (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    declared = {
        requirement.split("==")[0].split("[")[0].strip().lower().replace("-", "_")
        for requirement in manifest["project"]["dependencies"]
    }

    # `pyyaml` installs as `yaml`; the distribution name and the import name
    # differ for exactly this one runtime dependency.
    declared.add("yaml")

    for module in (REPOSITORY_ROOT / "src" / "prope" / "prompt_conversion").rglob(
        "*.py"
    ):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            roots: list[str] = []
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots = [node.module.split(".")[0]]

            for root in roots:
                # `sys.stdlib_module_names` rather than a hand-listed set: the
                # hand-listed one silently grows a hole every time this module
                # imports something new from the standard library, and the hole
                # looks like a passing test.
                if root == "prope" or root in sys.stdlib_module_names:
                    continue
                assert root.lower() in declared, (
                    f"{module.name} imports {root!r}, which pyproject.toml does "
                    "not declare. A clean `uv sync` would not be able to import "
                    "the application."
                )

