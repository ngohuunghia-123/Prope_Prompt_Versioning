"""The value objects the gateway is written in. No SQL, no FastAPI, no I/O.

The response-shape constants and the two latency sums live here for a structural
reason rather than a tidy one: `routes.py` serves the resolved path and
`observe.py` serves the forwarded one, `routes.py` imports `observe.py`, and both
have to answer with the same SSE framing and measure added latency the same way.
The only place both can import is below both.
"""

import json
import time
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from prope.prompt_registry.domain import ModelName, ModelNameInvalid

__all__ = [
    "CALL_ID_PREFIX",
    "CHATCMPL_PREFIX",
    "DONE",
    "MissReason",
    "ModelReference",
    "ModelReferenceConflict",
    "ModelReferenceInvalid",
    "PIN_SEPARATOR",
    "STREAM_HEADERS",
    "ServedIdentity",
    "Stage",
    "added_latency_ms",
    "elapsed_ms",
    "parse_model_reference",
    "pinned_at",
    "sse",
]

CALL_ID_PREFIX = "cal_"

#: What the gateway prepends to a `call_id` on the way out, because OpenAI's
#: clients expect a `chatcmpl-` id and some of them assert on it. It lives here
#: rather than in `schemas.py` because both sides of the wire need it and
#: `schemas.py` already imports this module — the other direction would be a
#: cycle. `schemas.CHATCMPL_PREFIX` re-exports it.
CHATCMPL_PREFIX = "chatcmpl-"

PIN_SEPARATOR = "@"

#: The terminator every `text/event-stream` this gateway writes ends with,
#: including the one-chunk fallback stream and the forwarded stream. OpenAI's
#: clients treat its absence as a connection that dropped mid-answer.
DONE = "data: [DONE]\n\n"

#: Told to every intermediary: **do not hold this response.**
#:
#: A `text/event-stream` is the one response shape whose value is in its timing —
#: INT-022's chunks are useful as they arrive and worthless as a batch. Any CDN or
#: reverse proxy between the gateway and the consumer will happily buffer it into
#: a single write unless told otherwise, and the failure that produces is a lie
#: rather than an error: the whole answer lands at once, the consumer reports no
#: fault, and it reads as a slow model. Nothing in Prope's logs disagrees, because
#: from here the stream went out chunk by chunk.
#:
#: `no-transform` is the directive with teeth. It forbids an intermediary from
#: altering the payload at all — Cloudflare documents it as what disables edge
#: compression and Polish, and compression is the mechanism that buffers, because
#: a compressor cannot emit until it has something to compress. `no-cache` is
#: belt and braces for a response that must never be replayed to a second caller,
#: and `x-accel-buffering: no` is nginx's own switch, which several proxies now
#: honour by convention.
#:
#: Costs nothing when no proxy is in the path, which is why it is unconditional
#: rather than a deployment setting: the gateway does not know what is downstream
#: of it, and a consumer behind their own corporate proxy is not visible here at
#: all.
STREAM_HEADERS = {
    "cache-control": "no-cache, no-transform",
    "x-accel-buffering": "no",
}


class MissReason(StrEnum):
    UNKNOWN_MODEL = "unknown_model"
    NO_RELEASE = "no_release"
    NOT_PERMITTED = "not_permitted"
    PIN_NOT_FOUND = "pin_not_found"
    PIN_NOT_APPROVED = "pin_not_approved"


class Stage(StrEnum):
    PRE_FIRST_BYTE = "pre_first_byte"
    MID_STREAM = "mid_stream"


class ModelReferenceInvalid(ValueError):  # noqa: N818
    def __init__(self, raw: str, detail: str) -> None:
        super().__init__(detail)
        self.raw = raw
        self.detail = detail


class ModelReferenceConflict(ValueError):  # noqa: N818
    """Both spellings of the pin arrived, and they name different revisions.

    Not resolved by precedence. Either order — model name wins, body wins — is a
    rule the caller has to know to predict what they will be served, and the one
    thing a version pin exists to give them is knowing exactly that. A request
    that asks for two revisions is a mistake in the calling code, and it is worth
    more to the integrator as a 400 naming both than as a silently-chosen one.
    """

    def __init__(self, pin: str, version: str) -> None:
        super().__init__(f"the model name pins {pin!r} and prope.version asks for {version!r}")
        self.pin = pin
        self.version = version


@dataclass(frozen=True, slots=True)
class ModelReference:
    raw: str
    name: ModelName
    pin: str | None

    @property
    def pinned(self) -> bool:
        return self.pin is not None

    @property
    def model_name(self) -> str:
        return str(self.name)


def parse_model_reference(raw: str) -> ModelReference:
    if not isinstance(raw, str) or not raw:
        raise ModelReferenceInvalid(str(raw), "the model field is empty")

    head, separator, pin = raw.partition(PIN_SEPARATOR)
    if separator and not pin:
        raise ModelReferenceInvalid(raw, "the pin after '@' is empty")
    if PIN_SEPARATOR in pin:
        raise ModelReferenceInvalid(raw, "a model name carries at most one '@'")

    try:
        name = ModelName.parse(head)
    except ModelNameInvalid as invalid:
        raise ModelReferenceInvalid(raw, str(invalid)) from invalid

    return ModelReference(raw=raw, name=name, pin=pin or None)


