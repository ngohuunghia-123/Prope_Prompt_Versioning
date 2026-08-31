"""Pure types for the chat orchestrator. No I/O, no database, no model call.

Everything a reviewer needs to argue about the agent's *shape* lives here: what
it is allowed to decide, what it is allowed to do, what it is allowed to tell the
browser to do, and what it must stop and ask a person about.

**The catalogue is closed, and that is the security design rather than a tidiness
preference.** `docs/materials/5-guardrails-ai-safety.pdf` (p40) lists six design
patterns for defending an agent and puts *Action-Selector* first: the agent
chooses from a fixed list of tools and **never lets a tool's output decide which
tool runs next**. Prope needs that pattern more than most products do, because
the data this agent reads is other people's prompt bodies — text written to
instruct a model, frequently containing "ignore previous instructions" as a
matter of course (A-020, A-046). A retrieved prompt body is therefore *indirect
injection* in the deck's exact sense (p25), arriving through the front door, by
design, on the happy path.

**The lethal trifecta is broken at this file** (deck 5, p41). An agent holding
private data, untrusted content, and external communications can be made to
exfiltrate without limit, no matter how good the filters are. This agent holds
the first two irreducibly. Its outbound surface was zero until the improvement
flow needed technique evidence the internal corpus cannot carry, and the one
exception is built to keep the property that matters — **nothing a model or a
retrieved prompt can aim**: `research_topic` POSTs a topic string to one
operator-configured search endpoint (`tools_research`), refuses entirely when
that endpoint is unconfigured, drops answers from outside a domain allow-list,
and returns bounded excerpts that are evidence to cite and never commands to
obey. There is deliberately no fetch-a-URL tool, and :data:`TOOLS` is where
that absence stays enforced.

**Writes exist and are gated by a person, once, in the conversation.** The write
tools do not execute when the supervisor selects them. They produce a
:class:`PendingAction`, the turn ends, and a second HTTP request carrying an
explicit human decision is what runs them. That is *human-in-the-loop* in deck
5's taxonomy (p53) — agent proposes, human approves — chosen over
*human-on-the-loop* because retiring a prompt or revoking a key are exactly the
"irreversible action" row of the deck's trigger table (p54), and because
Prope's first non-negotiable is that no prompt reaches production without a
recorded human approval. The approval chain past that point is untouched: this
agent cannot submit, approve, or release, and no tool below could grow that
ability without an edit to this module.

**The catalogue covers every domain the product manages — except the two acts
that require reaching outside it.** `create_provider` and `rotate_credential`
are absent because `provider_access.commands` refuses any credential it has not
verified with a live probe of the upstream endpoint; giving this agent those two
tools would mean giving it outbound network access, which is the lethal
trifecta's third leg and is never traded for convenience here. For those two
acts the assistant reads the provider list and hands the person a navigation to
the settings screen where the form does its own verification.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final

__all__ = [
    "MAX_MESSAGE_CHARACTERS",
    "MAX_PLAN_STEPS",
    "MAX_TRACE_ENTRIES",
    "TOOLS",
    "UI_DIRECTIVE_ARGUMENTS",
    "Citation",
    "HitlModel",
    "Intent",
    "PendingAction",
    "ToolCall",
    "ToolName",
    "ToolSpec",
    "TraceEntry",
    "TraceStatus",
    "UiDirective",
    "UiDirectiveKind",
    "WRITE_TOOLS",
]


#: One chat turn's input ceiling. Deliberately far below the 32 KiB a revision
#: body may be: a person pasting a whole prompt into the chat box is doing the
#: import flow, and the import flow carries the body in its own field where the
#: guardrail layer treats it as data rather than as instructions. A 32 KiB
#: "message" is an injection payload wearing a question mark.
MAX_MESSAGE_CHARACTERS: Final = 4_000

#: How many tool calls one turn may make before the supervisor must answer with
#: what it has. Deck 3 (p51) puts the supervisor's job as *route and summarise*;
#: a supervisor that can loop is a supervisor that can loop forever on a provider
#: that keeps returning nothing, and the cost of that is charged to the app's own
#: key. Five covers the longest real plan — read a prompt, list its suites,
#: start an eval run, then read the results back — while staying far below
#: anything that could loop.
MAX_PLAN_STEPS: Final = 5

#: The trace is returned to the client and stored. It is bounded so that a
#: pathological turn cannot write an unbounded row, and because a trace nobody
#: can read is not the observability deck 3 (p45) asks for.
MAX_TRACE_ENTRIES: Final = 32


class Intent(StrEnum):
    """What the supervisor decided the person is asking for.

    A closed set for `ManagementAction`'s reason one layer out: an intent the
    router invented would fall through to a branch nobody wrote, and every such
    failure is silent in the *permissive* direction. `REFUSED` is a first-class
    member rather than an exception, because "this is out of scope" is an answer
    the product owes the person and not an error the log owes an operator.
    """

    #: "Find me the prompt that..." — a library question, answered by retrieval.
    SEARCH = "search"
    #: "Is this prompt already in my database?" — the whole body arrives with it.
    DUPLICATE_CHECK = "duplicate_check"
    #: "Import this prompt" — conversion, duplicate check, then a proposed write.
    IMPORT_PROMPT = "import_prompt"
    #: "How does release approval work?" — answered from the documentation corpus
    #: and never from the model's own memory of how some other product works.
    DOCS_QUESTION = "docs_question"
    #: "Rename this prompt", "retire it", "what versions does it have" — an act on
    #: one known prompt rather than a question about the library.
    MANAGE_PROMPT = "manage_prompt"
    #: "Make a folder for...", "rename the marketing folder" — registry
    #: organisation. Folders are namespaces with labels, so these are cheap acts.
    MANAGE_FOLDER = "manage_folder"
    #: "Mint a key for the mobile team", "revoke the old key" — consumer
    #: credential administration, behind `workspace.manage_keys`.
    MANAGE_KEYS = "manage_keys"
    #: "Disable the OpenRouter config" — provider configuration administration,
    #: minus the two acts that need a live probe (see the module docstring).
    MANAGE_PROVIDERS = "manage_providers"
    #: "Run the regression suite on this version" — evaluation. Starting a run
    #: spends workspace credit, so it proposes; reading results does not.
    RUN_EVALUATION = "run_evaluation"
    #: "Is v3 released?", "how did the last eval run go" — status reads that span
    #: release and evaluation state without acting on either.
    CHECK_STATUS = "check_status"
    #: A greeting, a thank-you, a "what can you do". Answered without a tool.
    SMALLTALK = "smalltalk"
    #: The automatic turn after a human decision on a proposal. Answered
    #: deterministically — the settle did the work; this intent exists so the
    #: ack never masquerades as a routed answer.
    DECISION_ACK = "decision_ack"
    #: Out of scope, or refused by an input rail. Carries no plan.
    REFUSED = "refused"


class HitlModel(StrEnum):
    """Deck 5's three human-in-the-loop models (p53), as a value on each tool.

    Attached to the tool rather than decided at the call site, because "which
    actions need a person" is the question a reviewer should be able to answer by
    reading one table — and because a call site that decides its own oversight
    level will eventually decide it needs none.
    """

    #: The agent acts; a person can see it afterwards in the trace and the
    #: history log. Correct for reads, which are reversible by definition.
    ON_THE_LOOP = "on_the_loop"
    #: The agent proposes; a person approves before anything is written.
    IN_THE_LOOP = "in_the_loop"


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """One entry in the closed catalogue.

    `description` is sent to the router as the tool's advertisement, so it is
    written for a model choosing between six options rather than for a human
    reading a reference. `permission` names the `Action` the executor checks
    before it runs — a value here and not an authorisation call, because
    access-control's rule is that permission is a local decision with the subject
    passed in, and this module is not the one holding the subject.
    """

    name: "ToolName"
    description: str
    hitl: HitlModel
    #: True when running this tool changes a row. Every one of these ends a turn
    #: with a `PendingAction` instead of a result.
    writes: bool
    #: The `prope.access_control.actions.Action` value the executor must hold.
    #: Carried as a string so this module keeps no import edge to access-control:
    #: the tool layer resolves it, and `test_every_tool_names_a_real_permission`
    #: is what stops the string drifting from the enum.
    permission: str


class ToolName(StrEnum):
    """The whole surface. A new capability costs an edit here, and nowhere else.

    Note what is absent and is meant to stay absent: nothing that sends, posts,
    emails, or fetches a URL; nothing that submits a revision for review,
    approves one, or releases one; nothing that creates or rotates a provider
    credential (both need a live probe — see the module docstring); nothing that
    reads a call body. The first group is the lethal trifecta's third leg. The
    second is the approval chain, which is the one thing a spreadsheet cannot do
    and is not delegable to a model on any confidence score. The last has no read
    path in the MVP at all.
    """

    SEARCH_PROMPTS = "search_prompts"
    FIND_DUPLICATES = "find_duplicates"
    CONVERT_PROMPT = "convert_prompt"
    ANSWER_FROM_DOCS = "answer_from_docs"
    CREATE_PROMPT = "create_prompt"
    CREATE_REVISION = "create_revision"

    # --- prompt registry: reads -------------------------------------------
    GET_PROMPT = "get_prompt"
    LIST_VERSIONS = "list_versions"
    GET_RELEASE_STATUS = "get_release_status"

    # --- improvement research ------------------------------------------------
    #: The one leg that reaches outside the product, and the reason it exists at
    #: all: an instruction-shaped revision request ("làm cho prompt này khó bị
    #: prompt injection hơn") needs technique evidence the internal docs corpus
    #: does not carry. Gated three ways in `tools_research` — unconfigured
    #: provider refuses, a domain allow-list bounds where answers come from, and
    #: every excerpt is bounded untrusted data the responder may cite and never
    #: obey. See that module's docstring before adding a second outbound call.
    RESEARCH_TOPIC = "research_topic"

    # --- folders ------------------------------------------------------------
    LIST_FOLDERS = "list_folders"
    CREATE_FOLDER = "create_folder"
    RENAME_FOLDER = "rename_folder"
    DELETE_FOLDER = "delete_folder"

    # --- prompt registry: writes -------------------------------------------
    UPDATE_PROMPT = "update_prompt"
    MOVE_PROMPT = "move_prompt"
    RETIRE_PROMPT = "retire_prompt"

    # --- consumer API keys ---------------------------------------------------
    LIST_API_KEYS = "list_api_keys"
    CREATE_API_KEY = "create_api_key"
    REVOKE_API_KEY = "revoke_api_key"
    SET_API_KEY_SCOPE = "set_api_key_scope"

    # --- provider configurations (no create/rotate — needs a live probe) ----
    LIST_PROVIDERS = "list_providers"
    UPDATE_PROVIDER = "update_provider"
    DELETE_PROVIDER = "delete_provider"

    # --- evaluation -----------------------------------------------------------
    LIST_SUITES = "list_suites"
    START_EVAL_RUN = "start_eval_run"
    GET_EVAL_RESULTS = "get_eval_results"


#: The catalogue, and the only place a tool comes into existence.
#:
#: A `MappingProxyType` rather than a dict, so that a caller cannot register one
#: at runtime. Discovery — deck 3's MCP `tools/list` (p28) — is deliberately not
#: adopted here: the deck's own argument for it is that an agent should not need
#: to be programmed to know a tool exists, and that property is exactly what this
#: module is refusing. A tool this file does not name cannot be called, and the
#: route table's closed-vocabulary argument (`ManagementAction`) is the same one.
TOOLS: Final[MappingProxyType[str, ToolSpec]] = MappingProxyType(
    {
        ToolName.SEARCH_PROMPTS: ToolSpec(
            name=ToolName.SEARCH_PROMPTS,
            description=(
                "Find prompts in this workspace by meaning — 'find the prompt "
                "that...', 'do we have anything about...'. Input: a short query."
            ),
            hitl=HitlModel.ON_THE_LOOP,
            writes=False,
            permission="prompt.read",
        ),
        ToolName.FIND_DUPLICATES: ToolSpec(
            name=ToolName.FIND_DUPLICATES,
            description=(
                "Check whether a pasted prompt already exists here, when the person "
                "supplies the whole body and asks if it is already there. Input: the "
                "pasted text."
            ),
            hitl=HitlModel.ON_THE_LOOP,
            writes=False,
            permission="prompt.read",
        ),
        ToolName.CONVERT_PROMPT: ToolSpec(
            name=ToolName.CONVERT_PROMPT,
            description=(
                "Convert pasted prompt source into canonical XML; first step of an "
                "import; saves nothing. Input: source text and format."
            ),
            hitl=HitlModel.ON_THE_LOOP,
            writes=False,
            permission="prompt.create",
        ),
        ToolName.ANSWER_FROM_DOCS: ToolSpec(
            name=ToolName.ANSWER_FROM_DOCS,
            description=(
                "Answer how Prope itself works — approval, release, permissions, "
                "gateway, policy — from documentation, not memory. Input: the question."
            ),
            hitl=HitlModel.ON_THE_LOOP,
            writes=False,
            permission="prompt.read",
        ),
        ToolName.CREATE_PROMPT: ToolSpec(
            name=ToolName.CREATE_PROMPT,
            description=(
                "Register a new prompt with its first revision. arguments: title, "
                "name (model name), purpose, tags, body; namespace = destination "
                "folder slug when the person names one (a folder that does not "
                "exist yet is created by the import itself)."
            ),
            hitl=HitlModel.IN_THE_LOOP,
            writes=True,
            permission="prompt.create",
        ),
        ToolName.CREATE_REVISION: ToolSpec(
            name=ToolName.CREATE_REVISION,
            description=(
                "Save a new revision of an existing prompt. arguments: prompt_id, body, note."
            ),
            hitl=HitlModel.IN_THE_LOOP,
            writes=True,
            permission="revision.create",
        ),
        ToolName.GET_PROMPT: ToolSpec(
            name=ToolName.GET_PROMPT,
            description=(
                "Show one named prompt's details: title, purpose, status, model "
                "name. Input: prompt id or name."
            ),
            hitl=HitlModel.ON_THE_LOOP,
            writes=False,
            permission="prompt.read",
        ),
        ToolName.LIST_VERSIONS: ToolSpec(
            name=ToolName.LIST_VERSIONS,
            description=(
                "List one prompt's revisions, newest first ('what versions does it "
                "have'). Input: prompt id."
            ),
            hitl=HitlModel.ON_THE_LOOP,
            writes=False,
            permission="prompt.read",
        ),
        ToolName.GET_RELEASE_STATUS: ToolSpec(
            name=ToolName.GET_RELEASE_STATUS,
            description=(
                "Report released versus latest revision ('is it live yet'). Input: "
                "prompt id."
            ),
            hitl=HitlModel.ON_THE_LOOP,
            writes=False,
            permission="prompt.read",
        ),
        ToolName.LIST_FOLDERS: ToolSpec(
            name=ToolName.LIST_FOLDERS,
            description=(
                "List the workspace's folders with prompt counts ('what folders do "
                "we have'). Takes no input."
            ),
            hitl=HitlModel.ON_THE_LOOP,
            writes=False,
            permission="prompt.read",
        ),
        ToolName.RESEARCH_TOPIC: ToolSpec(
            name=ToolName.RESEARCH_TOPIC,
            description=(
                "Search vetted public sources for general prompt-engineering "
                "technique guidance; only after answer_from_docs, and only when the "
                "question is general practice rather than how Prope works. Input: a "
                "short topic."
            ),
            hitl=HitlModel.ON_THE_LOOP,
            writes=False,
            # The act is reachable only while improving prompts the actor can
            # already read, and what it returns is public web content — so it
            # rides `prompt.read` rather than minting a grant nobody seeds.
            permission="prompt.read",
        ),
        ToolName.UPDATE_PROMPT: ToolSpec(
            name=ToolName.UPDATE_PROMPT,
            description=(
                "Change a prompt's metadata. arguments: prompt_id plus any of title, purpose, tags, instruction."
            ),
            hitl=HitlModel.IN_THE_LOOP,
            writes=True,
            permission="prompt.edit",
        ),
        ToolName.MOVE_PROMPT: ToolSpec(
            name=ToolName.MOVE_PROMPT,
            description=(
                "Move a prompt to another folder and/or change its slug; the "
                "destination folder may be created implicitly. arguments: prompt_id, "
                "namespace = destination folder slug, name = new slug when asked for."
            ),
            hitl=HitlModel.IN_THE_LOOP,
            writes=True,
            permission="prompt.edit",
        ),
        ToolName.RETIRE_PROMPT: ToolSpec(
            name=ToolName.RETIRE_PROMPT,
            description=(
                "Retire a prompt so the gateway stops resolving its model name. "
                "arguments: prompt_id."
            ),
            hitl=HitlModel.IN_THE_LOOP,
            writes=True,
            permission="prompt.retire",
        ),
        ToolName.CREATE_FOLDER: ToolSpec(
            name=ToolName.CREATE_FOLDER,
            description=(
                "Declare a new folder (namespace). arguments: name, description."
            ),
            hitl=HitlModel.IN_THE_LOOP,
            writes=True,
            permission="prompt.create",
        ),
        ToolName.RENAME_FOLDER: ToolSpec(
            name=ToolName.RENAME_FOLDER,
            description=(
                "Rename or re-describe an existing folder; the slug never changes. "
                "arguments: slug, name, description."
            ),
            hitl=HitlModel.IN_THE_LOOP,
            writes=True,
            permission="prompt.create",
        ),
        ToolName.DELETE_FOLDER: ToolSpec(
            name=ToolName.DELETE_FOLDER,
            description=(
                "Remove a folder's label; a folder that still holds prompts is "
                "negotiated, not refused — the first card warns, and confirming it "
                "stages a second that moves every prompt into backup before the "
                "label drops. arguments: slug, or {\"scope\": \"empty\"} to remove every "
                "folder that currently holds no prompt (one confirmation card each)."
            ),
            hitl=HitlModel.IN_THE_LOOP,
            writes=True,
            permission="prompt.create",
        ),
        ToolName.LIST_API_KEYS: ToolSpec(
            name=ToolName.LIST_API_KEYS,
            description=(
                "List consumer keys by name and last four digits, never secrets "
                "('which keys are active'). Takes no input."
            ),
            hitl=HitlModel.ON_THE_LOOP,
            writes=False,
            permission="workspace.manage_keys",
        ),
        ToolName.CREATE_API_KEY: ToolSpec(
            name=ToolName.CREATE_API_KEY,
            description=(
                "Mint a consumer key with an explicit scope; the plaintext is shown "
                "once on confirmation. arguments: name, scope."
            ),
            hitl=HitlModel.IN_THE_LOOP,
            writes=True,
            permission="workspace.manage_keys",
        ),
        ToolName.REVOKE_API_KEY: ToolSpec(
            name=ToolName.REVOKE_API_KEY,
            description=(
                "Revoke a consumer key immediately. arguments: key_id."
            ),
            hitl=HitlModel.IN_THE_LOOP,
            writes=True,
            permission="workspace.manage_keys",
        ),
        ToolName.SET_API_KEY_SCOPE: ToolSpec(
            name=ToolName.SET_API_KEY_SCOPE,
            description=(
                "Replace a key's whole scope with new lists — wholesale, not a "
                "delta. arguments: key_id, scopes."
            ),
            hitl=HitlModel.IN_THE_LOOP,
            writes=True,
            permission="workspace.manage_keys",
        ),
        ToolName.LIST_PROVIDERS: ToolSpec(
            name=ToolName.LIST_PROVIDERS,
            description=(
                "List provider configurations with verification status, no "
                "credential material. Takes no input."
            ),
            hitl=HitlModel.ON_THE_LOOP,
            writes=False,
            permission="catalogue.read",
        ),
        ToolName.UPDATE_PROVIDER: ToolSpec(
            name=ToolName.UPDATE_PROVIDER,
            description=(
                "Change a provider configuration's display name, enabled state or "
                "concurrency limits; credentials cannot be added or rotated here. "
                "arguments: provider_config_id plus any of name, enabled, limits."
            ),
            hitl=HitlModel.IN_THE_LOOP,
            writes=True,
            permission="provider.configure",
        ),
        ToolName.DELETE_PROVIDER: ToolSpec(
            name=ToolName.DELETE_PROVIDER,
            description=(
                "Remove a provider configuration; refused while revisions still "
                "bind to it. arguments: provider_config_id."
            ),
            hitl=HitlModel.IN_THE_LOOP,
            writes=True,
            permission="provider.disable",
        ),
        ToolName.LIST_SUITES: ToolSpec(
            name=ToolName.LIST_SUITES,
            description=(
                "List one prompt's evaluation suites; use before starting a run "
                "when suites were not named. Input: prompt id."
            ),
            hitl=HitlModel.ON_THE_LOOP,
            writes=False,
            permission="suite.read",
        ),
        ToolName.START_EVAL_RUN: ToolSpec(
            name=ToolName.START_EVAL_RUN,
            description=(
                "Start evaluation runs of one prompt version against its suites; "
                "spends workspace credit. arguments: prompt_id, version_id, suites."
            ),
            hitl=HitlModel.IN_THE_LOOP,
            writes=True,
            permission="run.start",
        ),
        ToolName.GET_EVAL_RESULTS: ToolSpec(
            name=ToolName.GET_EVAL_RESULTS,
            description=(
                "Summarise recent evaluation runs of one prompt: pass rates, "
                "suites, recency ('how did the last test go'). Input: prompt id."
            ),
            hitl=HitlModel.ON_THE_LOOP,
            writes=False,
            permission="run.read",
        ),
    }
)

#: The write half, derived rather than repeated. A tool that gains `writes=True`
#: joins this set without anybody remembering to add it, which is the point.
WRITE_TOOLS: Final[frozenset[str]] = frozenset(name for name, spec in TOOLS.items() if spec.writes)


@dataclass(frozen=True, slots=True)
class ToolCall:
    """One step of a plan: which tool, with what.

    `arguments` is a plain dict rather than a typed union because the router is a
    language model and the shapes it can emit are not enumerable in advance. It
    is validated at the executor, per tool, where a missing key is a refusal the
    supervisor can report rather than a `KeyError` that ends the turn.
    """

    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)


class TraceStatus(StrEnum):
    """Deck 3's `status` field (p45): `ok | warn | error`, spelled out."""

    OK = "ok"
    WARN = "warn"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class TraceEntry:
    """One line of the decision path, in deck 3's shape (p45) minus one field.

    The deck asks for seven: timestamp, agent_id, action, input_summary,
    output_summary, status, latency_ms. Six of them are here. **`input_summary`
    is deliberately absent**, and its absence is the single most load-bearing
    decision in this file.

    A summary of a chat turn's input is a summary of what somebody typed, and
    what they typed is frequently a whole corporate prompt — the import flow
    exists because that is the normal case. A-020 forbids that text reaching
    anywhere it is not governed, and the trace is returned over the wire, stored
    in `chat.message`, and mirrored into Langfuse. So this carries *counts and
    identifiers*: how many results, which prompt ids, which tool, how long. A
    reader can reconstruct the route the decision took, which is what deck 3 (p46)
    actually asks a trace to make visible — "the path the decision took", not the
    content it took it over.

    `detail` is a small dict of scalars, checked at construction by the layer that
    builds these rather than here, so a future field cannot smuggle a body in
    under a new key without somebody editing `observability.SAFE_TRACE_KEYS`.
    """

    agent: str
    action: str
    status: TraceStatus
    latency_ms: int
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Citation:
    """Where one claim in a reply came from.

    Two shapes in one type, distinguished by which id is set: a documentation
    chunk (`document_id` + `heading`) or a stored prompt (`prompt_id` + `title`).
    They are one type because the client renders them in one list and because a
    reply grounded in a mix of both is the normal case for "how do I import this,
    and do we already have it?".
    """

    kind: str
    reference: str
    label: str
    #: Cosine similarity for a retrieved chunk, or `None` when the citation names
    #: a row the agent read directly rather than retrieved.
    score: float | None = None
    #: Stable display number, assigned from first appearance in the reply.
    index: int = 0
    #: Character offsets where the source was cited. Kept in the citation JSON so
    #: a transcript can reconstruct inline source buttons without rerunning RAG.
    mentions: tuple[int, ...] = ()
    #: A bounded, already-authorised extract. Prompt evidence is title + purpose,
    #: never its body; documentation evidence is the retrieved section.
    excerpt: str = ""
    #: Shipped knowledge document name for documentation citations.
    document: str | None = None
    #: Internal route for sources the person may open directly.
    href: str | None = None


