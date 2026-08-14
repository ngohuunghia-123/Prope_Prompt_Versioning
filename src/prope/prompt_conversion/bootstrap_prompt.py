"""Seed a fresh Langfuse project with the conversion instruction. Run once.

    uv run python -m prope.prompt_conversion.bootstrap_prompt

**This is the only place in `src/` allowed to pass a non-empty `labels`, and
`tests/unit/test_prompt_conversion_dspy.py` enforces that.** The exception is
narrow and is the whole reason it is safe: the text it labels `production` is
`FALLBACK_SYSTEM_PROMPT`, which is the text the module would have used anyway
with no Langfuse at all. Labelling it releases nothing that was not already
running. `optimize.py`, which proposes text nobody has read, publishes
unlabelled and waits for a person.

Idempotence is Langfuse's: a second run creates version 2 with the same body and
moves the label to it. Harmless, and visible in the version history — which is
better than this script guessing whether an existing version is "the same" one.
"""

from prope.prompt_conversion.prompting import (
    CONVERSION_PROMPT_NAME,
    FALLBACK_SYSTEM_PROMPT,
)
from prope.prompt_conversion.telemetry import get_langfuse


def main() -> None:
    langfuse = get_langfuse()
    if langfuse is None:
        raise RuntimeError(
            "Langfuse is not configured: set LANGFUSE_PUBLIC_KEY and "
            "LANGFUSE_SECRET_KEY (see .env.example)"
        )

    langfuse.create_prompt(
        name=CONVERSION_PROMPT_NAME,
        type="text",
        prompt=FALLBACK_SYSTEM_PROMPT,
        labels=["production"],
    )
    # The SDK batches in a background thread. Without this, a short-lived
    # process exits before the write leaves it and the prompt never appears.
    langfuse.flush()

    print(f"seeded {CONVERSION_PROMPT_NAME} and labelled it `production`")


if __name__ == "__main__":
    main()
