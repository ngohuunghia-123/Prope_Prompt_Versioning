"""The governance, safety and quality properties of prompt-search's extraction agent.

These tests are about the promises the module makes, not about whether a model
answers well. The three that would be worth reverting a release over:

* a compiled artifact must never replace the human-approved instruction
* nothing but `bootstrap_prompt.py` may label a Langfuse prompt `production`
* no prompt body, and nothing derived from one, may reach a log line or a span

Nothing here calls a model. `_FakeProgram` stands in for the DSPy program and
`_FakeAgent` for the whole `dspy_program` module, so the suite runs in
milliseconds and never spends the app's key.
"""

import ast
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from prope.observability import LOGGABLE_FIELDS
from prope.prompt_search.agent import evaluation, extraction, prompting
from prope.prompt_search.domain import ExtractedMetadata, ExtractedVariations

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "prope" / "prompt_search"
AGENT_ROOT = SOURCE_ROOT / "agent"


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


def _metadata(**overrides: Any) -> ExtractedMetadata:
    base = {
        "keywords": ("refund", "customer", "triage", "support", "policy"),
        "topics": ("customer support", "operations"),
        "entities": (),
        "variations": ExtractedVariations(
            en=("handle refunds", "process a refund request"),
            vi=("xu ly hoan tien", "yeu cau hoan tien"),
        ),
        "language": ("en",),
    }
    base.update(overrides)
    return ExtractedMetadata(**base)  # type: ignore[arg-type]


class _FakeProgram:
    """Stands in for the compiled DSPy program."""

    def __init__(self, result: Any = None, error: Exception | None = None) -> None:
        self.result = result if result is not None else SimpleNamespace()
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def acall(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


class _NullContext:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *exc: Any) -> bool:
        return False


class _FakeAgent:
    """Stands in for `dspy_program`, so no test ever imports DSPy."""

    MAX_OUTPUT_TOKENS = 2000

    def __init__(self, metadata: ExtractedMetadata, *, char_limit: int = 4000) -> None:
        self.metadata = metadata
        self.char_limit = char_limit

    def truncate_body(self, body: str) -> tuple[str, bool]:
        if len(body) <= self.char_limit:
            return body, False
        return body[: self.char_limit], True

    def usage_tracking(self) -> _NullContext:
        return _NullContext()

    def usage_of(self, _prediction: Any) -> dict[str, int]:
        return {"input": 1000, "output": 200}

    def cost_usd(self, usage: dict[str, int]) -> float:
        return usage["input"] / 1_000_000 * 0.15 + usage["output"] / 1_000_000 * 0.60

    def metadata_of(self, _prediction: Any) -> ExtractedMetadata:
        return self.metadata


