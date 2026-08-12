"""The wire shapes this module accepts and returns. OpenAI's, plus the `prope` object."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "ChatCompletionRequest",
    "ChatMessage",
    "PropeRequestOptions",
]


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow", protected_namespaces=())

    role: str
    content: Any = None


class PropeRequestOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    variables: dict[str, Any] = Field(default_factory=dict)


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow", protected_namespaces=())

    model: str
    messages: list[ChatMessage] = Field(min_length=1)
    stream: bool = False
    stream_options: dict[str, Any] | None = None
    prope: PropeRequestOptions | None = None

    def caller_messages(self) -> list[dict[str, Any]]:
        return [message.model_dump(exclude_none=True) for message in self.messages]

    def variables(self) -> dict[str, Any]:
        return dict(self.prope.variables) if self.prope is not None else {}

    def wants_usage(self) -> bool:
        options = self.stream_options or {}
        return bool(options.get("include_usage"))
