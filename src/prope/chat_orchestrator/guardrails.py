"""Input rails, output rails, and the directive validator between them.

Deck 5 (`docs/materials/5-guardrails-ai-safety.pdf`) is the whole of this file's
argument, and two of its sentences are the ones that shaped it:

* p42-43, *defense in depth* — three layers, each catching a different class of
  failure, none of them a replacement for another. Input rails here, LLM rails in
  `prompting.py` (spotlighting and an instruction hierarchy inside the signature),
  output rails here again.
* p37, *why filtering alone is not enough* — "data and instruction live in one
  token stream", emoji smuggling reaches 100% attack success against commercial
  guardrails, and durable defence comes from **architecture**: limit what the
  agent can do, not only what it may read. That is why the pattern list in
  `domain.py` exists and why this module is honest about being a *layer* rather
  than a solution. Nothing here is load-bearing on its own.

**Refusal is a product decision, not an error.** A refused turn returns a reply
the person can act on and a machine `code` the client translates (ADR-0053). It
is never a 500, never a stack trace, and never a silent empty answer — deck 5's
own framing (p57) is that a guardrail which makes the product feel broken is a
guardrail somebody will switch off.
"""

import re
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Final

from prope.chat_orchestrator.domain import (
    MAX_MESSAGE_CHARACTERS,
    UI_DIRECTIVE_ARGUMENTS,
    UiDirective,
    UiDirectiveKind,
)

__all__ = [
    "ALLOWED_DIALOGS",
    "ALLOWED_FORMS",
    "ALLOWED_FORM_FIELDS",
    "ALLOWED_HIGHLIGHTS",
    "ALLOWED_PANELS",
    "ALLOWED_STEPS",
    "ALLOWED_TABS",
    "NAVIGATION_ALLOW_LIST",
    "InputVerdict",
    "RateLimiter",
    "RefusalReason",
    "inspect_message",
    "redact_secrets",
    "sanitise_directives",
    "scrub_reply",
]


class RefusalReason:
    """Machine codes the client translates. Literal ASCII, per ADR-0053."""

    EMPTY = "chat_message_empty"
    TOO_LONG = "chat_message_too_long"
    INJECTION = "chat_message_refused_injection"
    OFF_TOPIC = "chat_message_off_topic"
    RATE_LIMITED = "chat_rate_limited"


@dataclass(frozen=True, slots=True)
class InputVerdict:
    """What the input rails decided, and why.

    `matched` names the rule rather than quoting the text it matched, for
    `TraceEntry`'s reason: the matched span is user content, and this verdict is
    logged, traced, and counted.
    """

    admitted: bool
    reason: str | None = None
    matched: str | None = None


# ---------------------------------------------------------------------------
# Layer 1 — validation
# ---------------------------------------------------------------------------

#: Unicode categories that carry no glyph and are the standard smuggling vector
#: deck 5 (p31, p37) names: zero-width joiners, directional overrides, and the
#: variation selectors that carry hidden payloads in "emoji smuggling". They are
#: stripped before any other rail runs, so that a pattern cannot be split by an
#: invisible character sitting inside the word `ignore`.
_INVISIBLE = re.compile(
    "[​-‏‪-‮⁠-⁤⁪-⁯︀-️﻿\U000e0000-\U000e007f]"
)


def _fold(text: str) -> str:
    """The string the rails below actually inspect.

    Invisibles removed, whitespace collapsed, case folded. Never stored, never
    returned — the original is what the agent sees, because normalising the input
    a person typed would change the meaning of the prompt they are importing.
    """
    return " ".join(_INVISIBLE.sub("", text).split()).casefold()


# ---------------------------------------------------------------------------
# Layer 2 — injection detection
# ---------------------------------------------------------------------------

