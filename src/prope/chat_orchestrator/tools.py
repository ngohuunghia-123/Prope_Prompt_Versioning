"""The six executors behind the closed catalogue, and the two confirmed writes.

Deck 3 (p18-19) describes a good worker in three properties, and each one is a
constraint this module honours rather than a description of it:

* **one narrow capability** — each function below calls exactly one other
  module's public seam and does nothing else;
* **as stateless as possible** — every executor takes a :class:`ToolContext` and
  returns a :class:`ToolResult`, holding nothing between calls;
* **local failure does not break the architecture** — an executor returns
  `outcome="error"` and the supervisor answers with what it has. Deck 3 names
  the alternative *No Fallback* (p20): a worker that raises and a supervisor that
  waits forever for output to summarise.

**Permission is checked here, per tool, with the subject passed in.** access-
control's rule is that permission is a local decision and that it may not read
the subject it authorises — so the caller passes `owner_id` and `access_level`
from the row it already read. Two consequences worth being explicit about:

1. The route-level `ManagementAction` on `POST /chat/messages` is a declaration,
   not an authorisation (`declares_action` attaches and checks nothing). The
   check that matters for a write is the one in :func:`execute_create_prompt` and
   :func:`execute_create_revision`, at the moment the write happens, against the
   actor who confirmed it.
2. The read tools inherit `visible_subject_filter`, which is the same filter the
   search box runs behind. **The assistant cannot see a prompt the person cannot
   see**, and that is a property of where the filter is applied rather than a
   promise made in an instruction a model might not follow.
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession

from prope.access_control.domain import VisibleFilter
from prope.chat_orchestrator import knowledge
from prope.chat_orchestrator.domain import ToolName

__all__ = [
    "Evidence",
    "ToolContext",
    "ToolResult",
    "REGISTRY_FORMAT",
    "execute_create_prompt",
    "execute_create_revision",
    "propose_create_prompt",
    "propose_create_revision",
    "run_answer_from_docs",
    "run_convert_prompt",
    "run_find_duplicates",
    "run_search_prompts",
    "slugify",
]

#: How many prompts a search reports back. Five, not fifty: the answer is prose a
#: person reads in a chat panel, and a reply listing twenty titles is a reply
#: nobody finishes. The full result page is one `navigate` directive away.
SEARCH_LIMIT: Final = 5

#: How many the duplicate probe reports. Three, matching the import dialog's own
#: top-N, because it feeds the same decision.
DUPLICATE_LIMIT: Final = 3

#: How many documentation chunks the responder sees. Four fits inside the
#: evidence budget while leaving room for a search result alongside it, which is
#: the mixed case: "how do I import this, and do we already have one?"
DOCS_LIMIT: Final = 4

#: Below this the duplicate probe stops calling something a near-match. Higher
#: than search's own floor because the two questions differ: search asks *what is
#: closest*, and a duplicate check asserts *this may already exist* in the
#: product's own voice, which is a claim that should be wrong less often.
DUPLICATE_SIMILARITY_FLOOR: Final = 0.55


@dataclass(frozen=True, slots=True)
class Evidence:
    """One item the responder may cite.

    `text` is what the model reads and `label` is what the person sees. They are
    separate fields because the model needs the purpose line to answer and the
    citation chip needs a title that fits on one row.
    """

    tag: str
    kind: str
    reference: str
    label: str
    text: str
    score: float | None = None
    document: str | None = None


@dataclass(frozen=True, slots=True)
class Proposal:
    """A write the executor declined to perform. See `domain.PendingAction`."""

    tool: str
    summary: str
    preview: dict[str, Any]
    arguments: dict[str, Any]
    #: Machine code refining what the card announces when one tool stages more
    #: than one kind of consent. Absent means the tool name itself is the label.
    variant: str | None = None


@dataclass(frozen=True, slots=True)
class ToolResult:
    """What one worker returns to the supervisor.

    `payload` is the only channel between steps of a plan, and it carries data
    rather than decisions: the converted XML flows from `convert_prompt` into the
    duplicate probe, and nothing in it can add a step. That is deck 5's
    *Plan-Then-Execute* (p40) enforced by the shape of the type.
    """

    tool: str
    outcome: str
    evidence: tuple[Evidence, ...] = ()
    detail: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)
    proposal: Proposal | None = None
    #: A machine code the client translates when `outcome` is not `ok`.
    reason: str | None = None
    #: Queued cards behind this one, for a write the ROUTER chose whose targets a
    #: step resolved to several. Each entry is `{"tool", "arguments"}` naming the
    #: same write with one concrete target, so the person approves the act once
    #: per target and nothing here can introduce a tool the plan did not name —
    #: that boundary is what keeps this from being the step-adding channel
    #: `payload` must never become. Read by the routed turn only; a queued step
    #: re-running this tool carries its own resolved arguments, never a scope.
    follow_ups: tuple[dict[str, Any], ...] = ()


@dataclass(slots=True)
class ToolContext:
    """Everything an executor is allowed to know.

    Deck 3 (p34) calls this *need to know*: a worker receives the context it
    needs to finish its task and no more. There is deliberately no session, no
    request, and no way back to the HTTP layer — an executor that could reach
    those could do something the catalogue does not describe.
    """

    db: AsyncSession
    workspace_id: str
    actor_id: str
    visible: VisibleFilter
    #: The whole prompt body the person supplied with this turn, if any.
    attachment: str | None = None
    attachment_format: str = "txt"
    #: Filled by `convert_prompt` and read by the write proposals.
    converted_xml: str | None = None
    conversion_model: str | None = None
    conversion_schema_version: str | None = None
    #: The turn's own message, verbatim. A last-resort body source for the
    #  import tools: people paste prompts into the composer, not the attachment
    #  slot, and the words are the person's own either way.
    message_text: str | None = None
    #: What this thread recently created or touched (`{kind, ref, label}`,
    #: newest first). The last-resort target for a write whose reference the
    #: router left empty: "đổi tên prompt ấy" lands on the prompt this thread
    #: just made, not on a refusal.
    thread_entities: list[dict[str, str]] = field(default_factory=list)
    #: Running tag counter, so evidence is numbered across a whole plan.
    next_tag: int = 1

    def tag(self) -> str:
        tag = f"E{self.next_tag}"
        self.next_tag += 1
        return tag


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------


async def _rank(context: ToolContext, query: str, limit: int) -> list[Any]:
    """One semantic search through prompt-search's public seam.

    Imported inside the function rather than at module scope: `prope.app` builds
    its route table at import, and a chain that pulls the embedding client in
    before settings are read is how a test ends up talking to api.openai.com.
    """
    from prope.prompt_search.agent.search import semantic_search

    return await semantic_search(
        db=context.db,
        query=query,
        workspace_id=context.workspace_id,
        visible=context.visible,
        actor_id=context.actor_id,
        cursor=None,
        limit=limit,
    )


async def run_search_prompts(context: ToolContext, *, query: str) -> ToolResult:
    """Find prompts in the workspace by meaning."""
    if not query.strip():
        return ToolResult(
            tool=ToolName.SEARCH_PROMPTS, outcome="error", reason="chat_tool_missing_query"
        )

    try:
        results = await _rank(context, query, SEARCH_LIMIT)
    except Exception:
        # The embedding provider, the database, or the ranker. Which one is a log
        # line's business; the supervisor only needs to know it has no results.
        return ToolResult(
            tool=ToolName.SEARCH_PROMPTS,
            outcome="error",
            reason="chat_tool_search_unavailable",
        )

    evidence = tuple(
        Evidence(
            tag=context.tag(),
            kind="prompt",
            reference=result.prompt_id,
            label=result.title,
            text=f"{result.title} — {result.purpose}".strip(" —"),
            score=result.similarity,
        )
        for result in results
    )

    return ToolResult(
        tool=ToolName.SEARCH_PROMPTS,
        outcome="ok",
        evidence=evidence,
        detail={"result_count": len(evidence)},
        # `query` rides along so the directive layer can hand the search screen
        # the same words rather than dropping the person on an empty page. It
        # goes no further: `detail` is what reaches telemetry, and it holds a
        # count (A-020).
        payload={"prompt_ids": [item.reference for item in evidence], "query": query},
    )


async def run_find_duplicates(context: ToolContext, *, text: str | None = None) -> ToolResult:
    """Rank visible prompts against a whole body the person supplied.

    The body comes from the attachment, from the conversion that ran before
    this step, or — when neither exists because the person pasted the whole
    prompt into the message box — from the turn's own text. Never from the
    router's `query`: a router that summarised a 4 KB prompt into a search
    phrase would turn a duplicate check into a topic search, and the two answer
    different questions.
    """
    body = text or context.converted_xml or context.attachment or context.message_text
    if not body or not body.strip():
        return ToolResult(
            tool=ToolName.FIND_DUPLICATES, outcome="error", reason="chat_tool_missing_text"
        )

    try:
        results = await _rank(context, body, DUPLICATE_LIMIT)
    except Exception:
        return ToolResult(
            tool=ToolName.FIND_DUPLICATES,
            outcome="error",
            reason="chat_tool_search_unavailable",
        )

    near = [
        result
        for result in results
        if result.similarity is not None and result.similarity >= DUPLICATE_SIMILARITY_FLOOR
    ]

    evidence = tuple(
        Evidence(
            tag=context.tag(),
            kind="prompt",
            reference=result.prompt_id,
            label=result.title,
            text=f"{result.title} — {result.purpose}".strip(" —"),
            score=result.similarity,
        )
        for result in near
    )

    return ToolResult(
        tool=ToolName.FIND_DUPLICATES,
        outcome="ok",
        evidence=evidence,
        detail={"result_count": len(evidence)},
        payload={"duplicate_ids": [item.reference for item in evidence]},
    )


def _is_canonical(source: str) -> bool:
    """Whether this text is already a canonical body. Never raises.

    `validate_canonical_xml` answers by raising, and every one of its refusals
    means the same thing here — *this needs converting* — so they collapse to
    `False` rather than being enumerated. A new refusal shape added to the
    canonical contract therefore routes a source to the converter, which is the
    safe direction: the wrong answer costs a model call, not a bad body.
    """
    from prope.canonical_prompt import validate_canonical_xml

    try:
        validate_canonical_xml(source)
    except Exception:
        return False
    return True


async def run_convert_prompt(context: ToolContext, *, source_format: str | None = None) -> ToolResult:
    """Turn the attached source into Prope's canonical XML. Saves nothing.

    The permission the underlying route checks is `prompt.create`, and it is
    checked there rather than duplicated here — this executor calls the service
    directly and the write it precedes is what actually needs the grant. A person
    who may not create prompts sees the conversion and cannot confirm the save,
    which is the honest ordering: the refusal arrives at the moment something
    would be written.
    """
    from prope.prompt_conversion.domain import InvalidAgentOutputError, InvalidSourceError
    from prope.prompt_conversion.service import (
        AgentUnavailableError,
        ConversionContext,
        convert_source,
    )

    source = context.attachment or context.message_text
    if not source or not source.strip():
        return ToolResult(
            tool=ToolName.CONVERT_PROMPT, outcome="error", reason="chat_tool_missing_text"
        )

    # **A paste that is already canonical is not converted, and this is the whole
    # of "do not force it".** `convert_source` validates the AGENT's output
    # (`prompt_conversion.domain`) and never looks at its input, so a person who
    # pasted canonical XML had it sent to a model and rewritten anyway — a model
    # call they paid for, latency they waited through, and their own words
    # replaced by a paraphrase of them. Prope stores canonical bodies
    # (`RevisionCreate._body_is_canonical_xml`), and a body that already IS one
    # has nothing to gain by making the round trip.
    #
    # The validator is the whole test, deliberately: "canonical" is defined in
    # exactly one place (`prope.canonical_prompt`), it is the same function the
    # registry will apply at the write, and a second opinion here is a second
    # definition that can disagree with the one that decides.
    if _is_canonical(source):
        context.converted_xml = source
        # No model touched it, so there is no model and no schema version to
        # record. Leaving these None is what keeps `ck_revision_binding_is_whole`
        # honest: provenance names the converter that produced a body, and
        # naming one for a body nobody converted would be a false record.
        context.conversion_model = None
        context.conversion_schema_version = None
        context.attachment_format = "xml"
        return ToolResult(
            tool=ToolName.CONVERT_PROMPT,
            outcome="ok",
            reason="chat_source_already_canonical",
            detail={"model": "", "truncated": False, "converted": False},
            payload={"xml_body": source, "model": "", "schema_version": ""},
        )

    try:
        xml_body, model, schema_version = await convert_source(
            source,
            source_format or context.attachment_format,
            context=ConversionContext(
                workspace_id=context.workspace_id,
                actor_id=context.actor_id,
                prompt_id=None,
            ),
        )
    except InvalidSourceError:
        return ToolResult(
            tool=ToolName.CONVERT_PROMPT, outcome="error", reason="conversion_invalid_source"
        )
    except InvalidAgentOutputError:
        return ToolResult(
            tool=ToolName.CONVERT_PROMPT,
            outcome="error",
            reason="conversion_invalid_agent_output",
        )
    except AgentUnavailableError:
        return ToolResult(
            tool=ToolName.CONVERT_PROMPT,
            outcome="error",
            reason="conversion_agent_unavailable",
        )

    context.converted_xml = xml_body
    context.conversion_model = model
    context.conversion_schema_version = schema_version
    # The registry's spelling, not the wire's. `registry.revision` admits
    # `markdown` and not `md`, and its provenance constraint pairs the format
    # with the conversion model — so normalising here, at the moment the
    # conversion succeeds, is what stops a confirmed write failing on a CHECK
    # nobody saw until a person had already approved it.
    context.attachment_format = REGISTRY_FORMAT.get(
        (source_format or context.attachment_format).lower(), "txt"
    )

    return ToolResult(
        tool=ToolName.CONVERT_PROMPT,
        outcome="ok",
        detail={"model": model, "truncated": False},
        payload={"xml_body": xml_body, "model": model, "schema_version": schema_version},
    )


async def run_answer_from_docs(context: ToolContext, *, question: str) -> ToolResult:
    """Retrieve documentation chunks that answer a question about Prope itself."""
    if not question.strip():
        return ToolResult(
            tool=ToolName.ANSWER_FROM_DOCS, outcome="error", reason="chat_tool_missing_query"
        )

    outcome = await knowledge.retrieve(question, limit=DOCS_LIMIT)

    evidence = tuple(
        Evidence(
            tag=context.tag(),
            kind="doc",
            reference=scored.chunk.id,
            label=scored.chunk.heading,
            text=f"{scored.chunk.heading}\n{scored.chunk.text}",
            score=round(scored.score, 4),
            document=scored.chunk.document,
        )
        for scored in outcome.chunks
    )

    return ToolResult(
        tool=ToolName.ANSWER_FROM_DOCS,
        outcome="ok",
        evidence=evidence,
        detail={
            "chunk_count": len(evidence),
            "mode": "hybrid" if outcome.dense_ran else "lexical",
            "corpus": knowledge.corpus_fingerprint(),
        },
        payload={"dense_ran": outcome.dense_ran},
    )


# ---------------------------------------------------------------------------
# Write proposals
# ---------------------------------------------------------------------------

#: The wire's format vocabulary mapped onto `ck_revision_original_format`'s.
#: prompt-conversion aliases `md` and `yml` for its own input; the registry
#: column does not, and the two vocabularies meeting anywhere but here is how
#: a confirmed write ends in an IntegrityError.
REGISTRY_FORMAT: Final[dict[str, str]] = {
    "txt": "txt",
    "md": "markdown",
    "markdown": "markdown",
    "json": "json",
    "yml": "yaml",
    "yaml": "yaml",
}

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
_DEFAULT_NAMESPACE: Final = "imported"
#: `registry.domain.NAME_PATTERN` allows 63 characters. Held to it here rather
#: than trimmed later, because a name the registry refuses is a proposal a person
#: approves and then watches fail.
_MAX_NAME_CHARACTERS: Final = 63


def slugify(title: str, *, fallback: str = "prompt") -> str:
    """A registry-legal `name` derived from a title.

    Deterministic, so that proposing the same import twice proposes the same
    name — and so the *model-name taken* refusal a person then sees is telling
    them something true about their library rather than about a random suffix.
    """
    import unicodedata

    decomposed = unicodedata.normalize("NFD", title.lower())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c)).replace("đ", "d")
    slug = _SLUG_STRIP.sub("-", stripped).strip("-")[:_MAX_NAME_CHARACTERS].rstrip("-")
    return slug if slug and slug[0].isalnum() else fallback


def propose_create_prompt(
    context: ToolContext,
    *,
    title: str,
    purpose: str = "",
    namespace: str = _DEFAULT_NAMESPACE,
    change_summary: str = "",
) -> ToolResult:
    """Describe the prompt that would be created. Writes nothing.

    **This function has no `db` write and that is the design**, not an oversight
    to be closed later. Deck 5 (p54) puts *irreversible action* at the top of the
    escalate-to-a-human table, and a registered prompt with a revision is
    irreversible in the way that matters: the revision chain is immutable and the
    name is permanent (A-021). So the proposal carries the exact arguments and a
    person's second request is what runs them.
    """
    body = context.converted_xml
    if not body:
        return ToolResult(
            tool=ToolName.CREATE_PROMPT, outcome="error", reason="chat_tool_nothing_to_save"
        )

    arguments = {
        "namespace": namespace,
        "name": slugify(title),
        "title": title.strip()[:200],
        "purpose": purpose.strip()[:2000],
        # BR-01 as a default value, and not the model's to choose: the catalogue
        # has no tool that could make a prompt workspace-visible.
        "access_level": "private",
        "body": body,
        "change_summary": (change_summary or "Nhập qua trợ lý").strip()[:200],
        # **The person's own text, kept.** `execute_create_prompt` falls back to
        # `arguments["body"]` when this is absent, so an import that omitted it
        # stored the CONVERTED xml as the original — and the paste it was made
        # from existed nowhere afterwards. `registry.revision` carries
        # `original_body` precisely so a conversion is reversible by reading, and
        # the chat path was the one caller not filling it.
        "original_body": context.attachment or context.message_text or body,
        "original_format": context.attachment_format,
        "conversion_model": context.conversion_model,
        "conversion_schema_version": context.conversion_schema_version,
    }

    return ToolResult(
        tool=ToolName.CREATE_PROMPT,
        outcome="ok",
        detail={"steps": 1},
        proposal=Proposal(
            tool=ToolName.CREATE_PROMPT,
            summary=f"{arguments['namespace']}/{arguments['name']}",
            preview={
                "title": arguments["title"],
                "purpose": arguments["purpose"],
                "namespace": arguments["namespace"],
                "name": arguments["name"],
                "access_level": arguments["access_level"],
                "body_characters": len(body),
            },
            arguments=arguments,
        ),
    )


def propose_create_revision(
    context: ToolContext, *, prompt_id: str, change_summary: str = ""
) -> ToolResult:
    """Describe the revision that would be saved. Writes nothing."""
    body = context.converted_xml
    if not body:
        return ToolResult(
            tool=ToolName.CREATE_REVISION, outcome="error", reason="chat_tool_nothing_to_save"
        )

    arguments = {
        "prompt_id": prompt_id,
        "body": body,
        "change_summary": (change_summary or "Cập nhật qua trợ lý").strip()[:200],
        # **The person's own text, kept.** `execute_create_prompt` falls back to
        # `arguments["body"]` when this is absent, so an import that omitted it
        # stored the CONVERTED xml as the original — and the paste it was made
        # from existed nowhere afterwards. `registry.revision` carries
        # `original_body` precisely so a conversion is reversible by reading, and
        # the chat path was the one caller not filling it.
        "original_body": context.attachment or context.message_text or body,
        "original_format": context.attachment_format,
        "conversion_model": context.conversion_model,
        "conversion_schema_version": context.conversion_schema_version,
    }

    return ToolResult(
        tool=ToolName.CREATE_REVISION,
        outcome="ok",
        detail={"prompt_id": prompt_id, "steps": 1},
        proposal=Proposal(
            tool=ToolName.CREATE_REVISION,
            summary=prompt_id,
            preview={
                "prompt_id": prompt_id,
                "change_summary": arguments["change_summary"],
                "body_characters": len(body),
            },
            arguments=arguments,
        ),
    )


# ---------------------------------------------------------------------------
# Confirmed writes — reached only from the confirmation route
# ---------------------------------------------------------------------------


class WriteRefused(Exception):  # noqa: N818 - a refusal, not a failure
    """The confirmed write may not proceed. Carries a machine code, never prose."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


