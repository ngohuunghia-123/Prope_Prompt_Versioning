"""Seed a fresh Langfuse project with both chat instructions. Run once.

    uv run python -m prope.chat_orchestrator.bootstrap_prompt

The third and last place in `src/` allowed to pass a non-empty `labels`, and the
exception is safe for the same narrow reason the other two give: the text it
labels `production` is the compiled-in fallback — the text the module would run
with no Langfuse at all. Labelling it releases nothing that was not already
running. Anything a person has not read publishes unlabelled and waits for them.

Two prompts rather than one, because the router and the responder are separately
promotable: tightening how the assistant *refuses* should not require re-reviewing
how it *routes*, and a single prompt would make every change to either a change
to both.

Idempotence is Langfuse's: a second run creates the next version with the same
body and moves the label to it. Harmless, and visible in the version history.
"""

from prope.app_agent.telemetry import get_langfuse
from prope.chat_orchestrator.prompting import (
    FALLBACK_RESPONDER_PROMPT,
    FALLBACK_ROUTER_PROMPT,
    RESPONDER_PROMPT_NAME,
    ROUTER_PROMPT_NAME,
)


def main() -> None:
    langfuse = get_langfuse()
    if langfuse is None:
        raise RuntimeError(
            "Langfuse is not configured: set LANGFUSE_PUBLIC_KEY and "
            "LANGFUSE_SECRET_KEY (see .env.example)"
        )

    for name, text in (
        (ROUTER_PROMPT_NAME, FALLBACK_ROUTER_PROMPT),
        (RESPONDER_PROMPT_NAME, FALLBACK_RESPONDER_PROMPT),
    ):
        langfuse.create_prompt(name=name, type="text", prompt=text, labels=["production"])
        print(f"seeded {name} and labelled it `production`")

    # The SDK batches on a background thread. Without this, a short-lived process
    # exits before the write leaves it and neither prompt ever appears.
    langfuse.flush()


if __name__ == "__main__":
    main()
