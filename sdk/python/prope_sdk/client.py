"""The two transports and the chain helper. Everything decided lives in `_wire`.

`Prope` and `AsyncPrope` are deliberately near-identical: they differ in `await`
and nothing else. That duplication is chosen over a shared base with hooks,
because the alternative hides the one thing a reader of an SDK needs to see
immediately — the request that is actually made.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
from types import TracebackType
from typing import Any

import httpx

from . import _wire
from .errors import GatewayUnavailable, PropeError
from .types import Answer, Chunk

__all__ = ["AsyncConversation", "AsyncPrope", "Conversation", "Prope"]

DEFAULT_TIMEOUT = 60.0

#: The gateway's own rule (`CONVERSATION_ID_PATTERN`, `CONVERSATION_ID_MAX_LENGTH`).
#: Checked locally so a caller-supplied id fails where it was chosen rather than
#: as a 422 from a request they have to go and read.
_CONVERSATION_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

_USER_AGENT = "prope-sdk-python/0.1.0"


def new_conversation_id() -> str:
    """A fresh correlation id. Prope never generates one, so the SDK does.

    ADR-0058: the conversation is the **caller's** name for a chain and Prope
    attaches no meaning to it. An application that already has a session or
    thread id should pass that instead — a graph keyed by something the
    application can look up is worth more than one keyed by a value only Prope
    has ever seen.
    """
    return uuid.uuid4().hex


def _check_conversation_id(value: str) -> str:
    if not _CONVERSATION_ID.match(value):
        raise ValueError(
            "conversation_id must be 1-64 characters of A-Za-z0-9_- "
            f"(got {value!r}). Prope stores it verbatim, so it has to be safe "
            "to put in a URL and a log line."
        )
    return value


def _headers(api_key: str) -> dict[str, str]:
    return {
        "authorization": f"Bearer {api_key}",
        "content-type": "application/json",
        "user-agent": _USER_AGENT,
    }


def _payload(response: httpx.Response) -> Mapping[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, Mapping) else {}


def _streamed_ok(response: httpx.Response) -> bool:
    """True when the response really is an event stream.

    A refusal arrives before the first byte as ordinary JSON, so a client that
    assumed SSE from the request would parse an error body as a stream and
    report nothing at all.
    """
    return response.status_code < 400 and "event-stream" in response.headers.get("content-type", "")


class _Base:
    def __init__(self, api_key: str, base_url: str, *, timeout: float = DEFAULT_TIMEOUT) -> None:
        if not api_key:
            raise ValueError("api_key is required. Mint one in Prope under Workspace > API keys.")
        if not base_url:
            raise ValueError("base_url is required, for example https://prope.example.com")
        self.api_key = api_key
        #: Origin only. The path is INT-022's and the SDK owns it, so a base URL
        #: that already ends in `/v1` would produce `/v1/v1/chat/completions` —
        #: the most common configuration mistake in every OpenAI-compatible
        #: client, and one worth normalising away rather than diagnosing.
        self.base_url = base_url.rstrip("/").removesuffix("/v1")
        self.timeout = timeout

    def _request(
        self,
        prompt: str,
        messages: Sequence[Mapping[str, Any]],
        variables: Mapping[str, Any] | None,
        pin: str | None,
        stream: bool,
        conversation_id: str | None,
        parent_call_id: str | None,
        extra: Mapping[str, Any],
    ) -> dict[str, Any]:
        _wire.check_messages(messages)
        if conversation_id is not None:
            _check_conversation_id(conversation_id)
        return _wire.build_body(
            prompt=prompt,
            messages=messages,
            variables=variables,
            pin=pin,
            stream=stream,
            conversation_id=conversation_id,
            parent_call_id=parent_call_id,
            extra=extra,
        )


class Prope(_Base):
    """A synchronous Prope client.

    ```python
    prope = Prope(api_key="prope_key_...", base_url="https://prope.example.com")
    answer = prope.chat("support/refund-classifier",
                        messages=[{"role": "user", "content": "Where is my refund?"}])
    print(answer.text, answer.version_id)
    ```

    **There is no `get_prompt`.** ADR-0065: the request travels to the prompt,
    never the prompt to the request. A consumer key cannot read a prompt body
    through this package, by design rather than by omission.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(api_key, base_url, timeout=timeout)
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout)

    def chat(
        self,
        prompt: str,
        *,
        messages: Sequence[Mapping[str, Any]],
        variables: Mapping[str, Any] | None = None,
        pin: str | None = None,
        conversation_id: str | None = None,
        parent_call_id: str | None = None,
        **extra: Any,
    ) -> Answer:
        """One governed call. `prompt` is `namespace/name`, never a provider model."""
        body = self._request(
            prompt, messages, variables, pin, False, conversation_id, parent_call_id, extra
        )
        try:
            response = self._client.post(
                self.base_url + _wire.CHAT_PATH, json=body, headers=_headers(self.api_key)
            )
        except httpx.HTTPError as unreachable:
            raise GatewayUnavailable(f"Could not reach the Prope gateway: {unreachable}") from unreachable

        _wire.raise_for(response.status_code, _payload(response), response.headers)
        answer = _wire.answer_from(_payload(response), response.headers)
        if conversation_id:
            answer = _replace_conversation(answer, conversation_id)
        return answer

    def stream(
        self,
        prompt: str,
        *,
        messages: Sequence[Mapping[str, Any]],
        variables: Mapping[str, Any] | None = None,
        pin: str | None = None,
        conversation_id: str | None = None,
        parent_call_id: str | None = None,
        **extra: Any,
    ) -> Iterator[Chunk]:
        """The same call, delta by delta. Concatenating every `chunk.text` is the answer."""
        body = self._request(
            prompt, messages, variables, pin, True, conversation_id, parent_call_id, extra
        )
        try:
            with self._client.stream(
                "POST", self.base_url + _wire.CHAT_PATH, json=body, headers=_headers(self.api_key)
            ) as response:
                if not _streamed_ok(response):
                    response.read()
                    _wire.raise_for(response.status_code, _payload(response), response.headers)
                    raise PropeError("The gateway answered a stream request with no stream.")
                for payload in _wire.sse_payloads(response.iter_lines()):
                    yield _wire.chunk_from(payload)
        except httpx.HTTPError as unreachable:
            raise GatewayUnavailable(f"Could not reach the Prope gateway: {unreachable}") from unreachable

    def models(self) -> list[str]:
        """Every released prompt this key may resolve — INT-010, its scope made visible.

        Both scopes, unioned by the gateway (ADR-0061): names granted directly
        and every released prompt in a granted folder. An empty list means the
        key resolves nothing, which is a scope problem rather than a release one.
        """
        try:
            response = self._client.get(
                self.base_url + "/v1/models", headers=_headers(self.api_key)
            )
        except httpx.HTTPError as unreachable:
            raise GatewayUnavailable(f"Could not reach the Prope gateway: {unreachable}") from unreachable
        _wire.raise_for(response.status_code, _payload(response), response.headers)
        return [str(row.get("id")) for row in _payload(response).get("data") or ()]

    def conversation(self, conversation_id: str | None = None) -> Conversation:
        """A chain whose steps thread themselves. See :class:`Conversation`."""
        return Conversation(self, conversation_id or new_conversation_id())

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Prope:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class Conversation:
    """A chain of calls that thread themselves into one conversation graph.

    ```python
    with prope.conversation() as chain:
        plan = chain.chat("support/planner", messages=[...])
        answer = chain.chat("support/answer", messages=[...])
    ```

    Each step sends `prope.conversation_id` and names the step before it as
    `prope.parent_call_id`. Doing that by hand is correct and tedious — the
    playground's agent mode threads six calls and every one of them is a place
    to get it wrong — and a chain assembled here is **correct by construction**,
    which is what makes the graph worth reading.

    Not thread-safe, and not meant to be: a conversation is one end-user's
    exchange, and two threads appending to one chain are two chains.
    """

    def __init__(self, client: Prope, conversation_id: str) -> None:
        self.client = client
        self.conversation_id = _check_conversation_id(conversation_id)
        #: The call the next step will name as its parent. `None` makes the next
        #: step a root, which is what the first one is.
        self.last_call_id: str | None = None

    def chat(self, prompt: str, **kwargs: Any) -> Answer:
        answer = self.client.chat(
            prompt,
            conversation_id=self.conversation_id,
            parent_call_id=self.last_call_id,
            **kwargs,
        )
        if answer.call_id:
            self.last_call_id = answer.call_id
        return answer

    def stream(self, prompt: str, **kwargs: Any) -> Iterator[Chunk]:
        parent = self.last_call_id
        for chunk in self.client.stream(
            prompt, conversation_id=self.conversation_id, parent_call_id=parent, **kwargs
        ):
            # The id arrives mid-stream rather than up front, so the chain
            # advances as soon as it is known — a step whose stream the caller
            # abandons still parents the next one correctly.
            if chunk.call_id:
                self.last_call_id = chunk.call_id
            yield chunk

    def branch(self) -> Conversation:
        """A second chain from this point, sharing the conversation.

        For a fan-out — three critics on one draft — where each branch should
        name the same parent rather than each other.
        """
        child = Conversation(self.client, self.conversation_id)
        child.last_call_id = self.last_call_id
        return child

    def __enter__(self) -> Conversation:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None