def pinned_at(reference: ModelReference, version: str | None) -> ModelReference:
    """Fold ``prope.version`` into a reference parsed from the model name.

    Two spellings of one idea, and they resolve through the same column
    comparison one module over: ``name@2`` has been A-022's since the gateway
    shipped, and ``prope.version`` is the form an OpenAI-shaped client can send
    without building the model string by hand — which matters because a typed SDK
    holds the model name in configuration and the version in the call.

    So the pin is folded here, at the edge, and everything downstream of this
    function is unchanged: one ``ModelReference``, one cache key, one refusal
    shape. A version that names no approved revision is the same byte-identical
    404 that ``@`` has always produced (A-116), because it is literally the same
    lookup.

    ``raw`` deliberately does not grow the version. It is what the response
    echoes as ``model`` and what a not-found names, and both must be the string
    the caller actually sent. ``pinned`` still tells the truth either way, so the
    response header, the ledger row and
    ``prope_gateway_pinned_call_total`` count a body-pinned call exactly as they
    count an ``@``-pinned one — which is the property that keeps the
    restore-blindness signal honest as integrations move to the new spelling.
    """
    if version is None or version == reference.pin:
        return reference
    if reference.pinned:
        raise ModelReferenceConflict(str(reference.pin), version)
    return replace(reference, pin=version)


@dataclass(frozen=True, slots=True)
class ServedIdentity:
    model_name: str
    version_id: str
    revision_number: int
    pinned: bool
    fallback: bool
    upstream_model: str | None
    #: The id of *this* call, which is the one thing on the response a caller
    #: cannot obtain any other way. Without it `prope.parent_call_id` is a field
    #: nobody can populate: the graph is threaded by naming the call a call
    #: followed from, and only the gateway knows what that call was called.
    call_id: str
    #: ADR-0069. Which rung of the revision's route answered, 1-based, and how
    #: many were dispatched to before one did.
    #:
    #: **`upstream_model` above must be read off the rung that SERVED**, not off
    #: the binding. It is the same field it has always been and it still means
    #: *the model that produced this answer*; a routed response built from the
    #: binding would name the primary whichever rung actually replied, which is a
    #: quieter lie than shipping no marker at all.
    route_combo_id: str | None = None
    route_entry: int | None = None
    route_attempts: int = 1

    def completion_id(self) -> str:
        """The `id` every response carries — the call id in OpenAI's clothing.

        The provider sends an id of its own and it is **overwritten**, not
        passed through. Two reasons. It is the caller's only handle on the row
        Prope recorded, and a response whose id names a third party's record
        rather than ours is a traceability claim that stops at the boundary.
        And the fallback path has always answered with this shape
        (`_completion`), so passing the upstream id through on the ordinary path
        made the same field mean two different things depending on whether the
        provider happened to be up.
        """
        return f"{CHATCMPL_PREFIX}{self.call_id}"

    def headers(self) -> dict[str, str]:
        headers = {
            "x-prope-model": self.model_name,
            "x-prope-version-id": self.version_id,
            "x-prope-revision": str(self.revision_number),
            "x-prope-pinned": _flag(self.pinned),
            # Bare, where the body's `id` is prefixed. This is the form that
            # appears in Prope's own screens and logs, so it is the form somebody
            # pastes into a search box; `PropeRequestOptions` accepts either,
            # which is what makes shipping both harmless rather than a choice the
            # integrator has to get right.
            "x-prope-call-id": self.call_id,
        }
        if self.fallback:
            headers["x-prope-fallback"] = _flag(True)
        # Only when the revision actually routes, following `x-prope-fallback`'s
        # precedent: a header that appears only when it has something to say.
        # Their ABSENCE is then meaningful too — this call went to the one
        # provider the revision binds, and nothing failed over.
        if self.route_entry is not None:
            headers["x-prope-route-entry"] = str(self.route_entry)
            headers["x-prope-route-attempts"] = str(self.route_attempts)
        return headers

    def body(self) -> dict[str, Any]:
        # The three route keys are ALWAYS present, where the headers are not, and
        # the asymmetry is deliberate. A header is a lookup by name and an absent
        # one costs a caller nothing; a body is destructured, and a key that
        # appears only sometimes is the shape a client gets wrong once and then
        # guards forever. `null` and `1` say *this call was not routed* just as
        # clearly, in a shape that never changes.
        return {
            "version_id": self.version_id,
            "revision_number": self.revision_number,
            "pinned": self.pinned,
            "fallback": self.fallback,
            "upstream_model": self.upstream_model,
            "route_combo_id": self.route_combo_id,
            "route_entry": self.route_entry,
            "route_attempts": self.route_attempts,
        }

    def stamp(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        stamped = dict(payload)
        stamped["id"] = self.completion_id()
        stamped["model"] = self.model_name
        stamped["prope"] = self.body()
        return stamped


def _flag(value: bool) -> str:
    return "true" if value else "false"


def sse(payload: Mapping[str, Any]) -> str:
    """One `text/event-stream` frame. `ensure_ascii=False` because the content is
    prose in whatever language the caller writes, and escaping it would triple the
    bytes on the wire for a Vietnamese answer (ADR-0053)."""
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


def elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def added_latency_ms(started: float, upstream_ms: float) -> int:
    """What Prope cost, as opposed to what the provider cost.

    Floored at zero rather than allowed negative: the two clocks are the same
    clock, but `upstream_ms` is measured inside provider-access around a span this
    one encloses, and a rounding disagreement of a millisecond must not produce a
    negative latency in a histogram somebody reads as a percentile.
    """
    return max(0, elapsed_ms(started) - int(upstream_ms))