#: Direct-injection patterns, in deck 5's p30 shape and extended past it.
#:
#: **These catch 60-70% of basic attempts and that is the honest claim** (deck 5,
#: p30 says exactly this number). They are here as the cheap layer, not the real
#: one: the real one is that this agent has six tools, no outbound capability, and
#: cannot write without a person pressing a button.
#:
#: Bilingual, because ADR-0053 makes Vietnamese the interface language and a
#: filter trained on English is the *language switch* bypass on p24 waiting to
#: happen. The Vietnamese forms are the ones a person would actually type.
_INJECTION_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = tuple(
    (name, re.compile(pattern, re.IGNORECASE))
    for name, pattern in (
        ("override_instructions", r"\bignore\s+(all\s+|any\s+)?(previous|above|prior|earlier)\b"),
        ("override_instructions_vi", r"\b(bỏ qua|phớt lờ|quên)\s+(mọi|tất cả|các)?\s*(hướng dẫn|chỉ dẫn|lệnh)"),
        ("disregard_instructions", r"\bdisregard\s+(all\s+|any\s+)?(previous|above|prior|your)\b"),
        ("persona_override", r"\byou are (now|no longer)\b"),
        ("persona_override_vi", r"\b(từ giờ|bây giờ) (bạn|mày) là\b"),
        ("system_prompt_extraction", r"\b(system|initial|original)\s+(prompt|instruction)"),
        ("system_prompt_extraction_vi", r"\b(prompt|chỉ thị) (hệ thống|gốc|ban đầu)\b"),
        ("reveal_instructions", r"\b(reveal|repeat|print|show|output)\s+(me\s+)?(your|the)\s+(instructions|prompt|rules|configuration)"),
        ("jailbreak_persona", r"\b(dan|do anything now|developer mode|no restrictions|without any (rules|filters))\b"),
        ("fake_turn", r"^\s*(system|assistant)\s*:", ),
        ("credential_fishing", r"\b(api[_ -]?key|secret[_ -]?key|access[_ -]?token|password|kek)\b.*\b(show|reveal|print|what|list|dump)\b"),
        ("credential_fishing_reverse", r"\b(show|reveal|print|list|dump)\b.*\b(api[_ -]?key|secret[_ -]?key|access[_ -]?token|\.env)\b"),
        ("prior_turn_extraction", r"\b(last|previous|other)\s+(user|person|customer)('s)?\s+(question|message|prompt|data)"),
        ("encoded_payload", r"\b(decode|base64|rot13)\b.{0,40}\b(and|then|rồi)\b.{0,40}\b(follow|execute|run|do)\b"),
    )
)


# ---------------------------------------------------------------------------
# Layer 3 — topic filter
# ---------------------------------------------------------------------------

#: Subjects this assistant refuses even when asked politely, because answering
#: them at all is the *DPD chatbot* incident on deck 5 p7: an assistant inside a
#: product answering a question the product has no business answering.
#:
#: Deliberately short. A long refusal list is a long list of things a person
#: cannot ask about their own prompt library, and the topic rail's real work is
#: done by the router — a request that maps to no tool gets `Intent.REFUSED`
#: without any of these firing.
_OFF_TOPIC_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = tuple(
    (name, re.compile(pattern, re.IGNORECASE))
    for name, pattern in (
        ("legal_or_medical_advice", r"\b(legal advice|medical advice|diagnos(e|is)|tư vấn pháp lý|chẩn đoán)\b"),
        ("financial_advice", r"\b(invest(ment)? advice|should i buy|crypto|cổ phiếu nào nên mua)\b"),
        ("weaponisation", r"\b(exploit|malware|ransomware|ddos|sql injection payload)\b.*\b(write|build|generate|viết|tạo)\b"),
    )
)


def inspect_message(text: str) -> InputVerdict:
    """Run every input rail over one turn's text, cheapest first.

    Order is deliberate and is the cost argument on deck 5 p43: validation is a
    length check, detection is a dozen regexes, and the topic filter is three
    more — all of it before a token is spent. The expensive layer, the router,
    only sees text that got past all of them.
    """
    if not text or not text.strip():
        return InputVerdict(admitted=False, reason=RefusalReason.EMPTY)

    if len(text) > MAX_MESSAGE_CHARACTERS:
        return InputVerdict(admitted=False, reason=RefusalReason.TOO_LONG)

    folded = _fold(text)

    for name, pattern in _INJECTION_PATTERNS:
        if pattern.search(folded):
            return InputVerdict(admitted=False, reason=RefusalReason.INJECTION, matched=name)

    for name, pattern in _OFF_TOPIC_PATTERNS:
        if pattern.search(folded):
            return InputVerdict(admitted=False, reason=RefusalReason.OFF_TOPIC, matched=name)

    return InputVerdict(admitted=True)


# ---------------------------------------------------------------------------
# Layer 4 — rate limiting
# ---------------------------------------------------------------------------


