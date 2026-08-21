"""The golden dataset: 42 labelled queries over the evaluation corpus.

36 hand-written queries plus the 6 duplicate probes below. It said 46 for as
long as it has existed, which is the sort of number nobody rechecks.

Built to `docs/materials/7-ai-evaluation-benchmarking.pdf` p20-22 — stratified
difficulty, explicit edge cases, adversarial inputs, and a label written by
reading the target prompt rather than by trusting its filename.

**Relevance is graded, not binary.** ``primary`` is what a person asking this
question wanted; ``secondary`` is what they would accept as a reasonable
neighbour. Binary labels over a corpus this uniform would score a plausible
answer as a miss and make every measurement noise: three memory-architecture
prompts genuinely answer "an agent that remembers between sessions", and a
ranker that returns all three is not wrong.

**Adversarial cases expect nothing.** They exist because cosine distance always
answers (`repository.MIN_SEARCH_SIMILARITY`): a corpus of 120 prompts will
always contain a least-unrelated one, and an import dialog presents whatever it
is handed as a near-duplicate. Abstention is a measured property here, not a
hoped-for one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Difficulty = Literal["easy", "medium", "hard", "adversarial"]

#: Graded gains for nDCG. A near-neighbour is worth having; it is not the answer.
GAIN_PRIMARY = 3.0
GAIN_SECONDARY = 1.0


@dataclass(frozen=True, slots=True)
class GoldenQuery:
    id: str
    query: str
    difficulty: Difficulty
    category: str
    primary: tuple[str, ...] = ()
    """Corpus **file stems**, not database names — the identifier a reviewer can
    verify by opening ``playgrounds/prompts/<stem>.txt``."""

    secondary: tuple[str, ...] = ()
    note: str = ""
    #: `similar` sends the text to POST /prompts/search/similar, `search` to the
    #: AI search route. Same ranking underneath; different length regime.
    route: Literal["search", "similar"] = "search"
    probe_source: str | None = field(default=None)
    """Set on generated duplicate probes: the corpus file the text was cut from."""

    @property
    def relevant(self) -> frozenset[str]:
        return frozenset(self.primary) | frozenset(self.secondary)

    def gain(self, name: str) -> float:
        if name in self.primary:
            return GAIN_PRIMARY
        if name in self.secondary:
            return GAIN_SECONDARY
        return 0.0


# --------------------------------------------------------------------------
# Easy — factual lookup, one obvious target (deck p21: 5 per 20)
# --------------------------------------------------------------------------
EASY: tuple[GoldenQuery, ...] = (
    GoldenQuery(
        id="e01",
        query="kubernetes cluster hardening and workload orchestration",
        difficulty="easy",
        category="devops",
        primary=("kubernetes_specialist",),
        secondary=("platform_engineer_iac", "terraform_iac_specialist", "sre"),
    ),
    GoldenQuery(
        id="e02",
        query="solidity smart contract gas optimisation and audit",
        difficulty="easy",
        category="blockchain",
        primary=("solidity_smart_contract_engineer",),
        secondary=("solana_blockchain_architect",),
    ),
    GoldenQuery(
        id="e03",
        query="WCAG accessibility audit with screen reader testing",
        difficulty="easy",
        category="frontend",
        primary=("accessibility_auditor",),
        secondary=("frontend_developer", "web_quality_auditor"),
    ),
    GoldenQuery(
        id="e04",
        query="scrum master facilitating agile ceremonies and removing blockers",
        difficulty="easy",
        category="process",
        primary=("scrum_master",),
        secondary=("Agile_Transformation_Lead", "Technical_Program_Manager"),
    ),
    GoldenQuery(
        id="e05",
        query="terraform infrastructure as code module design",
        difficulty="easy",
        category="devops",
        primary=("terraform_iac_specialist",),
        secondary=("platform_engineer_iac", "cloud_architect"),
    ),
    GoldenQuery(
        id="e06",
        query="OSINT open source intelligence analyst",
        difficulty="easy",
        category="security",
        primary=("osint_intelligence_analyst",),
        secondary=("security_researcher", "threat_detection_engineer"),
    ),
    GoldenQuery(
        id="e07",
        query="bioinformatics NGS omics analysis pipeline",
        difficulty="easy",
        category="science",
        primary=("bioinformatics_engineer",),
        secondary=("scientific_database_orchestrator",),
    ),
)

# --------------------------------------------------------------------------
# Medium — paraphrase and purpose-level description, no shared vocabulary
# with the target's title (deck p21: 7 per 20)
# --------------------------------------------------------------------------
MEDIUM: tuple[GoldenQuery, ...] = (
    GoldenQuery(
        id="m01",
        query="I need help writing and speeding up database queries across Postgres and BigQuery",
        difficulty="medium",
        category="data",
        primary=("sql_assistant",),
        secondary=("data_analyst", "database_schema_designer", "analytics_engineer"),
        note="Paraphrase: never says SQL, never says the title.",
    ),
    GoldenQuery(
        id="m02",
        query="someone to answer angry customers about a broken subscription and close the ticket",
        difficulty="medium",
        category="support",
        primary=("customer_support_agent",),
        secondary=("customer_success_strategist", "community_manager"),
    ),
    GoldenQuery(
        id="m03",
        query="teach me by asking questions instead of giving me the answer",
        difficulty="medium",
        category="education",
        primary=("socratic_tutor",),
        secondary=("Adaptive_Learning_Designer", "Mr_Ranedeer", "LearnOS_PRO"),
    ),
    GoldenQuery(
        id="m04",
        query="grow organic traffic from search engines with keyword and backlink strategy",
        difficulty="medium",
        category="marketing",
        primary=("seo_specialist",),
        secondary=("growth_hacker", "paid_advertising_architect", "brand_strategist"),
    ),
    GoldenQuery(
        id="m05",
        query="translate a research paper from a PDF page by page keeping the layout",
        difficulty="medium",
        category="language",
        primary=("pdf_translator",),
        secondary=("Technical_Translator_Localizer", "research_paper_proofreader"),
    ),
    GoldenQuery(
        id="m06",
        query="review my code for injection flaws and insecure dependencies before merge",
        difficulty="medium",
        category="security",
        primary=("code_reviewer_security",),
        secondary=("security_researcher", "owasp_secure_application_architect", "defending_code_security_harness_architect"),
    ),
    GoldenQuery(
        id="m07",
        query="write API documentation that developers can actually skim",
        difficulty="medium",
        category="writing",
        primary=("technical_writer",),
        secondary=("Technical_Documentation_Strategist", "openwiki_agent_documentation_architect"),
    ),
    GoldenQuery(
        id="m08",
        query="plan retirement savings and build an investment portfolio for a family",
        difficulty="medium",
        category="finance",
        primary=("financial_advisor",),
        secondary=("cfo_financial_strategy", "investment_research_analyst"),
    ),
    GoldenQuery(
        id="m09",
        query="design core game loops, progression and player motivation systems",
        difficulty="medium",
        category="games",
        primary=("game_designer",),
        secondary=("Game_Economy_Designer", "Game_Level_Designer", "game_ai_designer"),
    ),
    GoldenQuery(
        id="m10",
        query="analyse a contract and research relevant case law",
        difficulty="medium",
        category="legal",
        primary=("legal_analyst",),
        secondary=("Contract_Negotiation_Strategist", "compliance_auditor", "ai_governance_legal_agent"),
    ),
    GoldenQuery(
        id="m11",
        query="build a hiring pipeline and structured interview process",
        difficulty="medium",
        category="hr",
        primary=("recruitment_strategist",),
        secondary=("hr_talent_development",),
    ),
    GoldenQuery(
        id="m12",
        query="differential diagnosis and SOAP note drafting for a patient encounter",
        difficulty="medium",
        category="health",
        primary=("clinical_assistant",),
        secondary=("healthcare_operations_agent", "Health_Informatics_Specialist", "healthcare_ai_architect"),
    ),
    GoldenQuery(
        id="m13",
        query="firmware for a microcontroller with tight memory and real time constraints",
        difficulty="medium",
        category="embedded",
        primary=("embedded_firmware_engineer",),
        secondary=("industrial_robotics_architect", "automotive_functional_safety_architect"),
    ),
    GoldenQuery(
        id="m14",
        query="prompts for generating video clips with camera movement and shot description",
        difficulty="medium",
        category="creative",
        primary=("video_gen_prompting",),
        secondary=("Cinematography_Prompt_Engineer", "openmontage_video_director", "agentic_video_editor"),
    ),
)

# --------------------------------------------------------------------------
# Hard — the query is answered by a CLUSTER of near-identical prompts, or it
# is ambiguous. This is where a whole-document embedding over a uniform corpus
# is expected to fail, and where a ranker earns its keep (deck p21: 5 per 20).
# --------------------------------------------------------------------------
HARD: tuple[GoldenQuery, ...] = (
    GoldenQuery(
        id="h01",
        query="an agent that remembers things across sessions instead of forgetting everything",
        difficulty="hard",
        category="agent-memory",
        primary=("agent_memory_architect", "agent_native_memory_system_architect", "personal_agent_brain_architect"),
        secondary=("proactive_memory_agent_long_horizon", "local_first_memory_engineer", "agent_state_hygiene_architect", "codebase_memory_mcp_architect"),
        note="The densest near-duplicate cluster in the library.",
    ),
    GoldenQuery(
        id="h02",
        query="stop a tool result or web page from hijacking my agent's instructions",
        difficulty="hard",
        category="security",
        primary=("prompt_injection_guardian",),
        secondary=("agent_data_injection_attack_auditor", "instruction_bleed_auditor", "memory_poisoning_attack_auditor", "guard_skill_architect"),
        note="Four auditors sit next to the guardian; only one is the defence.",
    ),
    GoldenQuery(
        id="h03",
        query="design a Model Context Protocol server exposing tools to an agent",
        difficulty="hard",
        category="agent-infra",
        primary=("mcp_server_architect",),
        secondary=("mcp_apps_ui_architect", "tool_schema_architect", "agent_tool_engineer", "codebase_memory_mcp_architect"),
    ),
    GoldenQuery(
        id="h04",
        query="orchestrate several retrieval agents over a document corpus and merge what they find",
        difficulty="hard",
        category="rag",
        primary=("multi_agent_rag_orchestrator",),
        secondary=("multi_agent_orchestrator", "deep_research", "webswarm_deep_wide_research_orchestrator", "notebooklm_research_orchestrator"),
    ),
    GoldenQuery(
        id="h05",
        query="cut the number of tokens my agent spends without losing what it needs to know",
        difficulty="hard",
        category="context",
        primary=("context_compression_architect", "prompt_compression_strategist", "agent_context_efficiency_engineer"),
        secondary=("headroom_context_compression_architect", "opensquilla_token_efficient_agent_architect", "elastic_context_orchestrator"),
    ),
    GoldenQuery(
        id="h06",
        query="score my agent's answers automatically and catch regressions before release",
        difficulty="hard",
        category="eval",
        primary=("agent_eval_designer", "eval_benchmark_architect"),
        secondary=("llm_judge_routing_strategist", "agentatlas_trajectory_eval_architect", "verification_specialist", "test_strategy_architect"),
        # KNOWN GAP, deliberately not yet applied: the judge (`--judge`) flagged
        # `agent_atlas_trajectory_auditor` as an exact answer here and it is one —
        # a sibling of the eval-architect above that this list missed. Adding it
        # raises precision for every ranker equally, so it is left out of the run
        # that the before/after comparison was measured on and belongs in the
        # next revision of this set, together with a re-baselining.
    ),
)

# --------------------------------------------------------------------------
# Multilingual — ADR-0053 makes Vietnamese the interface language while the
# whole corpus is English. Cross-lingual recall is the single property the
# embedding leg is supposed to have that the lexical leg cannot (deck p33,
# data-foundation: "hoàn tiền" ≈ "refund").
# --------------------------------------------------------------------------
MULTILINGUAL: tuple[GoldenQuery, ...] = (
    GoldenQuery(
        id="v01",
        query="trợ lý viết câu truy vấn SQL và tối ưu hoá cơ sở dữ liệu",
        difficulty="hard",
        category="multilingual",
        primary=("sql_assistant",),
        secondary=("data_analyst", "database_schema_designer"),
    ),
    GoldenQuery(
        id="v02",
        query="chăm sóc khách hàng, trả lời khiếu nại và hoàn tiền",
        difficulty="hard",
        category="multilingual",
        primary=("customer_support_agent",),
        secondary=("customer_success_strategist",),
    ),
    GoldenQuery(
        id="v03",
        query="kiểm tra bảo mật mã nguồn, tìm lỗ hổng trước khi phát hành",
        difficulty="hard",
        category="multilingual",
        primary=("code_reviewer_security",),
        secondary=("security_researcher", "owasp_secure_application_architect"),
    ),
    GoldenQuery(
        id="v04",
        query="viết tài liệu kỹ thuật cho lập trình viên",
        difficulty="hard",
        category="multilingual",
        primary=("technical_writer",),
        secondary=("Technical_Documentation_Strategist",),
    ),
)

# --------------------------------------------------------------------------
# Adversarial — out of scope. The correct answer is an empty list, and the
# product renders that honestly ("nothing resembles this"). Anything returned
# here is a false positive the import dialog would present as a near-duplicate.
# --------------------------------------------------------------------------
ADVERSARIAL: tuple[GoldenQuery, ...] = (
    GoldenQuery(
        id="a01",
        query="công thức nấu phở bò gia truyền Hà Nội",
        difficulty="adversarial",
        category="out-of-scope",
        note="Vietnamese beef noodle soup recipe. Nothing in a prompt library answers this.",
    ),
    GoldenQuery(
        id="a02",
        query="what time does the last train from Utrecht to Amsterdam leave on Sunday",
        difficulty="adversarial",
        category="out-of-scope",
    ),
    GoldenQuery(
        id="a03",
        query="zzqqx wibblefrotz plimbard",
        difficulty="adversarial",
        category="nonsense",
        note="No token in the corpus. A ranker without a floor still returns five rows.",
    ),
    GoldenQuery(
        id="a04",
        query="knitting patterns for a cable sweater in worsted weight yarn",
        difficulty="adversarial",
        category="out-of-scope",
    ),
    GoldenQuery(
        id="a05",
        query="my landlord will not return the deposit, what are my rights as a tenant in Vietnam",
        difficulty="adversarial",
        category="near-domain",
        note=(
            "Adjacent to legal_analyst but asks for advice, not for a prompt. "
            "Labelled adversarial because a prompt REGISTRY should not answer it; "
            "counted separately from the nonsense cases."
        ),
    ),
)

HAND_WRITTEN: tuple[GoldenQuery, ...] = EASY + MEDIUM + HARD + MULTILINGUAL + ADVERSARIAL

#: Prompts a duplicate probe is cut from. Chosen across the length range and
#: across clusters: two from the dense agent-memory block, three from isolated
#: single-topic prompts, one very long.
PROBE_SOURCES: tuple[str, ...] = (
    "sql_assistant",
    "kubernetes_specialist",
    "agent_memory_architect",
    "prompt_injection_guardian",
    "socratic_tutor",
    "clinical_assistant",
)

#: How much of a prompt a probe carries.
#:
#: 1,800 characters is roughly what somebody pastes from the top of a prompt
#: they are importing — the opening role and a rule or two. Not the whole file:
#: a probe that IS the document tests an identity lookup, and the import screen
#: never has the whole document, it has whatever was on the clipboard.
PROBE_CHARACTERS = 1800


def duplicate_probes(corpus) -> list[GoldenQuery]:
    """Whole-body probes: the import screen's duplicate check, measured.

    The head of a real prompt, sent to ``POST /prompts/search/similar``. The
    prompt it was cut from must rank first — the corpus contains that exact text
    — and anything else at rank 1 is a duplicate check that would let a person
    re-import a prompt they already own.

    **What this measures is self-retrieval of a verbatim prefix, and that is
    the whole of it.** There is no paraphrase here and no distractor, so the
    check cannot fail the way the product failed: a duplicate that was
    *rewritten* rather than copied shares none of these terms. Its
    ``context_precision_at_3`` of 0.333 is arithmetically forced as well — each
    probe has exactly one ``primary`` and the metric divides by ``len(top)`` —
    so that number has never carried information. The set that does carry it is
    ``eval/retrieval/similarity.py``: ten anchor/twin/decoy triplets, read by
    ``tests/golden/``. These probes are kept because verbatim self-retrieval is
    still worth a regression guard, not because they measure duplicate
    detection.
    """
    by_stem = {item.stem: item for item in corpus}
    probes: list[GoldenQuery] = []
    for index, stem in enumerate(PROBE_SOURCES, start=1):
        item = by_stem.get(stem)
        if item is None:
            continue
        text = item.raw.strip()[:PROBE_CHARACTERS]
        probes.append(
            GoldenQuery(
                id=f"d{index:02d}",
                query=text,
                difficulty="easy",
                category="duplicate-probe",
                primary=(item.stem,),
                route="similar",
                probe_source=item.source_file,
                note=f"first {PROBE_CHARACTERS} characters of {item.source_file}",
            )
        )
    return probes


def required_stems() -> tuple[str, ...]:
    """Every corpus file the golden set refers to, so selection can guarantee them."""
    names: set[str] = set(PROBE_SOURCES)
    for query in HAND_WRITTEN:
        names.update(query.primary)
        names.update(query.secondary)
    return tuple(sorted(names))