class UiDirectiveKind(StrEnum):
    """The closed vocabulary the agent may use to drive the browser.

    **Why a vocabulary and not a URL or a script.** The reply is model output, and
    model output that the client executes is the shortest path from an injected
    prompt body to a real action in somebody's session. A closed set of named
    intents, each with a validated argument shape, means the worst a compromised
    model can do is ask for a navigation the client already offers on a menu.

    **`navigate` is validated against a route allow-list**, not merely
    string-checked, because an unvalidated `to` is an open redirect that the
    product itself performs — the one phishing primitive a chat assistant should
    never hand out.
    """

    #: Move the SPA to one of Prope's own routes.
    NAVIGATE = "navigate"
    #: Switch the navigation rail's mode: `home`, `chat`, `search`, `notifications`.
    OPEN_PANEL = "open_panel"
    #: Select a tab within the page the person is on.
    SELECT_TAB = "select_tab"
    #: Fill a named form with named fields, without submitting it.
    PREFILL_FORM = "prefill_form"
    #: Draw attention to a named region already on screen.
    HIGHLIGHT = "highlight"
    #: Open one of the app's existing dialogs by name.
    OPEN_DIALOG = "open_dialog"
    #: Advance the import stepper the chat is driving.
    SET_STEP = "set_step"


#: `kind -> the argument keys it admits`. Extra keys are dropped rather than
#: rejected, because a model that adds a field should degrade to the directive
#: working, not to the turn failing — but an unknown *kind* is dropped whole,
#: because that is a directive nobody wrote a handler for.
UI_DIRECTIVE_ARGUMENTS: Final[MappingProxyType[str, frozenset[str]]] = MappingProxyType(
    {
        UiDirectiveKind.NAVIGATE: frozenset({"to"}),
        UiDirectiveKind.OPEN_PANEL: frozenset({"panel"}),
        UiDirectiveKind.SELECT_TAB: frozenset({"tab"}),
        UiDirectiveKind.PREFILL_FORM: frozenset({"form", "fields"}),
        UiDirectiveKind.HIGHLIGHT: frozenset({"target"}),
        UiDirectiveKind.OPEN_DIALOG: frozenset({"dialog"}),
        UiDirectiveKind.SET_STEP: frozenset({"step"}),
    }
)