@pytest.fixture(autouse=True)
def _isolated_breaker(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fresh circuit breaker per test.

    `agent.base` owns one at module scope, so without this a test that drives a
    failure leaves the breaker half-tripped for whatever runs next — and the
    resulting cross-test coupling is order-dependent and miserable to find.
    """
    from prope.app_agent.circuit import CircuitBreaker

    breaker = CircuitBreaker(on_state_change=lambda _open: None)
    monkeypatch.setattr("prope.prompt_search.agent.base._breaker", breaker)
    monkeypatch.setattr(
        extraction, "call_app_service", lambda operation: breaker.call(operation)
    )


@pytest.fixture(autouse=True)
def _local_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never reach for Langfuse. Every test runs on the in-code fallback."""
    monkeypatch.setattr(
        extraction,
        "load_extraction_prompt",
        lambda: prompting.ExtractionPrompt(
            text=prompting.FALLBACK_EXTRACTION_PROMPT,
            managed_prompt=None,
            version=None,
            is_fallback=True,
        ),
    )


def _install(
    monkeypatch: pytest.MonkeyPatch,
    *,
    metadata: ExtractedMetadata | None = None,
    program: _FakeProgram | None = None,
    char_limit: int = 4000,
) -> _FakeProgram:
    agent = _FakeAgent(metadata if metadata is not None else _metadata(), char_limit=char_limit)
    fake_program = program if program is not None else _FakeProgram()
    monkeypatch.setattr(extraction, "_agent", agent)
    monkeypatch.setattr(extraction, "build_program", lambda _instructions: fake_program)
    return fake_program


# ---------------------------------------------------------------------------
# Governance — the reasons this module is allowed to exist at all
# ---------------------------------------------------------------------------


def test_only_bootstrap_may_label_a_langfuse_prompt() -> None:
    """`labels=` non-empty is a RELEASE. Exactly one file in this module may do it.

    Prope's first non-negotiable is that no prompt reaches production without a
    recorded human approval. An agent that could label its own proposed
    instruction `production` would be that promise broken inside the product.
    `bootstrap_prompt.py` is exempt because the text it labels is the fallback —
    the text the module runs with no Langfuse at all — so labelling it releases
    nothing that was not already live.
    """
    offenders: list[str] = []

    for path in AGENT_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if getattr(node.func, "attr", None) != "create_prompt":
                continue
            for keyword in node.keywords:
                if keyword.arg != "labels":
                    continue
                empty = isinstance(keyword.value, ast.List) and not keyword.value.elts
                if not empty and path.name != "bootstrap_prompt.py":
                    offenders.append(f"{path.name}:{node.lineno}")

    assert offenders == []


def test_optimize_publishes_unlabelled() -> None:
    """The one call in `optimize.py` passes `labels=[]` literally, not by default."""
    tree = ast.parse((AGENT_ROOT / "optimize.py").read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "create_prompt"
    ]

    assert len(calls) == 1
    labels = {keyword.arg: keyword.value for keyword in calls[0].keywords}["labels"]
    assert isinstance(labels, ast.List)
    assert labels.elts == []


def test_build_program_applies_the_artifact_before_the_instruction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Load order is the governance decision. Reversed, a file overrides a human.

    A compiled artifact carries both demonstrations and the instruction it was
    compiled with. `load()` first and `with_instructions()` second means the
    demonstrations survive and the approved instruction always wins.
    """
    from prope.prompt_search.agent import dspy_program

    dspy_program.reset_programs()
    order: list[str] = []

    class _Recorder:
        instructions = "from the artifact"

        def with_instructions(self, text: str) -> Any:
            order.append(f"instructions:{text}")
            return self

    class _Program:
        def __init__(self) -> None:
            self.extract = SimpleNamespace(signature=_Recorder())

        def load(self, path: str) -> None:
            order.append(f"load:{path}")

        def set_lm(self, _lm: Any) -> None:
            order.append("set_lm")

    monkeypatch.setattr(dspy_program, "MetadataExtractionProgram", lambda _sig: _Program())
    monkeypatch.setattr(dspy_program, "build_lm", lambda: object())

    dspy_program.build_program("the approved instruction", compiled_path="artifact.json")

    assert order[0] == "load:artifact.json"
    assert order[1] == "instructions:the approved instruction"
    dspy_program.reset_programs()


def test_the_shared_lm_never_caches_to_disk() -> None:
    """`cache=False` is a SECURITY setting, asserted rather than trusted.

    DSPy's default on-disk cache would write every rendered prompt — untrusted
    corporate prompt bodies under A-020 — into `~/.dspy_cache` on the host.
    """
    from prope.app_agent import dspy_runtime

    captured: dict[str, Any] = {}

    class _LM:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    original = dspy_runtime.dspy.LM
    dspy_runtime.dspy.LM = _LM  # type: ignore[misc]
    try:
        dspy_runtime.build_lm(max_tokens=2000)
    finally:
        dspy_runtime.dspy.LM = original  # type: ignore[misc]

    assert captured["cache"] is False
    assert captured["temperature"] == 0.0
    assert captured["max_tokens"] == 2000


def test_importing_the_search_api_does_not_pull_dspy_in() -> None:
    """Eleven seconds of import must stay off every process start.

    `api.py` imports the extraction module and `app.py` mounts that router, so
    anything that reaches `import dspy` from here lands on `worker`'s startup
    too — a process that also runs provider-access's batch dispatch and has
    nothing to do with extraction.

    **This runs in a subprocess and checks `sys.modules`, deliberately.** The
    first version of this test parsed `extraction.py` for a literal
    `import dspy` and passed while the chain
    `extraction -> evaluation -> dspy_program -> dspy` was live: the offending
    import was two modules away and the AST of one file cannot see it. The caps
    that chain existed for now live in `domain.py`.
    """
    import subprocess

    probe = (
        "import sys; import prope.prompt_search.api; "
        "print('dspy' in sys.modules)"
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "False", (
        "importing prompt_search.api pulled DSPy in; some module in its import "
        "graph reaches dspy_program at module scope"
    )


def test_no_span_is_given_the_model_input_or_output() -> None:
    """`generation.update(input=..., output=...)` would ship prompt bodies to Langfuse.

    Prope records usage, cost, metadata and scores by hand precisely so that the
    text never leaves. OpenInference's DSPy auto-instrumentation is not installed
    for the same reason; this catches the hand-written equivalent.
    """
    for path in AGENT_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if getattr(node.func, "attr", None) != "update":
                continue
            passed = {keyword.arg for keyword in node.keywords}
            assert not (passed & {"input", "output"}), f"{path.name}:{node.lineno}"


# ---------------------------------------------------------------------------
# The deterministic layer: what the model proposes, code disposes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "raw", "expected"),
    [
        ("keywords", ["Refund", "refund", "REFUND"], ("refund",)),
        ("keywords", ["  spaced   out  "], ("spaced out",)),
        ("keywords", ["ok", 42, None, "fine"], ("ok", "fine")),
        ("topics", ["Support"], ("support",)),
        ("entities", ["PostgreSQL", "postgresql"], ("PostgreSQL",)),
    ],
)
def test_terms_are_cleaned_before_they_reach_a_row(
    field: str, raw: list[Any], expected: tuple[str, ...]
) -> None:
    from prope.prompt_search.agent.dspy_program import metadata_of

    result = metadata_of(SimpleNamespace(**{field: raw}))
    assert getattr(result, field) == expected


def test_a_hostile_body_cannot_make_the_index_row_unbounded() -> None:
    """The instruction ASKS for 5-15 keywords; the caps are what enforce it."""
    from prope.prompt_search.agent.dspy_program import MAX_KEYWORDS, metadata_of

    result = metadata_of(SimpleNamespace(keywords=[f"term{n}" for n in range(500)]))
    assert len(result.keywords) == MAX_KEYWORDS


def test_a_copied_sentence_is_not_a_keyword() -> None:
    from prope.prompt_search.agent.dspy_program import metadata_of

    sentence = "you are a helpful assistant that always answers in complete sentences and never refuses"
    result = metadata_of(SimpleNamespace(keywords=[sentence, "assistant"]))
    assert result.keywords == ("assistant",)


def test_language_is_constrained_to_the_two_codes_the_column_admits() -> None:
    from prope.prompt_search.agent.dspy_program import metadata_of

    result = metadata_of(SimpleNamespace(language=["VI", "fr", "en", "klingon"]))
    # Sorted en-before-vi so two bilingual prompts store the same array.
    assert result.language == ("en", "vi")


def test_truncation_is_reported_rather_than_silent() -> None:
    from prope.prompt_search.agent import dspy_program

    short, cut = dspy_program.truncate_body("a" * 10)
    assert (short, cut) == ("a" * 10, False)

    long, cut = dspy_program.truncate_body("a" * (dspy_program.BODY_CHARACTER_LIMIT + 1))
    assert cut is True
    assert len(long) == dspy_program.BODY_CHARACTER_LIMIT


# ---------------------------------------------------------------------------
# The quality metric
# ---------------------------------------------------------------------------


def test_diacritics_fold_so_vietnamese_terms_ground() -> None:
    assert evaluation.fold("Kiểm Tra") == evaluation.fold("kiem tra")
    assert evaluation.fold("Đơn hàng") == "don hang"


def test_a_grounded_extraction_outscores_an_invented_one() -> None:
    source = {
        "title": "Refund triage",
        "purpose": "Sort refund requests",
        "body": "Decide whether a customer refund request is approved or escalated.",
    }
    grounded = evaluation.score_extraction(_metadata(), **source)
    invented = evaluation.score_extraction(
        _metadata(keywords=("blockchain", "kubernetes", "mortgage", "opera", "welding")),
        **source,
    )

    assert grounded.groundedness > invented.groundedness
    assert grounded.total > invented.total


def test_variations_and_topics_are_not_required_to_appear_in_the_source() -> None:
    """A paraphrase for a searcher whose words differ is the point of those fields.

    Every KEYWORD below occurs in the source and every VARIATION and TOPIC does
    not, so a groundedness of exactly 1.0 is the assertion that only keywords and
    entities are graded for it.
    """
    score = evaluation.score_extraction(
        _metadata(
            keywords=("refund", "customer", "triage", "request", "escalated"),
            topics=("service operations", "back office"),
            variations=ExtractedVariations(
                en=("get money back", "undo a purchase"),
                vi=("hoan tra tien", "huy giao dich"),
            ),
        ),
        title="Refund triage",
        purpose="Sort refund requests",
        body="Decide whether a customer refund request is approved or escalated.",
    )
    assert score.groundedness == pytest.approx(1.0)


def test_an_empty_extraction_scores_zero_groundedness() -> None:
    score = evaluation.score_extraction(
        evaluation.empty_metadata(), title="t", purpose="p", body="b"
    )
    assert score.groundedness == 0.0
    assert not score.passed


def test_a_topic_that_merely_repeats_a_keyword_costs_hygiene() -> None:
    clean = evaluation.score_extraction(_metadata(), title="", purpose="", body="")
    overlapping = evaluation.score_extraction(
        _metadata(topics=("refund", "operations")), title="", purpose="", body=""
    )
    assert overlapping.hygiene < clean.hygiene


def test_the_optimizer_metric_returns_a_bool_when_dspy_is_choosing_demonstrations() -> None:
    """`trace` set means DSPy is deciding whether to KEEP a bootstrapped demo."""
    example = SimpleNamespace(
        title="Refund triage",
        purpose="Sort refund requests",
        body="Decide whether a customer refund request is approved or escalated.",
        expected={"expected_keywords": ["refund"]},
    )
    prediction = SimpleNamespace(
        keywords=["refund", "customer", "triage", "support", "policy"],
        topics=["customer support", "operations"],
        entities=[],
        variations_en=["handle refunds", "process a refund"],
        variations_vi=["xu ly hoan tien", "yeu cau hoan tien"],
        language=["en"],
    )

    assert isinstance(evaluation.extraction_metric(example, prediction), float)
    assert isinstance(evaluation.extraction_metric(example, prediction, trace=object()), bool)


def test_expected_keywords_are_scored_for_recall_not_precision() -> None:
    """Finding extra good terms must not be punished."""
    example = SimpleNamespace(
        title="", purpose="", body="", expected={"expected_keywords": ["refund"]}
    )
    exact = SimpleNamespace(keywords=["refund"])
    generous = SimpleNamespace(keywords=["refund", "customer", "triage"])

    assert evaluation._expected_recall(  # noqa: SLF001
        example.expected, _metadata(keywords=tuple(exact.keywords))
    ) == 1.0
    assert evaluation._expected_recall(  # noqa: SLF001
        example.expected, _metadata(keywords=tuple(generous.keywords))
    ) == 1.0


# ---------------------------------------------------------------------------
# The golden set
# ---------------------------------------------------------------------------


def _golden_records() -> list[dict]:
    path = evaluation.golden_path()
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_every_golden_record_explains_why_it_exists() -> None:
    """A-020: no real corporate prompts in the pilot.

    A `note` is the cheapest available proxy — a prompt pasted in from a real
    workspace does not arrive with an explanation of which behaviour it pins
    down. See `datasets/README.md`.
    """
    records = _golden_records()
    assert len(records) >= 10

    for record in records:
        assert record.get("note", "").strip(), record.get("title")
        assert {"title", "purpose", "body"} <= record.keys()


def test_the_golden_set_covers_both_languages_and_prompt_injection() -> None:
    joined = " ".join(record["body"] for record in _golden_records()).lower()
    assert "ignore all previous instructions" in joined
    assert "kiểm tra" in joined


def test_no_golden_record_names_a_resolvable_host() -> None:
    """RFC 2606 `.invalid`, so nothing in the file can be fetched or mailed."""
    for record in _golden_records():
        for token in record["body"].split():
            if "@" in token or token.startswith("http"):
                assert ".invalid" in token, token


# ---------------------------------------------------------------------------
# The live path
# ---------------------------------------------------------------------------


async def test_a_successful_extraction_records_cost_quality_and_a_log_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from prope.prompt_search import observability

    program = _install(monkeypatch)
    before = observability.extraction_cost_usd_total._value.get()  # noqa: SLF001

    result = await extraction.extract_metadata(
        "Decide whether a customer refund request is approved.",
        "Sort refund requests",
        "Refund triage",
        context=extraction.ExtractionContext(
            workspace_id="wsp_1", actor_id="usr_1", prompt_id="prm_1", job_id="psj_1"
        ),
    )

    assert result.keywords
    assert observability.extraction_cost_usd_total._value.get() > before  # noqa: SLF001
    # The body reached the program; nothing else did.
    assert program.calls[0]["body"].startswith("Decide whether")


async def test_an_extraction_with_no_keywords_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A row with no keywords makes a prompt look indexed while being unfindable."""
    _install(monkeypatch, metadata=evaluation.empty_metadata())

    with pytest.raises(extraction.ExtractionFailedError):
        await extraction.extract_metadata("body", "purpose", "title")


async def test_an_upstream_failure_surfaces_as_the_modules_own_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`worker.run_indexing_job` maps this onto `reason=agent_error`."""
    _install(monkeypatch, program=_FakeProgram(error=RuntimeError("upstream 500")))

    with pytest.raises(extraction.ExtractionFailedError):
        await extraction.extract_metadata("body", "purpose", "title")


async def test_a_long_body_is_truncated_and_counted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from prope.prompt_search import observability

    program = _install(monkeypatch, char_limit=50)
    before = observability.extraction_body_truncated_total._value.get()  # noqa: SLF001

    await extraction.extract_metadata("x" * 500, "purpose", "title")

    assert len(program.calls[0]["body"]) == 50
    assert observability.extraction_body_truncated_total._value.get() == before + 1  # noqa: SLF001


async def test_running_on_the_fallback_instruction_is_counted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Otherwise "the managed prompt stopped loading" looks like "all is well"."""
    from prope.prompt_search import observability

    _install(monkeypatch)
    before = observability.extraction_prompt_fallback_total._value.get()  # noqa: SLF001

    await extraction.extract_metadata("body", "purpose", "title")

    assert observability.extraction_prompt_fallback_total._value.get() == before + 1  # noqa: SLF001


async def test_the_preview_and_index_paths_are_traced_separately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same work, different latency budget and traffic shape. One dashboard each."""
    names: list[str] = []

    def _record(*, body: str, purpose: str, title: str, context: Any, operation: str) -> Any:
        names.append(operation)
        raise extraction.ExtractionFailedError("stop here")

    monkeypatch.setattr(extraction, "_extract", _record)

    for call in (extraction.extract_metadata, extraction.preview_extraction):
        with pytest.raises(extraction.ExtractionFailedError):
            await call("body", "purpose", "title")

    assert names == ["index-extraction", "preview-extraction"]


async def test_every_field_this_module_logs_is_on_the_allow_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A-046, checked against the real allow-list rather than a copy of it."""
    captured: dict[str, Any] = {}

    class _Log:
        def info(self, event: str, **fields: Any) -> None:
            captured.update({"event": event, **fields})

    _install(monkeypatch)
    monkeypatch.setattr(extraction, "log", _Log())

    await extraction.extract_metadata(
        "body",
        "purpose",
        "title",
        context=extraction.ExtractionContext(workspace_id="wsp_1", actor_id="usr_1"),
    )

    assert captured
    assert set(captured) <= LOGGABLE_FIELDS, set(captured) - LOGGABLE_FIELDS


async def test_no_logged_value_carries_any_of_the_three_text_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The lock file: extracted metadata may carry sensitive terms out of the body."""
    captured: dict[str, Any] = {}

    class _Log:
        def info(self, event: str, **fields: Any) -> None:
            captured.update(fields)

    secret_body = "SENSITIVE-BODY-MARKER internal pricing rules"
    _install(monkeypatch, metadata=_metadata(keywords=("SECRET-KEYWORD-MARKER", "refund")))
    monkeypatch.setattr(extraction, "log", _Log())

    await extraction.extract_metadata(secret_body, "SENSITIVE-PURPOSE-MARKER", "title")

    rendered = json.dumps(captured, default=str)
    assert "SENSITIVE-BODY-MARKER" not in rendered
    assert "SENSITIVE-PURPOSE-MARKER" not in rendered
    assert "SECRET-KEYWORD-MARKER" not in rendered


# ---------------------------------------------------------------------------
# The bug that started all of this
# ---------------------------------------------------------------------------


def test_every_module_scope_third_party_import_is_a_declared_dependency() -> None:
    """`langfuse` was imported at module scope and declared nowhere.

    It only worked because somebody had installed it into `.venv` by hand; a
    clean `uv sync` produced an application that could not import itself. This
    walks every module-scope import in `prompt_search` and checks the
    distribution behind it is actually declared.
    """
    import tomllib

    project = tomllib.loads(
        (Path(__file__).resolve().parents[2] / "pyproject.toml").read_text(encoding="utf-8")
    )
    declared = {
        requirement.split("[")[0].split("=")[0].split(">")[0].split("<")[0].strip().lower()
        for requirement in project["project"]["dependencies"]
    }
    # Import name differs from distribution name for these.
    aliases = {
        "yaml": "pyyaml",
        "sqlalchemy": "sqlalchemy",
        "aio_pika": "aio-pika",
        "ulid": "python-ulid",
        "prometheus_client": "prometheus-client",
        "dotenv": "python-dotenv",
        "jose": "python-jose",
    }
    local = {"prope"}

    for path in SOURCE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [(node.module or "").split(".")[0]]

            for name in names:
                if not name or name in sys.stdlib_module_names or name in local:
                    continue
                distribution = aliases.get(name, name).replace("_", "-")
                assert distribution in declared, (
                    f"{path.name} imports `{name}` at module scope, "
                    f"but `{distribution}` is not in pyproject dependencies"
                )
