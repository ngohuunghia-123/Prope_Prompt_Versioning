"""The value objects the four seams are written in. No SQL, no FastAPI, no I/O."""

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

__all__ = [
    "Adapter",
    "CatalogueEntry",
    "CatalogueSource",
    "ConfigStatus",
    "CredentialRecord",
    "DispatchError",
    "DispatchResult",
    "ErrorClass",
    "Origin",
    "Priority",
    "ProviderConfig",
    "ProviderUnavailable",
    "Usage",
    "VerificationOutcome",
    "VerificationStatus",
]


class Adapter(StrEnum):
    OPENAI_COMPATIBLE = "openai_compatible"


class ConfigStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class VerificationStatus(StrEnum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"


class CatalogueSource(StrEnum):
    DISCOVERED = "discovered"
    MANUAL = "manual"


class Priority(StrEnum):
    INTERACTIVE = "interactive"
    BATCH = "batch"


class Origin(StrEnum):
    PROPE = "prope"
    PROVIDER = "provider"


class ErrorClass(StrEnum):
    RATE_LIMITED = "rate_limited"
    CREDENTIAL_REJECTED = "credential_rejected"
    MODEL_UNAVAILABLE = "model_unavailable"
    INVALID_REQUEST = "invalid_request"
    CONTENT_POLICY = "content_policy"
    UPSTREAM_UNAVAILABLE = "upstream_unavailable"
    UPSTREAM_TIMEOUT = "upstream_timeout"
    CONTRACT_VIOLATION = "contract_violation"
    BLOCKED_ADDRESS = "blocked_address"
    KEY_UNAVAILABLE = "key_unavailable"
    CONFIGURATION_UNUSABLE = "configuration_unusable"
    ADMISSION_REFUSED = "admission_refused"


class ProviderUnavailable(Exception):  # noqa: N818
    """A configuration that cannot serve a dispatch at all."""

    def __init__(self, error_class: ErrorClass, message: str) -> None:
        super().__init__(message)
        self.error_class = error_class


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    id: str
    workspace_id: str
    display_name: str
    adapter: Adapter
    base_url: str
    status: ConfigStatus
    verification_status: VerificationStatus
    interactive_concurrency: int
    batch_concurrency: int

    def concurrency_for(self, priority: Priority) -> int:
        if priority is Priority.INTERACTIVE:
            return self.interactive_concurrency
        return self.batch_concurrency


@dataclass(frozen=True, slots=True)
class CredentialRecord:
    """The stored envelope. Never the secret — `crypto.decrypt` produces that."""

    id: str
    provider_config_id: str
    ciphertext: str = field(repr=False)
    nonce: str = field(repr=False)
    wrapped_dek: str = field(repr=False)
    kek_version: int
    last_four: str


@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None

    @property
    def reported(self) -> bool:
        return self.input_tokens is not None or self.output_tokens is not None


@dataclass(frozen=True, slots=True)
class CatalogueEntry:
    model_id: str
    display_name: str | None
    supports_streaming: bool
    available: bool
    source: CatalogueSource
    #: What the provider itself listed the model at, on the ledger's per-1k
    #: unit, when its catalogue publishes prices at all (OpenRouter does,
    #: OpenAI and Gemini do not). Discovery metadata only — the ledger stays
    #: the only writer of adoptable prices.
    input_price_per_1k: float | None = None
    output_price_per_1k: float | None = None


@dataclass(frozen=True, slots=True)
class DispatchError:
    error_class: ErrorClass
    origin: Origin
    fallback_eligible: bool
    retryable: bool
    message: str
    #: What the provider itself said, verbatim, when its body carried an
    #: ``error.message`` — the sentence a person needs to read (a rate-limit
    #: window, a rejected parameter) that a class name cannot stand in for.
    #:
    #: **Excluded from ``repr`` and never logged (T-026).** A provider that
    #: echoes its request back inside the message is the ordinary way a prompt
    #: body reaches a log file, so this field exists for exactly one consumer:
    #: the tenant-scoped case-result row the workspace's own UI renders. It
    #: must not cross into a log, a metric label, or an observation payload.
    provider_message: str | None = field(default=None, repr=False)
    upstream_status: int | None = None
    provider_code: str | None = None
    provider_type: str | None = None
    usage: Usage | None = None

    @property
    def failed(self) -> bool:
        return True


@dataclass(slots=True)
class DispatchResult:
    response: Mapping[str, Any] | None = None
    usage: Usage | None = None
    stream: AsyncIterator[Any] | None = None
    upstream_duration_ms: float = 0.0
    error: DispatchError | None = None
    attempt: int = 1

    @property
    def failed(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class VerificationOutcome:
    passed: bool
    reason: str | None
    detail: str | None
    checked_at: datetime