async def execute_create_prompt(context: ToolContext, arguments: dict[str, Any]) -> dict[str, str]:
    """Register the prompt and its first revision, in one transaction.

    The permission check is here, at the write, against the actor who confirmed —
    not against the actor who was proposed to. They are the same person today,
    because the proposal is only offered to its own actor; asserting it at the
    write is what keeps that true if a later feature shares a thread.
    """
    from prope.access_control.actions import Action
    from prope.access_control.seams import Actor, ActorType, Subject, SubjectType, may
    from prope.prompt_registry import commands
    from prope.prompt_registry.domain import RevisionDraft

    actor = Actor(
        type=ActorType.USER, id=context.actor_id, workspace_id=context.workspace_id
    )
    workspace = Subject(
        type=SubjectType.WORKSPACE,
        id=context.workspace_id,
        workspace_id=context.workspace_id,
    )
    if not await may(context.db, actor, Action.PROMPT_CREATE, workspace):
        raise WriteRefused("permission_denied")

    now = datetime.now(UTC)
    prompt = await commands.create_prompt(
        context.db,
        workspace_id=context.workspace_id,
        actor_id=context.actor_id,
        namespace=str(arguments["namespace"]),
        name=str(arguments["name"]),
        title=str(arguments["title"]),
        purpose=str(arguments.get("purpose") or ""),
        # The person who confirmed owns what they created. Never a value from the
        # proposal: `owner_id` is how A-007 lets an Admin register on somebody's
        # behalf, and that is a deliberate act on a form, not something an
        # assistant infers.
        owner_id=context.actor_id,
        access_level="private",
        tags=[],
        now=now,
    )

    revision = await commands.create_revision(
        context.db,
        workspace_id=context.workspace_id,
        actor_id=context.actor_id,
        prompt_id=prompt.id,
        draft=RevisionDraft(
            body=str(arguments["body"]),
            change_summary=str(arguments["change_summary"]),
            original_body=str(arguments.get("original_body") or arguments["body"]),
            original_format=str(arguments.get("original_format") or "txt"),
            conversion_model=arguments.get("conversion_model"),
            conversion_schema_version=arguments.get("conversion_schema_version"),
        ),
        now=now,
    )

    return {"prompt_id": prompt.id, "version_id": revision.version_id}


