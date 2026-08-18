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
from prope.session_auth import WORKSPACE_REQUIRED as WORKSPACE_REQUIRED_CODE
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
    #: ADR-0056. The session is live and names no workspace, and this route reads
    #: tenant data. Its counterpart in the client is the workspace chooser, not the
    #: sign-in screen — which is why it is not ``SESSION_REQUIRED``, and why a
    #: distinct code was worth minting rather than reusing ``PERMISSION_DENIED``:
    #: nothing was denied, and the person has an obvious next action.
    WORKSPACE_REQUIRED = WORKSPACE_REQUIRED_CODE
    #: ADR-0057. The presented invite code is unknown, expired, revoked, or has
    #: reached its use limit. **One code for all four**, byte-identical in every
    #: field, for the reason ``AUTHENTICATION_FAILED`` shares its three failures:
    #: distinguishing them turns the endpoint into an oracle for *"this code is
    #: live"*, which is the first thing a script would read.
    INVITE_NOT_REDEEMABLE = "invite_not_redeemable"

    # --- provider-access (INT-027) ----------------------------------------
    #: A-090. The live probe did not pass, so nothing was saved active. Its
    #: ``details.reason`` is one of ``verification``'s closed reason tokens —
    #: never a provider's own error body (T-026).
    PROVIDER_VERIFICATION_FAILED = "provider_verification_failed"
    #: ADR-0047. The base URL is not https, or it resolves to a loopback,
    #: link-local, reserved or private address. Refused at save time and again
    #: at dispatch time.
    PROVIDER_BASE_URL_REFUSED = "provider_base_url_refused"
    #: A-096. A revision binds this configuration, so the delete is refused by
    #: the foreign key. Disabling it is the operation that is always available.
    PROVIDER_BOUND_BY_REVISIONS = "provider_bound_by_revisions"
    #: ADR-0032. No ``PROPE_KEK_V<n>`` is present in this process, so no
    #: credential can be stored or read. Distinct from every provider-origin
    #: refusal, because this one is Prope's.
    PROVIDER_KEY_UNAVAILABLE = "provider_key_unavailable"

    # --- prompt-registry (INT-024) ----------------------------------------
    #: A-021. ``namespace/name`` is unique per workspace and immutable once
    #: created, so this is a ``409`` rather than a ``422``: the body was
    #: well-formed and the name is taken.
    REGISTRY_MODEL_NAME_TAKEN = "registry_model_name_taken"
    #: A-052. The prompt has an active release, so ``/retire`` is refused until
    #: INT-014 clears it. ``details`` names the release, because a refusal that
    #: cannot say what is blocking it is a button that does nothing.
    REGISTRY_ACTIVE_RELEASE = "registry_active_release"
    #: A-048. Two authors allocated the same ``revision_number`` and the unique
    #: constraint arbitrated. The author sees *somebody else saved first* rather
    #: than losing their text silently, which is the whole point of the counter
    #: being allocated inside the transaction.
    REGISTRY_REVISION_CONFLICT = "registry_revision_conflict"
    #: The revision binds a ``provider_config_id`` no configuration carries.
    #: Distinct from a model the catalogue does not list, which is **never** a
    #: refusal (A-091, INT-016): an unknown configuration is a broken reference,
    #: a missing catalogue entry is a stale third-party list.
    REGISTRY_UNKNOWN_PROVIDER_CONFIG = "registry_unknown_provider_config"
    #: The folder slug is claimed — by a declared folder, or by some prompt's
    #: namespace. **One code for both**, because they are one fact to the person
    #: typing: the grid already draws a card either way, and a second code would
    #: describe our storage rather than their workspace. ``PATCH`` is the verb
    #: that names an existing folder; ``POST`` refuses it.
    REGISTRY_FOLDER_SLUG_TAKEN = "registry_folder_slug_taken"
    #: Prompts still carry this namespace, so the folder will not be unnamed.
    #: There is no foreign key being protected here — the prompts would survive
    #: untouched and the folder would revert to a derived one — so ``details``
    #: carries the count, which is the only thing that makes the refusal
    #: actionable rather than mysterious.
    REGISTRY_FOLDER_NOT_EMPTY = "registry_folder_not_empty"
    #: The playground turn cannot be dispatched: the revision binds no provider
    #: configuration or no upstream model. Refused **before** the provider is
    #: called rather than after, because otherwise every turn returns the same
    #: transport error and the screen reads as a broken prompt instead of an
    #: unconfigured one. The next action is binding a provider, and the code is
    #: what lets the client say so.
    REGISTRY_TRIAL_UNBOUND = "registry_trial_unbound"
    #: A-078 / ADR-0011. The body uses ``{{name}}`` and the request supplied no
    #: value. ``details.variable`` names it, because the screen renders one input
    #: per placeholder and needs to know which one to mark.
    REGISTRY_TRIAL_MISSING_VARIABLE = "registry_trial_missing_variable"
    #: The composed set exceeds ``MAX_COMPOSED_BYTES``. Its own code rather than
    #: ``VALIDATION_FAILED`` because the body was well-formed and the fix is to
    #: shorten the conversation, which is advice a generic code cannot give.
    REGISTRY_TRIAL_TOO_LARGE = "registry_trial_too_large"
    #: A-029 / INT-020. The workspace is over its monthly ceiling. Ceilings
    #: refuse eval runs and never gateway traffic; a playground turn is internal
    #: spend a person chose to make, so it is on the refusing side of that line.
    REGISTRY_TRIAL_SPEND_CEILING_REACHED = "registry_trial_spend_ceiling_reached"

    # --- prompt-conversion ----------------------------------------------
    CONVERSION_INVALID_SOURCE = "conversion_invalid_source"
    CONVERSION_INVALID_AGENT_OUTPUT = "conversion_invalid_agent_output"
    CONVERSION_AGENT_UNAVAILABLE = "conversion_agent_unavailable"

    # --- evaluation, the dataset library (step 4b) ------------------------
    #: A shipped Chung dataset cannot be edited or deleted: it is the same in
    #: every workspace, which is the only reason "passes the safety set" means
    #: anything across two installs. Copying it into a folder is the answer, and
    #: the message says so — this is a refusal with an obvious next action, not
    #: a wall.
    EVAL_DATASET_READ_ONLY = "eval_dataset_read_only"
    #: The drafting agent could not be called at all — down, or its breaker is
    #: open. Deliberately distinct from `EVAL_DRAFTER_EMPTY`: this one is
    #: somebody else's outage and retrying later is the answer.
    EVAL_DRAFTER_UNAVAILABLE = "eval_drafter_unavailable"
    #: The agent answered, and nothing it returned could be stored — every case
    #: was incomplete, or every assertion failed to compile. The call worked;
    #: the output did not. Retrying may help, writing one by hand certainly
    #: will, and conflating this with the outage above would advise neither.
    EVAL_DRAFTER_EMPTY = "eval_drafter_empty"

    # --- release-control (INT-026) ----------------------------------------
    #: A-067. Another revision of this prompt is already In review, and this
    #: submission is not a newer one — a newer submission supersedes the open
    #: task instead of being refused.
    RELEASE_REVIEW_ALREADY_OPEN = "release_review_already_open"
    #: A-058 / A-070, ADR-0005. Evaluation reports `requires_acknowledgement`,
    #: or the summary could not be pulled at all — unknown evidence is treated
    #: like failing evidence. `details.failing_suites` names them; the decision
    #: is never blocked, only never frictionless.
    RELEASE_ACKNOWLEDGEMENT_REQUIRED = "release_acknowledgement_required"
    #: A-009 / A-069 / A-066. Break-glass, withdraw, restore and
    #: request-changes each carry a mandatory one-line reason, and
    #: `requires_reason` in the action registry refuses the history append
    #: independently.
    RELEASE_REASON_REQUIRED = "release_reason_required"
    #: A-072. INT-013's compare-and-set lost: somebody released something else
    #: while this screen was open. `details` names what is actually released
    #: now, because a reviewer who cannot see that cannot re-decide.
    RELEASE_POINTER_CONFLICT = "release_pointer_conflict"
    #: BR-03. Only an `Approved` revision may be released. This module checks
    #: it and `fk_prompt_property_released_version_id` enforces it
    #: independently — defence in depth, because the whole product fails if
    #: unapproved text reaches production.
    RELEASE_REVISION_NOT_APPROVED = "release_revision_not_approved"
    #: A release with no approval record is only reachable through break-glass,
    #: which is a separate permission and a separate route.
    RELEASE_NO_APPROVAL_RECORDED = "release_no_approval_recorded"
    #: A-010 / OQ-002. A restore is exempt from a fresh release decision only
    #: for a revision that was already released once. A restore to an Approved
    #: revision that has never been released is an ordinary release.
    RELEASE_NOT_PREVIOUSLY_RELEASED = "release_not_previously_released"
    #: A-052 / ADR-0009. There is nothing to withdraw. A withdrawal of nothing
    #: is a caller bug rather than a no-op, and absorbing it would write a
    #: mandatory-reason event describing an act that did not happen.
    RELEASE_NOTHING_RELEASED = "release_nothing_released"
    #: A-073. The task is closed or superseded. It never closes itself on a
    #: timer, and it cannot be closed twice.
    RELEASE_TASK_NOT_OPEN = "release_task_not_open"
    #: ADR-0008. INT-012 refused the transition — the revision is not in a
    #: state the decision can be applied to, or a double-submit arrived.
    RELEASE_ILLEGAL_TRANSITION = "release_illegal_transition"

    # --- chat-orchestrator -------------------------------------------------
    #: The proposal was confirmed or rejected already. Its own code rather than
    #: ``ALREADY_EXISTS`` because a second click on a confirmation card is the
    #: normal way to reach it, and the client renders it as *"đã xử lý"* beside
    #: the existing result rather than as a failure the person caused.
    CHAT_ACTION_ALREADY_DECIDED = "chat_action_already_decided"


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

    def _conversion_no_store(request: Request, response: JSONResponse) -> JSONResponse:
        if request.url.path == "/api/v1/prompt-conversions":
            response.headers["Cache-Control"] = "no-store"
        return response

    @application.exception_handler(ManagementRefusal)
    async def _management_refusal(request: Request, refusal: ManagementRefusal) -> JSONResponse:
        return _conversion_no_store(request, _envelope(
            refusal.status_code,
            ErrorCode(refusal.code),
            refusal.message,
            refusal.details,
            "api.refused",
        ))

    @application.exception_handler(RequestValidationError)
    async def _validation_failed(request: Request, error: RequestValidationError) -> JSONResponse:
        return _conversion_no_store(request, _envelope(
            422,
            ErrorCode.VALIDATION_FAILED,
            "the request did not match this route's schema",
            {"fields": [{"loc": [str(part) for part in item["loc"]], "type": item["type"]} for item in error.errors()]},
            "api.refused",
        ))

    @application.exception_handler(SQLAlchemyError)
    async def _database_failed(request: Request, error: SQLAlchemyError) -> JSONResponse:
        log.warning("api.database_failed", reason=type(error).__name__)
        return _conversion_no_store(request, _envelope(
            500,
            ErrorCode.INTERNAL_ERROR,
            "the request could not be completed",
            None,
            "api.failed",
        ))
