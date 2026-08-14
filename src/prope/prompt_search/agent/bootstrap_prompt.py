"""Seed a fresh Langfuse project with the extraction instruction. Run once.

    uv run python -m prope.prompt_search.agent.bootstrap_prompt

**This and `prompt_conversion.bootstrap_prompt` are the only two places in
`src/` allowed to pass a non-empty `labels`, and
`tests/unit/test_prompt_search_dspy.py` enforces it for this module.** The
exception is narrow and that is the whole reason it is safe: the text it labels
`production` is `FALLBACK_EXTRACTION_PROMPT`, which is the text the module would
have used anyway with no Langfuse at all. Labelling it releases nothing that was
not already running. `optimize.py`, which proposes text nobody has read,
publishes unlabelled and waits for a person.

Idempotence is Langfuse's: a second run creates the next version with the same
body and moves the label to it. Harmless, and visible in the version history —
better than this script guessing whether an existing version is "the same" one.
"""

from prope.app_agent.telemetry import get_langfuse
from prope.prompt_search.agent.prompting import (
    EXTRACTION_PROMPT_NAME,
    FALLBACK_EXTRACTION_PROMPT,
)


def main() -> None:
    langfuse = get_langfuse()
    if langfuse is None:
        raise RuntimeError(
            "Langfuse is not configured: set LANGFUSE_PUBLIC_KEY and "
            "LANGFUSE_SECRET_KEY (see .env.example)"
        )

    langfuse.create_prompt(
        name=EXTRACTION_PROMPT_NAME,
        type="text",
        prompt=FALLBACK_EXTRACTION_PROMPT,
        labels=["production"],
    )
    # The SDK batches on a background thread. Without this, a short-lived process
    # exits before the write leaves it and the prompt never appears.
    langfuse.flush()

    print(f"seeded {EXTRACTION_PROMPT_NAME} and labelled it `production`")


if __name__ == "__main__":
    main()
