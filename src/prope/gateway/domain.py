"""The value objects the gateway is written in. No SQL, no FastAPI, no I/O."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from prope.prompt_registry.domain import ModelName, ModelNameInvalid

__all__ = [
    "CALL_ID_PREFIX",
    "CHATCMPL_PREFIX",
    "MissReason",
    "ModelReference",
    "ModelReferenceInvalid",
    "PIN_SEPARATOR",
    "ServedIdentity",
    "Stage",
    "parse_model_reference",
]

CALL_ID_PREFIX = "cal_"

#: What the gateway prepends to a `call_id` on the way out, because OpenAI's
#: clients expect a `chatcmpl-` id and some of them assert on it. It lives here
#: rather than in `schemas.py` because both sides of the wire need it and
#: `schemas.py` already imports this module — the other direction would be a
#: cycle. `schemas.CHATCMPL_PREFIX` re-exports it.
CHATCMPL_PREFIX = "chatcmpl-"

PIN_SEPARATOR = "@"


class MissReason(StrEnum):
    UNKNOWN_MODEL = "unknown_model"
    NO_RELEASE = "no_release"
    NOT_PERMITTED = "not_permitted"
    PIN_NOT_FOUND = "pin_not_found"
    PIN_NOT_APPROVED = "pin_not_approved"


class Stage(StrEnum):
    PRE_FIRST_BYTE = "pre_first_byte"
    MID_STREAM = "mid_stream"


class ModelReferenceInvalid(ValueError):
    def __init__(self, raw: str, detail: str) -> None:
        super().__init__(detail)
        self.raw = raw
        self.detail = detail


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
        return headers

    def body(self) -> dict[str, Any]:
        return {
            "version_id": self.version_id,
            "revision_number": self.revision_number,
            "pinned": self.pinned,
            "fallback": self.fallback,
            "upstream_model": self.upstream_model,
        }

    def stamp(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        stamped = dict(payload)
        stamped["id"] = self.completion_id()
        stamped["model"] = self.model_name
        stamped["prope"] = self.body()
        return stamped


def _flag(value: bool) -> str:
    return "true" if value else "false"