class RateLimiter:
    """A per-actor sliding window, in process memory.

    Deck 5 puts rate limiting in the input rails (p29) for a reason this product
    feels directly: every admitted turn spends the *app's own* provider key, not
    the workspace's. `LLM10 Unbounded Consumption` on the OWASP list (p10) is a
    cost attack before it is an availability one.

    **In process memory, and the limitation is stated rather than hidden.** Prope
    runs one `app` container (ADR-0033), so one process is the whole fleet and a
    shared counter would be a Redis nobody decided to have. The day a second
    replica exists this becomes a per-replica limit, which is the moment to move
    it — not before.
    """

    def __init__(self, *, limit: int = 20, window_seconds: float = 60.0) -> None:
        self._limit = limit
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = {}

    def admit(self, actor_id: str, *, now: float | None = None) -> bool:
        """True when this actor may spend another turn."""
        stamp = time.monotonic() if now is None else now
        window = self._hits.setdefault(actor_id, deque())

        while window and stamp - window[0] > self._window:
            window.popleft()

        if len(window) >= self._limit:
            return False

        window.append(stamp)
        return True

    def forget(self, actor_id: str) -> None:
        """Drop one actor's window. For tests and for a signed-out session."""
        self._hits.pop(actor_id, None)


# ---------------------------------------------------------------------------
# Output rails
# ---------------------------------------------------------------------------

#: Shapes that must never appear in a reply, whatever produced them.
#:
#: The agent has no tool that could read any of these, so a match means either
#: the model invented one — a hallucinated credential is still a credential a
#: person might try — or something upstream leaked. Both are redacted, and the
#: redaction is counted rather than silently applied.
_SECRET_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\b(?:pk|sk)_(?:live|test)_[A-Za-z0-9]{16,}"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]{20,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\b(api[_-]?key|secret|password|kek)\s*[:=]\s*\S{8,}"),
)

REDACTION = "[đã ẩn]"


def redact_secrets(text: str) -> tuple[str, int]:
    """The reply with any credential-shaped span replaced, and how many there were."""
    redacted = 0
    for pattern in _SECRET_PATTERNS:
        text, count = pattern.subn(REDACTION, text)
        redacted += count
    return text, redacted


#: Sentences from this module's own instructions. Their appearance in a reply is
#: `LLM07 System Prompt Leakage` (deck 5, p10) happening, and the whole reply is
#: replaced rather than patched: a reply that was mid-way through reciting its
#: instructions is not a reply whose remainder can be trusted.
_INSTRUCTION_MARKERS: Final[tuple[str, ...]] = (
    "SECURITY BOUNDARY",
    "UNTRUSTED DATA",
    "You are Prope's assistant",
    "TOOL CATALOGUE",
)


def scrub_reply(text: str) -> tuple[str, list[str]]:
    """Output content filter. Returns the safe reply and the rails that fired."""
    fired: list[str] = []

    for marker in _INSTRUCTION_MARKERS:
        if marker in text:
            return "", ["instruction_leak"]

    text, redacted = redact_secrets(text)
    if redacted:
        fired.append("secret_redacted")

    return text, fired


# ---------------------------------------------------------------------------
# The directive validator
# ---------------------------------------------------------------------------

#: Every route the agent may send somebody to, as anchored patterns.
#:
#: Anchored on both ends, and `{id}` is a bounded character class rather than
#: `.*`: an unanchored pattern would admit `/app/prompts@evil.example`, which
#: browsers route to the host and not to the path. That is the open-redirect the
#: `NAVIGATE` docstring in `domain.py` names.
#:
#: Kept in step with `src/prope-fe/features/prompt-lifecycle/PromptLifecycleRoutes.tsx`
#: by `test_every_navigable_route_exists_in_the_router`.
NAVIGATION_ALLOW_LIST: Final[tuple[re.Pattern[str], ...]] = tuple(
    re.compile(pattern)
    for pattern in (
        r"^/app/prompts$",
        r"^/app/prompts/new$",
        r"^/app/prompts/new/wizard$",
        r"^/app/prompts/folder/[A-Za-z0-9_-]{1,64}$",
        r"^/app/prompts/[A-Za-z0-9_-]{1,64}$",
        r"^/app/prompts/[A-Za-z0-9_-]{1,64}/edit$",
        r"^/app/prompts/[A-Za-z0-9_-]{1,64}/test$",
        r"^/app/prompts/[A-Za-z0-9_-]{1,64}/evaluation/run$",
        r"^/app/imports/new$",
        r"^/app/imports/[A-Za-z0-9_-]{1,64}$",
        r"^/app/search$",
        # The one route allowed to carry a query string, and it is percent-encoded
        # by the caller: the class is exactly `quote(..., safe="")`'s output
        # alphabet — unreserved characters and `%`. So a space, a `#`, a second
        # `?`, and an `&` that would smuggle a second parameter all fail the match
        # rather than arriving at the router as something to re-parse.
        r"^/app/search\?q=[A-Za-z0-9%._~-]{1,200}$",
        r"^/app/reviews$",
        r"^/app/datasets$",
        r"^/app/settings/providers$",
        r"^/app/settings/keys$",
        r"^/app/settings/workspace$",
    )
)

