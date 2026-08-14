"""Mock LLM provider.

Deterministic-ish: it patterns on the system prompt to produce a clearly
improved version of whatever you feed it. This lets the agent run end-to-end
without an API key during development and tests.

It is intentionally simple — the goal is "looks like an improvement", not
"actually the best rewrite". The real OpenAI path is the production path.
"""
from __future__ import annotations

import time
from typing import Any

from .base import LLMMessage, LLMProvider, LLMResponse


def _looks_like_system_prompt(text: str) -> bool:
    return any(
        marker in text.lower()
        for marker in (
            "you are",
            "your task",
            "your role",
            "act as",
            "you will",
            "assistant",
        )
    )


def _extract_original_block(message: str) -> str | None:
    """Pull the user's actual prompt out of a node template.

    Each user-side template wraps the prompt in `# Original prompt\\n\\n...`.
    For the explainer we don't use this; for analyst/optimizer we do.
    """
    if "# Original prompt" not in message:
        return None
    after = message.split("# Original prompt", 1)[1]
    # Cut at the next all-caps heading we know about.
    cut_markers = (
        "# Analyst report",
        "# Metadata",
        "# Optimized prompt",
        "# Analyst findings",
        "# Changes applied",
        "# Deterministic comparison",
        "# Output",
    )
    for marker in cut_markers:
        if marker in after:
            after = after.split(marker, 1)[0]
    return after.strip() or None


class MockProvider(LLMProvider):
    """A pure-Python, no-network 'LLM' for dev / tests."""

    name = "mock"

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        json_mode: bool = False,
        **kwargs: Any,
    ) -> LLMResponse:
        start = time.perf_counter()
        system = next((m for m in messages if m.role == "system"), None)
        last_user = next(
            (m for m in reversed(messages) if m.role == "user"), None
        )

        # Hint for json_mode shape selection — cheap string match on the
        # opening line of the system prompt.
        role_hint = "optimizer"
        if system and system.content:
            head = system.content.strip().lower()[:120]
            if head.startswith("you are the prompt analyst"):
                role_hint = "analyst"
            elif head.startswith("you are the prompt optimizer"):
                role_hint = "optimizer"
            elif head.startswith("you are the evaluation explainer"):
                role_hint = "explainer"
        self._system_role_hint = role_hint  # used by _rewrite

        original = (last_user.content if last_user else "") or (
            system.content if system else ""
        )

        text = self._rewrite(original, json_mode=json_mode)

        # Token estimate: ~4 chars per token.
        in_tok = sum(len(m.content) for m in messages) // 4
        out_tok = max(1, len(text) // 4)
        elapsed = int((time.perf_counter() - start) * 1000) + 1

        return LLMResponse(
            text=text,
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_ms=elapsed,
            provider=self.name,
            model=model or "mock-rewriter",
        )

    # ---------- internals ----------

    def _rewrite(self, original: str, *, json_mode: bool) -> str:
        """Apply a deterministic transformation that reads as an improvement.

        Rules applied (in order):
        1. If the prompt lacks a clear role statement, prepend one.
        2. If it lacks explicit output format guidance, append a structured
           output block.
        3. If it lacks constraint / guardrail language, append guardrails.
        4. Otherwise, lightly tighten wording and add an Examples section.

        When `json_mode` is true we additionally shape the output JSON to
        match what the calling node expects (analyst vs. optimizer). The
        caller is identified from the role hint set on the instance by
        `generate()`.
        """
        # Extract the actual prompt block from the calling template, so the
        # optimizer sees the user's prompt and not the surrounding template.
        target = _extract_original_block(original) or original

        if not target or not target.strip():
            target = "You are a helpful assistant."

        text = target.strip()
        added: list[str] = []
        lower = text.lower()

        if not _looks_like_system_prompt(text):
            added.append("# Role\nYou are a focused, reliable assistant.")

        if "format" not in lower and "json" not in lower:
            added.append(
                "# Output format\n"
                "Respond concisely. When a structured answer is requested, "
                "use JSON. Otherwise use plain prose."
            )

        if "guardrail" not in lower and "constraint" not in lower:
            added.append(
                "# Constraints\n"
                "- Do not invent facts.\n"
                "- If unsure, say so and ask one clarifying question.\n"
                "- Refuse unsafe requests and explain why briefly."
            )

        if "example" not in lower:
            added.append(
                "# Examples\n"
                "User: Summarize the attached spec in three bullets.\n"
                "Assistant: \n"
                "- Bullet one — main goal.\n"
                "- Bullet two — key constraint.\n"
                "- Bullet three — open question."
            )

        if added:
            improved = text + "\n\n" + "\n\n".join(added)
        else:
            improved = self._tighten(text)

        if json_mode:
            import json as _json
            role = getattr(self, "_system_role_hint", "optimizer")
            if role == "analyst":
                return _json.dumps(
                    {
                        "strengths": [
                            "Clear role statement"
                            if _looks_like_system_prompt(text)
                            else "Concise scope"
                        ],
                        "issues": (
                            []
                            if "constraint" in lower
                            else ["No explicit constraints / guardrails"]
                        ),
                        "optimization_opportunities": (
                            []
                            if "example" in lower
                            else ["Add a short Examples block"]
                        ),
                        "risk_level": "low",
                        "findings": [
                            {
                                "category": "missing_constraint",
                                "severity": "medium",
                                "description": "No explicit guardrails / refusal guidance.",
                                "suggestion": "Add a Constraints block.",
                            }
                        ],
                        "recommended_changes": [
                            "Add Constraints, Output format, Examples blocks."
                        ],
                    }
                )
            # optimizer
            return _json.dumps(
                {
                    "proposed_prompt": improved,
                    "changes": [
                        {
                            "type": "add",
                            "reason": "Added role / format / constraints / examples blocks.",
                            "expected_effect": "More deterministic, fewer ambiguities.",
                        }
                    ],
                    "risks": [],
                }
            )
        return improved

    @staticmethod
    def _tighten(text: str) -> str:
        # Conservative, regex-free tweaks — replace verbose phrases.
        replacements = {
            "in order to": "to",
            "due to the fact that": "because",
            "at this point in time": "now",
            "a large number of": "many",
            "in the event that": "if",
        }
        out = text
        for k, v in replacements.items():
            out = out.replace(k, v)
        if not out.endswith(("# Constraints", "# Role", "# Output format")):
            out += "\n\n# Notes\nKeep responses concise and verifiable."
        return out