@dataclass(frozen=True, slots=True)
class UiDirective:
    """One instruction to the client, already validated.

    Constructed only by `guardrails.sanitise_directives`. A `UiDirective` that
    exists is one the client may execute, which is why nothing else builds them.
    """

    kind: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PendingAction:
    """A write the agent wants to make and has not made.

    **This is the object the whole HITL design rests on**, so it carries the
    *preview* rather than a promise to compute one later: deck 5's anti-pattern
    list (p57) names "human review but no context" as the failure that turns
    approval into a rubber stamp. `summary` and `preview` are what the client
    renders on the confirmation card, and `arguments` is the exact payload the
    executor will use — not a re-derivation of it, so that what a person approved
    and what runs cannot differ.

    `id` is opaque and single-use: the confirmation route consumes it, and a
    second confirmation of the same id is a no-op rather than a second write.
    """

    id: str
    tool: str
    summary: str
    preview: dict[str, Any]
    arguments: dict[str, Any]
    #: A machine code the client translates in place of the tool name when one
    #: tool stages more than one kind of consent card — `delete_folder` stages a
    #: plain deletion and, behind an approval, the negotiated move-to-backup-
    #: then-delete whose card must not both announce "delete folder". Persisted
    #: with the row so a reopened thread still shows the right label. Never read
    #: by the executor: dispatch is by `tool`, exactly as before.
    variant: str | None = None
    #: The import source this proposal was made from. Persisted with the row so
    #  the follow-up turn — the one that finishes a "…and put it in a new
    #  folder" request — can convert and propose without the person pasting the
    #  body a second time. Never rendered to the client.
    resume_attachment: str | None = None
    resume_attachment_format: str | None = None
    #: The plan steps queued behind this one, oldest first: `{"tool": name,
    #: "arguments": {...}}`. Persisted with the pending-action row so an
    #: approval runs the next step automatically instead of dropping it —
    #: the fix for a multi-write request losing its second half to the first
    #: confirmation card. Prope-written, never model prose; never rendered.
    remaining_steps: list[dict[str, Any]] = field(default_factory=list)
