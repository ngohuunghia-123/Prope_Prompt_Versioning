"""A-045's one error envelope, and the closed set of machine codes it may carry.

**This file is OQ-021's answer, taken at the moment the question said it would
be.** ``prope.call_ledger.schemas.install_error_envelope`` shipped in Phase 2
with a docstring that named its own eviction date: *"when a second module mounts
routes, this function and ``prope.session_auth.ManagementRefusal`` move together
to wherever OQ-021's answer puts the shared surface."* Phase 7 is that second
module, and the move is not a tidy-up — it is forced. access-control may not
import ``prope.call_ledger``: ADR-0018 makes call-ledger a **sink**, a module
with no outbound edges *and no inbound ones from a feature module*, and an
``from prope.call_ledger.schemas import ErrorCode`` in access-control's routes
would be the first edge into it. The envelope had to leave that package before a
second router could exist.

**Why the codes are one enum for the whole product rather than one per module.**
ADR-0053 puts every user-facing string behind a keyed catalogue and makes the
client render the ``code`` and never the ``message``; the catalogue is keyed on
exactly these literals. A per-module enum would let two modules mint the same
code with two meanings, or — worse and likelier — mint a code the catalogue has
never seen, which renders as **nothing at all**, silently. One closed set is the
same shape ``prope.session_auth.ManagementAction`` already uses for the same
reason, and members are module-prefixed by convention wherever the code is not
genuinely global.

**``ManagementRefusal`` stays in ``prope.session_auth``.** OQ-021 expected the
two to move together and they do not need to: that module is already the shared,
module-neutral home for the session boundary, and the refusal is raised by
``require_session`` itself. Splitting the exception from its only unconditional
raiser to keep a sentence true would be tidying at the cost of a real dependency.

**Nothing here is call-ledger's, and nothing here is access-control's.** Both
modules import it; neither owns it. A module adding a refusal adds a member
below, prefixed with its own name unless the code is genuinely product-wide.
"""

from enum import StrEnum
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError
from ulid import ULID

from prope.session_auth import PASSWORD_CHANGE_REQUIRED as PASSWORD_CHANGE_REQUIRED_CODE
from prope.session_auth import SESSION_REQUIRED as SESSION_REQUIRED_CODE
from prope.session_auth import ManagementRefusal

log = structlog.get_logger(__name__)

__all__ = [
    "REQUEST_ID_PREFIX",
    "ApiError",
    "ErrorCode",
    "ErrorEnvelope",
    "install_error_envelope",
]