class AsyncPrope(_Base):
    """The same client for an `asyncio` application. Identical surface, awaited."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(api_key, base_url, timeout=timeout)
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def chat(
        self,
        prompt: str,
        *,
        messages: Sequence[Mapping[str, Any]],
        variables: Mapping[str, Any] | None = None,
        pin: str | None = None,
        conversation_id: str | None = None,
        parent_call_id: str | None = None,
        **extra: Any,
    ) -> Answer:
        body = self._request(
            prompt, messages, variables, pin, False, conversation_id, parent_call_id, extra
        )
        try:
            response = await self._client.post(
                self.base_url + _wire.CHAT_PATH, json=body, headers=_headers(self.api_key)
            )
        except httpx.HTTPError as unreachable:
            raise GatewayUnavailable(f"Could not reach the Prope gateway: {unreachable}") from unreachable

        _wire.raise_for(response.status_code, _payload(response), response.headers)
        answer = _wire.answer_from(_payload(response), response.headers)
        if conversation_id:
            answer = _replace_conversation(answer, conversation_id)
        return answer

    async def stream(
        self,
        prompt: str,
        *,
        messages: Sequence[Mapping[str, Any]],
        variables: Mapping[str, Any] | None = None,
        pin: str | None = None,
        conversation_id: str | None = None,
        parent_call_id: str | None = None,
        **extra: Any,
    ) -> AsyncIterator[Chunk]:
        body = self._request(
            prompt, messages, variables, pin, True, conversation_id, parent_call_id, extra
        )
        try:
            async with self._client.stream(
                "POST", self.base_url + _wire.CHAT_PATH, json=body, headers=_headers(self.api_key)
            ) as response:
                if not _streamed_ok(response):
                    await response.aread()
                    _wire.raise_for(response.status_code, _payload(response), response.headers)
                    raise PropeError("The gateway answered a stream request with no stream.")
                async for line in response.aiter_lines():
                    for payload in _wire.sse_payloads(iter([line])):
                        yield _wire.chunk_from(payload)
        except httpx.HTTPError as unreachable:
            raise GatewayUnavailable(f"Could not reach the Prope gateway: {unreachable}") from unreachable

    async def models(self) -> list[str]:
        try:
            response = await self._client.get(
                self.base_url + "/v1/models", headers=_headers(self.api_key)
            )
        except httpx.HTTPError as unreachable:
            raise GatewayUnavailable(f"Could not reach the Prope gateway: {unreachable}") from unreachable
        _wire.raise_for(response.status_code, _payload(response), response.headers)
        return [str(row.get("id")) for row in _payload(response).get("data") or ()]

    def conversation(self, conversation_id: str | None = None) -> AsyncConversation:
        return AsyncConversation(self, conversation_id or new_conversation_id())

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> AsyncPrope:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()


class AsyncConversation:
    """:class:`Conversation` for :class:`AsyncPrope`."""

    def __init__(self, client: AsyncPrope, conversation_id: str) -> None:
        self.client = client
        self.conversation_id = _check_conversation_id(conversation_id)
        self.last_call_id: str | None = None

    async def chat(self, prompt: str, **kwargs: Any) -> Answer:
        answer = await self.client.chat(
            prompt,
            conversation_id=self.conversation_id,
            parent_call_id=self.last_call_id,
            **kwargs,
        )
        if answer.call_id:
            self.last_call_id = answer.call_id
        return answer

    async def stream(self, prompt: str, **kwargs: Any) -> AsyncIterator[Chunk]:
        parent = self.last_call_id
        async for chunk in self.client.stream(
            prompt, conversation_id=self.conversation_id, parent_call_id=parent, **kwargs
        ):
            if chunk.call_id:
                self.last_call_id = chunk.call_id
            yield chunk

    def branch(self) -> AsyncConversation:
        child = AsyncConversation(self.client, self.conversation_id)
        child.last_call_id = self.last_call_id
        return child

    async def __aenter__(self) -> AsyncConversation:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


def _replace_conversation(answer: Answer, conversation_id: str) -> Answer:
    """`Answer` is frozen, so threading its conversation back on is a rebuild.

    The gateway does not echo `conversation_id`, and it should not — it is the
    caller's own value. Putting it on the result anyway means a caller logging
    one object logs everything needed to find the call again.
    """
    return Answer(
        text=answer.text,
        model=answer.model,
        call_id=answer.call_id,
        version_id=answer.version_id,
        revision=answer.revision,
        upstream_model=answer.upstream_model,
        pinned=answer.pinned,
        fallback=answer.fallback,
        usage=answer.usage,
        conversation_id=conversation_id,
        raw=answer.raw,
    )
