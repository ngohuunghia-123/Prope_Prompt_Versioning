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
the first two irreducibly. So it holds **no** outbound capability at all: there
is no tool that sends, posts, emails, or fetches a URL, and :data:`TOOLS` is
where that absence is enforced rather than merely observed.

**Writes exist and are gated by a person, once, in the conversation.** The two
write tools do not execute when the supervisor selects them. They produce a
:class:`PendingAction`, the turn ends, and a second HTTP request carrying an
explicit human decision is what runs them. That is *human-in-the-loop* in deck
5's taxonomy (p53) — agent proposes, human approves — chosen over
*human-on-the-loop* because creating a prompt and saving a revision are exactly
the "irreversible action" row of the deck's trigger table (p54), and because
Prope's first non-negotiable is that no prompt reaches production without a
recorded human approval. The approval chain past that point is untouched: this
agent cannot submit, approve, or release, and no tool below could grow that
ability without an edit to this module.
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
#: key. Three is enough for the longest real plan — convert, then check for
#: duplicates, then propose the write.
MAX_PLAN_STEPS: Final = 3

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
    #: A greeting, a thank-you, a "what can you do". Answered without a tool.
    SMALLTALK = "smalltalk"
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
    """The whole surface. Six entries, and a seventh costs an edit here.

    Note what is absent and is meant to stay absent: nothing that sends, posts,
    emails, or fetches a URL; nothing that submits a revision for review,
    approves one, or releases one; nothing that reads a call body. The first
    group is the lethal trifecta's third leg. The second is the approval chain,
    which is the one thing a spreadsheet cannot do and is not delegable to a
    model on any confidence score. The third has no read path in the MVP at all.
    """

    SEARCH_PROMPTS = "search_prompts"
    FIND_DUPLICATES = "find_duplicates"
    CONVERT_PROMPT = "convert_prompt"
    ANSWER_FROM_DOCS = "answer_from_docs"
    CREATE_PROMPT = "create_prompt"
    CREATE_REVISION = "create_revision"


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
                "Find prompts in this workspace by meaning. Use for 'find the prompt "
                "that...', 'do we have anything about...', or any request to locate "
                "an existing prompt. Input: a short search query."
            ),
            hitl=HitlModel.ON_THE_LOOP,
            writes=False,
            permission="prompt.read",
        ),
        ToolName.FIND_DUPLICATES: ToolSpec(
            name=ToolName.FIND_DUPLICATES,
            description=(
                "Check whether a prompt the person has pasted already exists in the "
                "workspace. Use when they supply a whole prompt body and ask whether "
                "it is already there. Input: the pasted prompt text."
            ),
            hitl=HitlModel.ON_THE_LOOP,
            writes=False,
            permission="prompt.read",
        ),
        ToolName.CONVERT_PROMPT: ToolSpec(
            name=ToolName.CONVERT_PROMPT,
            description=(
                "Convert pasted prompt source into Prope's canonical XML structure. "
                "Use as the first step of an import. Saves nothing. Input: the "
                "pasted source text and its format."
            ),
            hitl=HitlModel.ON_THE_LOOP,
            writes=False,
            permission="prompt.create",
        ),
        ToolName.ANSWER_FROM_DOCS: ToolSpec(
            name=ToolName.ANSWER_FROM_DOCS,
            description=(
                "Answer a question about how Prope itself works — approval, release, "
                "permissions, the gateway, policy. Use for any question about the "
                "product rather than about a stored prompt. Input: the question."
            ),
            hitl=HitlModel.ON_THE_LOOP,
            writes=False,
            permission="prompt.read",
        ),
        ToolName.CREATE_PROMPT: ToolSpec(
            name=ToolName.CREATE_PROMPT,
            description=(
                "Register a new prompt and its first revision. Requires the person's "
                "explicit confirmation and never runs in the same turn it is chosen."
            ),
            hitl=HitlModel.IN_THE_LOOP,
            writes=True,
            permission="prompt.create",
        ),
        ToolName.CREATE_REVISION: ToolSpec(
            name=ToolName.CREATE_REVISION,
            description=(
                "Save a new revision of an existing prompt. Requires the person's "
                "explicit confirmation and never runs in the same turn it is chosen."
            ),
            hitl=HitlModel.IN_THE_LOOP,
            writes=True,
            permission="revision.create",
        ),
    }
)

#: The write half, derived rather than repeated. A tool that gains `writes=True`
#: joins this set without anybody remembering to add it, which is the point.
WRITE_TOOLS: Final[frozenset[str]] = frozenset(
    name for name, spec in TOOLS.items() if spec.writes
)


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
