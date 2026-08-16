"""ADR-0011's composition: the revision's body is the system message, and the only one.

**The implementation moved to `prope.prompt_composition` and this module is now its
re-export**, for the reason written at the top of `templating.py`: prompt-registry's
playground composes a draft revision the same way this gateway composes a released
one, and an inland module may not import from the gateway to do it.

Unchanged names, unchanged behaviour, unchanged limit.
"""

from prope.prompt_composition import (
    MAX_COMPOSED_BYTES,
    SYSTEM_ROLE,
    CallerSystemMessage,
    OversizeRequest,
    compose,
    composed_size,
    refuse_caller_system_message,
)

__all__ = [
    "MAX_COMPOSED_BYTES",
    "SYSTEM_ROLE",
    "CallerSystemMessage",
    "OversizeRequest",
    "compose",
    "composed_size",
    "refuse_caller_system_message",
]