class ErrorCode(StrEnum):
    """The closed set of machine codes the envelope's ``code`` may carry.

    **A ``StrEnum`` and not a free string, because of ADR-0053.** The interface
    language is Vietnamese only, behind an i18n layer with a keyed catalogue and
    **no literal display strings** — the API returns a machine ``code`` and the
    client translates it. A route that invented a code would therefore render as
    nothing at all in the SPA, and it would do so silently. Closing the set here
    makes an unknown code impossible to produce rather than merely unlikely.

    ``prope.call_ledger.domain`` states the same rule for statuses at rest: a
    status that is stored or transmitted is a **fact**, not a label, and it stays
    literal ASCII wherever it travels.

    ``SESSION_REQUIRED`` takes its value from ``prope.session_auth`` rather than
    repeating the literal, so the refusal and the vocabulary cannot drift.

    **Grouping is by owning module and the prefixes are load-bearing.** Four
    members are genuinely product-wide and carry no prefix. Everything else names
    the module that raises it, so that two modules refusing for two different
    reasons cannot collide on one catalogue key — the same argument
    ``ManagementAction`` makes one file over.
    """

    # --- product-wide -----------------------------------------------------
    SESSION_REQUIRED = SESSION_REQUIRED_CODE
    NOT_FOUND = "not_found"
    VALIDATION_FAILED = "validation_failed"
    INTERNAL_ERROR = "internal_error"

    # --- call-ledger (INT-028) --------------------------------------------
    PRICE_EFFECTIVE_RANGE_AMBIGUOUS = "price_effective_range_ambiguous"
    PRICE_BOTH_PRICES_ARE_ZERO = "price_both_prices_are_zero"
    PRICE_IS_NEGATIVE = "price_is_negative"
    MONEY_SCALE_EXCEEDED = "money_scale_exceeded"
    SPEND_CEILING_LIMIT_IS_NEGATIVE = "spend_ceiling_limit_is_negative"
    SPEND_CEILING_LIMIT_NEEDS_CURRENCY = "spend_ceiling_limit_needs_currency"
    RETENTION_WINDOW_NOT_POSITIVE = "retention_window_not_positive"

    # --- access-control (INT-029) -----------------------------------------
    #: A-116's second shape. The actor can SEE the subject and may not act on it,
    #: so the refusal names the missing permission in ``details.permission``. Its
    #: counterpart is ``NOT_FOUND`` above, and which of the two a route answers is
    #: a security decision rather than an ergonomic one.
    PERMISSION_DENIED = "permission_denied"
    #: A-144 / ADR-0043. The one code the three login failures share — unknown
    #: email, wrong password, and rate-limited all render as this, because a
    #: distinguishable rate-limit response reintroduces the account-enumeration
    #: oracle the whole login path is shaped to close.
    AUTHENTICATION_FAILED = "authentication_failed"
    #: A-117. Refused because it would leave the workspace with zero Admins.
    LAST_ADMIN_CANNOT_BE_REMOVED = "last_admin_cannot_be_removed"
    #: ADR-0054 / A-151's pre-condition: the person still holds a membership, and
    #: the tombstone is the account-level act that FOLLOWS every removal.
    USER_STILL_HAS_MEMBERSHIP = "user_still_has_membership"
    #: The account exists and cannot authenticate or be acted on: ``status`` is
    #: ``tombstoned`` and nothing un-tombstones a row.
    USER_IS_TOMBSTONED = "user_is_tombstoned"
    #: A-110. An Admin added a person whose email is already in ``access.user``.
    #: Distinct from ``VALIDATION_FAILED`` because the body was well-formed.
    EMAIL_ALREADY_REGISTERED = "email_already_registered"
    #: The person is already a member of this workspace, or already holds the
    #: role, or already holds a grant at that level. A no-op the caller should see.
    ALREADY_EXISTS = "already_exists"
    #: A-110's forced first sign-in: ``must_change_password`` is set, so every
    #: route but sign-out and change-password refuses until it is cleared. Takes
    #: its value from ``prope.session_auth`` for ``SESSION_REQUIRED``'s reason —
    #: the module that raises a refusal owns its literal.
    PASSWORD_CHANGE_REQUIRED = PASSWORD_CHANGE_REQUIRED_CODE


class ApiError(BaseModel):
    """A-045's error object: ``{code, message, details?, request_id}``.

    ``code`` is what the client renders (ADR-0053). ``message`` is for the
    person reading a log or a test failure and is **English on purpose** — it is
    never displayed, so translating it would be translating something nobody
    sees. ``details`` carries structured values the caller already sent, so a
    client can point at the field that was wrong; it never carries a constraint
    name, a SQL fragment or a driver's words (T-02-34). ``request_id``
    is INT-024's requirement for a ``5xx``, and is filled for every refusal
    rather than only those, because a client reporting a ``422`` it did not
    expect is worth being able to find.
    """

    model_config = ConfigDict(extra="forbid")

    code: ErrorCode
    message: str
    details: dict[str, Any] | None = None
    request_id: str | None = None


class ErrorEnvelope(BaseModel):
    """The whole of A-045's error shape: ``{error: {...}}``. There is one.

    Every refusal from every management route in every module renders as this,
    including the ones FastAPI would otherwise answer with its own
    ``{"detail": ...}``. ``prope.app`` registers the handlers that make that
    true. The gateway is exempt and returns OpenAI-shaped errors (A-026,
    INT-022) — that exemption is the gateway's, in Phase 19, and nothing here.
    """

    model_config = ConfigDict(extra="forbid")

    error: ApiError


#: The prefix on a request identifier. Not a stored id, so it carries no lock
#: file row — it exists to join an envelope a client is holding to the log line
#: the refusal wrote, which is INT-024's reason for putting it in the envelope at
#: all.
REQUEST_ID_PREFIX = "req_"


