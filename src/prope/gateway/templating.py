"""A-078 / ADR-0011: `{{variable}}` placeholders, and the refusal when one is unfilled.

**The implementation moved to `prope.prompt_composition` and this module is now its
re-export.** Two callers compose a revision for dispatch — this gateway serving a
released revision, and prompt-registry's playground trying a draft — and the rule
has to be one rule. It could not stay here: an inland module importing from the
gateway is the edge the module map forbids `evaluation` to have, because the
gateway is the outermost surface and nothing behind it may depend on it.

The names below are unchanged and so is their behaviour. This file survives rather
than being deleted so that the gateway's own imports keep reading as gateway
imports, and so that `A-078` has somewhere in this module to point at.
"""

from prope.prompt_composition import (
    PLACEHOLDER,
    MissingVariable,
    UnfilledPlaceholder,
    render,
    required_variables,
)

__all__ = [
    "PLACEHOLDER",
    "MissingVariable",
    "UnfilledPlaceholder",
    "render",
    "required_variables",
]