ALLOWED_PANELS: Final[frozenset[str]] = frozenset({"home", "chat", "search", "notifications"})
ALLOWED_TABS: Final[frozenset[str]] = frozenset(
    {"overview", "versioning", "evaluation", "logs", "production"}
)
ALLOWED_FORMS: Final[frozenset[str]] = frozenset({"import", "prompt-editor"})
ALLOWED_DIALOGS: Final[frozenset[str]] = frozenset({"convert-to-xml", "similar-prompts"})
ALLOWED_HIGHLIGHTS: Final[frozenset[str]] = frozenset(
    {
        "duplicate-card",
        "prompt-table",
        "search-results",
        "version-rail",
        "import-summary",
        "keys-list",
        "providers-list",
        "eval-runs",
    }
)
#: The import stepper the chat drives, in order.
ALLOWED_STEPS: Final[frozenset[str]] = frozenset(
    {"paste", "convert", "duplicates", "review", "save"}
)

#: Which fields a `prefill_form` directive may set. A closed set because the
#: client writes them straight into controlled inputs, and because a field named
#: here is a field somebody decided the agent should be able to touch — `owner_id`
#: and `access_level` are absent on purpose.
ALLOWED_FORM_FIELDS: Final[frozenset[str]] = frozenset(
    {"title", "purpose", "name", "namespace", "body", "change_summary", "tags"}
)

#: A prefilled field is rendered into an editable input, so it is bounded by what
#: the registry would accept rather than by what a model might emit.
_MAX_FIELD_CHARACTERS: Final = 32_768
#: How many directives one reply may carry. A reply that wants to do eleven
#: things to the interface is not a reply, it is a script.
_MAX_DIRECTIVES: Final = 6


def _navigable(target: Any) -> bool:
    return isinstance(target, str) and any(
        pattern.match(target) for pattern in NAVIGATION_ALLOW_LIST
    )


def _fields(raw: Any) -> dict[str, str] | None:
    """A `prefill_form` payload, cleaned — or `None` when nothing survives."""
    if not isinstance(raw, dict):
        return None

    cleaned: dict[str, str] = {}
    for key, value in raw.items():
        if key not in ALLOWED_FORM_FIELDS:
            continue
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value if isinstance(item, (str, int)))
        if not isinstance(value, str) or not value.strip():
            continue
        cleaned[key] = value[:_MAX_FIELD_CHARACTERS]

    return cleaned or None


def sanitise_directives(raw: Any) -> list[UiDirective]:
    """Turn whatever the agent proposed into directives the client may execute.

    **Drop, never raise, and never repair.** A directive the validator does not
    recognise is discarded and the rest of the reply still ships, because the
    text is the answer and the directives are the convenience. Raising here would
    let one malformed navigation turn a correct answer into an error page.

    A dropped directive is counted (`chat_directive_dropped_total`) so that a
    model quietly emitting nothing usable does not look identical to a model
    emitting nothing.
    """
    if not isinstance(raw, (list, tuple)):
        return []

    directives: list[UiDirective] = []

    for item in raw:
        if len(directives) >= _MAX_DIRECTIVES:
            break
        if not isinstance(item, dict):
            continue

        kind = item.get("kind")
        if not isinstance(kind, str) or kind not in UI_DIRECTIVE_ARGUMENTS:
            continue

        arguments = {
            key: value
            for key, value in item.items()
            if key in UI_DIRECTIVE_ARGUMENTS[kind]
        }

        match kind:
            case UiDirectiveKind.NAVIGATE:
                if not _navigable(arguments.get("to")):
                    continue
            case UiDirectiveKind.OPEN_PANEL:
                if arguments.get("panel") not in ALLOWED_PANELS:
                    continue
            case UiDirectiveKind.SELECT_TAB:
                if arguments.get("tab") not in ALLOWED_TABS:
                    continue
            case UiDirectiveKind.OPEN_DIALOG:
                if arguments.get("dialog") not in ALLOWED_DIALOGS:
                    continue
            case UiDirectiveKind.HIGHLIGHT:
                if arguments.get("target") not in ALLOWED_HIGHLIGHTS:
                    continue
            case UiDirectiveKind.SET_STEP:
                if arguments.get("step") not in ALLOWED_STEPS:
                    continue
            case UiDirectiveKind.PREFILL_FORM:
                if arguments.get("form") not in ALLOWED_FORMS:
                    continue
                fields = _fields(arguments.get("fields"))
                if fields is None:
                    continue
                arguments["fields"] = fields
            case _:  # pragma: no cover - the membership test above is total
                continue

        directives.append(UiDirective(kind=kind, arguments=arguments))

    return directives