def _envelope(
    status_code: int,
    code: ErrorCode,
    message: str,
    details: dict[str, Any] | None,
    event: str,
) -> JSONResponse:
    """One refusal, rendered once, logged once.

    The ``request_id`` is generated here and written to **both** the response and
    the log line, which is the whole of its usefulness: a client reporting a
    refusal it did not expect can be found in the log by a value it is holding.

    **The log line carries the code and the id and nothing else** (A-046). Not
    the message — which quotes the caller's own figures in some branches — not
    the details, not the path, not the cookie. ``code`` is a member of a closed
    ``StrEnum`` and ``event`` is fixed in source, so both are bounded by
    construction in the sense ADR-0030 requires of anything that is going to be
    aggregated.

    That rule is doing more work here than it did in Phase 2. ``details`` on an
    access-control refusal can carry a user id, an email a caller just typed, or
    the name of a permission; ``message`` on the login path is fixed text shared
    by three different failures precisely so it cannot distinguish them. Neither
    reaches this log line, and neither ever may.
    """
    request_id = f"{REQUEST_ID_PREFIX}{ULID()}"
    log.info(event, reason=str(code), request_id=request_id)
    envelope = ErrorEnvelope(error=ApiError(code=code, message=message, details=details, request_id=request_id))
    return JSONResponse(status_code=status_code, content=envelope.model_dump(mode="json"))


def install_error_envelope(application: FastAPI) -> None:
    """Make A-045's envelope the **only** error shape this application produces.

    Called by ``prope.app``'s factory and by nothing else in production. Every
    module that mounts routes relies on it, which is why it lives here rather
    than in any one of them — see the module docstring for OQ-021.

    Three handlers, and the second one is the one that earns this function's
    existence:

    ``ManagementRefusal``  every refusal a route or a dependency raises,
    including :func:`~prope.session_auth.require_session`'s ``401``.

    ``RequestValidationError``  FastAPI's own answer to a malformed body or an
    out-of-range query parameter is ``{"detail": [...]}`` — a **second** error
    shape, which A-045 says does not exist. Without this handler a client would
    have to parse two, and the one it would meet most often is the one nobody
    documented. ``details`` names the fields that failed and their error types
    and deliberately **not** ``input`` or ``ctx``: echoing a rejected value back
    is how a body ends up in a response from a module that has no body read path
    — and, from Phase 7, how a password a caller mistyped ends up in a response
    at all.

    ``SQLAlchemyError``  INT-028's *"5xx on database failure"*, with the
    ``request_id`` INT-024 requires. The message is fixed text: a driver's
    exception at this depth can quote a row, a constraint name or a connection
    string carrying credentials (T-02-34), so none of it is forwarded and only
    the exception's class reaches the log.

    **There is deliberately no catch-all ``Exception`` handler.** Registering one
    makes Starlette's ``ServerErrorMiddleware`` stop re-raising, so a genuine bug
    becomes a tidy ``500`` that no test fails on. An unexpected exception should
    be loud; a database failure is not unexpected, which is why it has a handler
    and the general case does not.

    That absence is also what makes INT-001's *"fails closed by raising"* true
    without any code saying so: ``may()`` raising reaches
    ``ServerErrorMiddleware`` and becomes a ``500`` nobody caught, and there is
    no handler in which it could have become an allow.
    """

    @application.exception_handler(ManagementRefusal)
    async def _management_refusal(_: Request, refusal: ManagementRefusal) -> JSONResponse:
        return _envelope(
            refusal.status_code,
            ErrorCode(refusal.code),
            refusal.message,
            refusal.details,
            "api.refused",
        )

    @application.exception_handler(RequestValidationError)
    async def _validation_failed(_: Request, error: RequestValidationError) -> JSONResponse:
        return _envelope(
            422,
            ErrorCode.VALIDATION_FAILED,
            "the request did not match this route's schema",
            {"fields": [{"loc": [str(part) for part in item["loc"]], "type": item["type"]} for item in error.errors()]},
            "api.refused",
        )

    @application.exception_handler(SQLAlchemyError)
    async def _database_failed(_: Request, error: SQLAlchemyError) -> JSONResponse:
        log.warning("api.database_failed", reason=type(error).__name__)
        return _envelope(
            500,
            ErrorCode.INTERNAL_ERROR,
            "the request could not be completed",
            None,
            "api.failed",
        )
