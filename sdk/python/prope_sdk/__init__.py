"""Prope's Python SDK. **The request travels to the prompt, never the reverse.**

```python
from prope_sdk import Prope

prope = Prope(api_key="prope_key_...", base_url="https://prope.example.com")

answer = prope.chat(
    "support/refund-classifier",
    messages=[{"role": "user", "content": "Where is my refund?"}],
    variables={"tier": "gold"},
)
print(answer.text)
print(answer.version_id, answer.revision)   # what actually served it
```

ADR-0065 is the whole design in one rule: **there is no `get_prompt`.** No
method here returns prompt text, a template, or a revision body. The gateway
composes the system message from the released revision and dispatches it; this
package sends the caller's own messages and variables and nothing else.

That is not a missing feature. If prompt bodies travelled to the application,
three things would break at once: the charter's *never holds a copy of the
text*; `version_id` on a call record, which would become "this revision was
fetched at some point" rather than "this revision produced this call"; and
release control, since a template fetched once at boot outlives any withdrawal.

**The package is `prope_sdk`, not `prope`.** Prope's own service package is
`prope`, and the SDK's tests run against the real gateway app in one process
(ADR-0065) — two importable packages of the same name is a problem with no good
day. Customers who prefer the shorter name can `import prope_sdk as prope`.

What it does carry is context a gateway cannot infer: see
:class:`~prope_sdk.client.Conversation` for chains that thread themselves.
Local steps that are not LLM calls — a tool that raised, a retrieval that
returned nothing — are **not** in this version; their storage is OQ-154 and
shipping a method that silently dropped them would be worse than not having one.
"""

from ._wire import CHAT_PATH
from .client import (
    DEFAULT_TIMEOUT,
    AsyncConversation,
    AsyncPrope,
    Conversation,
    Prope,
    new_conversation_id,
)
from .errors import (
    AuthenticationError,
    CallerSystemMessage,
    GatewayUnavailable,
    InvalidRequest,
    MissingVariable,
    ModelNotFound,
    PropeError,
    RateLimited,
    UpstreamError,
)
from .types import Answer, Chunk, Usage

__version__ = "0.1.0"

__all__ = [
    "CHAT_PATH",
    "DEFAULT_TIMEOUT",
    "Answer",
    "AsyncConversation",
    "AsyncPrope",
    "AuthenticationError",
    "CallerSystemMessage",
    "Chunk",
    "Conversation",
    "GatewayUnavailable",
    "InvalidRequest",
    "MissingVariable",
    "ModelNotFound",
    "Prope",
    "PropeError",
    "RateLimited",
    "UpstreamError",
    "Usage",
    "__version__",
    "new_conversation_id",
]
