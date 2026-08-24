"""The research leg: vetted public sources, reached server-side, heavily gated.

The catalogue's founding rule is that this agent holds **no** outbound
capability (`domain.py`'s lethal-trifecta argument). `research_topic` is the one
deliberate exception, and it is shaped by that rule rather than beside it:

* **Config-gated.** With no `CHAT_RESEARCH_API_URL` set the tool does not exist
  in practice — every call answers `chat_tool_research_unavailable` and the flow
  degrades to the documentation corpus plus the model's own knowledge. A deploy
  that never sets the variable ships exactly the posture the invariant describes.
* **Endpoint-pinned, not URL-fetching.** The tool POSTs a topic to one operator-
  configured search API. Neither the router nor anything a retrieved prompt says
  can aim it at a URL; there is no fetch-a-link capability to talk into.
* **Domain allow-list.** Answers from outside `CHAT_RESEARCH_ALLOWED_DOMAINS`
  (a conservative default when unset) are dropped before they become evidence,
  so a compromised or SEO-poisoned result cannot wear a citation.
* **Bounded untrusted data.** Three results, five-hundred-character excerpts,
  kind `"web"` evidence like any other: the responder may cite them and must
  never obey them.

Every failure — unconfigured, timeout, non-2xx, malformed payload — returns
`outcome="error"` with a reason code. Nothing here raises past the worker layer.
"""

import os
from typing import Any, Final

import httpx
import structlog

from prope.chat_orchestrator import tools
from prope.chat_orchestrator.domain import ToolName

__all__ = ["run_research_topic"]

logger = structlog.get_logger(__name__)

RESULTS_LIMIT: Final = 3
EXCERPT_CHARACTERS: Final = 500
TIMEOUT_SECONDS: Final = 12.0

#: When the operator names no allow-list, these are the only domains an answer
#: may come from. Vendor documentation and primary research — the sources whose
#: claims about prompt-injection defence survive scrutiny — rather than blogs.
DEFAULT_ALLOWED_DOMAINS: Final = (
    "anthropic.com",
    "openai.com",
    "google-deepmind.github.io",
    "simonwillison.net",
    "owasp.org",
    "nist.gov",
    "arxiv.org",
    "microsoft.com",
)


def _api_url() -> str:
    # Read per call, not at import: an operator can add the variable without a
    # redeploy of the process that already imported this module, and tests can
    # toggle it with the env alone.
    return os.getenv("CHAT_RESEARCH_API_URL", "").strip()


def _allowed_domains() -> frozenset[str]:
    raw = os.getenv("CHAT_RESEARCH_ALLOWED_DOMAINS", "")
    domains = tuple(d.strip().lower() for d in raw.split(",") if d.strip())
    return frozenset(domains) or frozenset(DEFAULT_ALLOWED_DOMAINS)


def _unavailable(reason: str) -> tools.ToolResult:
    return tools.ToolResult(tool=ToolName.RESEARCH_TOPIC, outcome="error", reason=reason)


def _host_of(url: str) -> str:
    try:
        return httpx.URL(url).host.lower()
    except Exception:
        return ""


async def run_research_topic(context: tools.ToolContext, *, query: str) -> tools.ToolResult:
    """Three bounded excerpts from allow-listed public sources, or a named refusal."""
    api_url = _api_url()
    if not api_url:
        return _unavailable("chat_tool_research_unavailable")
    if not query.strip():
        return _unavailable("chat_tool_missing_query")

    payload: dict[str, Any] | None = None
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.post(
                api_url,
                json={"query": query.strip(), "max_results": RESULTS_LIMIT},
                headers={"Authorization": f"Bearer {os.getenv('CHAT_RESEARCH_API_KEY', '')}"}
                if os.getenv("CHAT_RESEARCH_API_KEY")
                else {},
            )
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        # The class name only: a provider error body can echo the query, and the
        # query is frequently a quote from a prompt body (A-020's shape).
        logger.warning(
            "chat_orchestrator.research_failed",
            exception=type(exc).__name__,
            actor_id=context.actor_id,
            workspace_id=context.workspace_id,
        )
        return _unavailable("chat_tool_research_unavailable")

    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        return _unavailable("chat_tool_research_unavailable")

    allowed = _allowed_domains()
    evidence: list[tools.Evidence] = []
    for item in results:
        if not isinstance(item, dict) or len(evidence) >= RESULTS_LIMIT:
            break
        url = str(item.get("url", ""))
        host = _host_of(url)
        if not host or not any(host == d or host.endswith(f".{d}") for d in allowed):
            continue
        title = " ".join(str(item.get("title", "")).split())[:120]
        content = " ".join(str(item.get("content", "")).split())[:EXCERPT_CHARACTERS]
        if not content:
            continue
        evidence.append(
            tools.Evidence(
                tag=context.tag(),
                kind="web",
                reference=url[:300],
                label=title or host,
                text=f"{title} ({host}): {content}".strip(": "),
            )
        )

    if not evidence:
        return _unavailable("chat_tool_no_allowed_results")

    return tools.ToolResult(
        tool=ToolName.RESEARCH_TOPIC,
        outcome="ok",
        evidence=tuple(evidence),
        detail={"result_count": len(evidence), "domains_configured": bool(os.getenv("CHAT_RESEARCH_ALLOWED_DOMAINS"))},
        payload={"sources": [item.reference for item in evidence]},
    )
