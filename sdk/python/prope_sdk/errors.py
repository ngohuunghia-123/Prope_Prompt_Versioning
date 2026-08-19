"""What the gateway refused with, as exceptions a caller can branch on.

Every error carries the machine ``code`` from the envelope rather than a message
somebody parses. ADR-0053 makes the code the stable thing and the message the
translated thing, so a caller that branches on text is a caller that breaks the
day the interface language changes.

**Nothing here is retried and nothing here is swallowed.** ADR-0065: a
convenience layer that quietly answers when the governed path is unavailable is
a way for an ungoverned answer to reach production, which is the one outcome
Prope exists to prevent. The SDK raises; the application decides.
"""

from __future__ import annotations

__all__ = [
    "AuthenticationError",
    "CallerSystemMessage",
    "GatewayUnavailable",
    "InvalidRequest",
    "MissingVariable",
    "ModelNotFound",
    "PropeError",
    "RateLimited",
    "UpstreamError",
]


class PropeError(Exception):
    """Base for everything this package raises.

    ``code`` is the gateway's machine code (``model_not_found``,
    ``missing_variable``, ...). ``status`` is the HTTP status. ``param`` names
    the offending field when the gateway identified one.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status: int | None = None,
        param: str | None = None,
        error_type: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status
        self.param = param
        self.error_type = error_type

    def __str__(self) -> str:
        return f"{self.code}: {self.message}" if self.code else self.message


class AuthenticationError(PropeError):
    """401. The key is absent, malformed, unknown, or revoked.

    **Four facts, one exception, deliberately.** ADR-0021 makes the gateway
    answer all four identically so a probe learns nothing from the difference,
    and an SDK that split them apart would reconstruct the oracle the gateway
    declines to be.
    """


class ModelNotFound(PropeError):
    """404. **Says less than it appears to, and that is the design.**

    Byte-identical (A-116) whether the prompt does not exist, exists but has no
    release, exists but this key is not scoped to it, or exists and is pinned to
    a revision that was never approved. Do not write code that infers which.

    In practice the first thing to check is the key's scope, because that is the
    one a person controls without a release.
    """


class InvalidRequest(PropeError):
    """400. The request was refused before anything reached a provider."""


class MissingVariable(InvalidRequest):
    """400 ``missing_variable``. The revision has a placeholder nothing filled.

    ``name`` is the variable the gateway named, parsed out of ``param`` so the
    caller does not have to. A revision can add a placeholder after a caller
    shipped, so this is a runtime condition rather than a programming error.
    """

    @property
    def name(self) -> str | None:
        if not self.param:
            return None
        _, _, name = self.param.partition("prope.variables.")
        return name or None


class CallerSystemMessage(InvalidRequest):
    """400 ``system_message_not_allowed``. A ``system`` message was sent.

    Raised **locally, before the request leaves**, because it is the single most
    likely mistake in a migrated call site: the literal that used to be the
    system prompt is still being passed. The released revision carries the
    system prompt; that is the whole point of the migration.
    """


class RateLimited(PropeError):
    """429. Too many concurrent requests for this key.

    ``retry_after`` is the gateway's own hint in seconds when it sent one. The
    SDK does not act on it — see the module docstring.
    """

    def __init__(self, message: str, *, retry_after: float | None = None, **kwargs: object) -> None:
        super().__init__(message, **kwargs)  # type: ignore[arg-type]
        self.retry_after = retry_after


class UpstreamError(PropeError):
    """502/503/504. The provider failed, timed out, or refused.

    The call was governed correctly and the model did not answer. Distinct from
    :class:`GatewayUnavailable` because this one means Prope worked.
    """


class GatewayUnavailable(PropeError):
    """The gateway could not be reached at all: DNS, connect, TLS, read timeout.

    No ``status`` and no ``code``, because nothing answered. This is the failure
    an application most needs to handle deliberately, and the reason the SDK
    ships no silent fallback: the honest options are to fail the request or to
    degrade in a way only the application can choose.
    """