async def execute_create_revision(
    context: ToolContext, arguments: dict[str, Any]
) -> dict[str, str]:
    """Save the next revision of an existing prompt.

    Refuses in two different shapes on purpose, and the difference is A-116's:
    a prompt the actor cannot see is `not_found`, and one they can see but may
    not revise is `permission_denied`. Collapsing them would turn this route into
    an oracle for which prompt ids exist in a workspace.
    """
    from prope.access_control.actions import Action
    from prope.access_control.seams import (
        AccessLevel,
        Actor,
        ActorType,
        Subject,
        SubjectType,
        may,
    )
    from prope.prompt_registry import commands
    from prope.prompt_registry import repository as registry_repository
    from prope.prompt_registry.domain import RevisionDraft

    prompt_id = str(arguments["prompt_id"])
    row = await registry_repository.load_prompt(context.db, prompt_id)
    if row is None:
        raise WriteRefused("not_found")

    actor = Actor(
        type=ActorType.USER, id=context.actor_id, workspace_id=context.workspace_id
    )
    subject = Subject(
        type=SubjectType.PROMPT,
        id=row.id,
        workspace_id=row.workspace_id,
        owner_id=row.owner_id,
        access_level=AccessLevel(row.access_level),
        # ADR-0061. Read off the same row the other two come from, and required
        # for the same reason ADR-0020 requires them: a namespace grant is the
        # fifth source `may()` unions, and a subject that omitted its namespace
        # would silently skip it — which reads as "the grant does not work"
        # rather than as a missing field.
        namespace=row.namespace,
    )
    if not await may(context.db, actor, Action.REVISION_CREATE, subject):
        if await may(context.db, actor, Action.PROMPT_READ, subject):
            raise WriteRefused("permission_denied")
        raise WriteRefused("not_found")

    revision = await commands.create_revision(
        context.db,
        workspace_id=context.workspace_id,
        actor_id=context.actor_id,
        prompt_id=prompt_id,
        draft=RevisionDraft(
            body=str(arguments["body"]),
            change_summary=str(arguments["change_summary"]),
            original_body=str(arguments.get("original_body") or arguments["body"]),
            original_format=str(arguments.get("original_format") or "txt"),
            conversion_model=arguments.get("conversion_model"),
            conversion_schema_version=arguments.get("conversion_schema_version"),
        ),
        now=datetime.now(UTC),
    )

    return {"prompt_id": prompt_id, "version_id": revision.version_id}


#: The two executors this module owns directly. **The full write registry lives
#: in `executors.py`**, which joins these with the domain modules and asserts
#: completeness against the catalogue — one place, checked at import.
CONFIRMED_EXECUTORS: Final = {
    ToolName.CREATE_PROMPT: execute_create_prompt,
    ToolName.CREATE_REVISION: execute_create_revision,
}
