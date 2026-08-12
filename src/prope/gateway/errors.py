"""The OpenAI error contract, and the handler set that is the only thing producing it.

ADR-0050: registered on the gateway application object, never on the management
one, so no handler inspects a request path to decide which contract it serves.
A-116's identical-shape rule for a scope refusal is enforced by
:func:`model_not_found` being the one constructor all three model-name refusals
reach for.
"""

from enum import StrEnum
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.background import BackgroundTask
from starlette.exceptions import HTTPException as StarletteHTTPException

from prope.provider_access.domain import DispatchError, ErrorClass

log = structlog.get_logger(__name__)

__all__ = [
    "ErrorType",
    "GatewayError",
    "authentication_failed",
    "error_payload",
    "install_openai_errors",
    "model_not_found",
    "openai_response",
    "translate_dispatch_error",
]


class ErrorType(StrEnum):
    INVALID_REQUEST = "invalid_request_error"
    AUTHENTICATION = "authentication_error"
    PERMISSION = "permission_error"
    RATE_LIMIT = "rate_limit_error"
    API = "api_error"


class GatewayError(Exception):
    def __init__(
        self,
        status_code: int,
        error_type: str,
        code: str,
        message: str,
        *,
        param: str | None = None,
        headers: dict[str, str] | None = None,
        background: BackgroundTask | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type
        self.code = code
        self.message = message
        self.param = param
        self.headers = headers or {}
        self.background = background


def error_payload(error_type: str, code: str, message: str, param: str | None) -> dict[str, Any]:
    return {"error": {"message": message, "type": error_type, "param": param, "code": code}}


def openai_response(
    status_code: int,
    error_type: str,
    code: str,
    message: str,
    *,
    param: str | None = None,
    headers: dict[str, str] | None = None,
    background: BackgroundTask | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_payload(error_type, code, message, param),
        headers=headers,
        background=background,
    )


def model_not_found(model: str) -> GatewayError:
    return GatewayError(
        404,
        ErrorType.INVALID_REQUEST,
        "model_not_found",
        f"The model `{model}` does not exist or you do not have access to it.",
        param="model",
    )


def authentication_failed() -> GatewayError:
    return GatewayError(
        401,
        ErrorType.AUTHENTICATION,
        "invalid_api_key",
        "Incorrect API key provided.",
    )


DISPATCH_TRANSLATION: dict[ErrorClass, tuple[int, str, str]] = {
    ErrorClass.RATE_LIMITED: (429, ErrorType.RATE_LIMIT, "rate_limit_exceeded"),
    ErrorClass.CREDENTIAL_REJECTED: (502, ErrorType.API, "upstream_credential_rejected"),
    ErrorClass.MODEL_UNAVAILABLE: (502, ErrorType.API, "upstream_model_unavailable"),
    ErrorClass.INVALID_REQUEST: (400, ErrorType.INVALID_REQUEST, "upstream_invalid_request"),
    ErrorClass.CONTENT_POLICY: (400, ErrorType.INVALID_REQUEST, "content_policy_violation"),
    ErrorClass.UPSTREAM_UNAVAILABLE: (502, ErrorType.API, "upstream_unavailable"),
    ErrorClass.UPSTREAM_TIMEOUT: (504, ErrorType.API, "upstream_timeout"),
    ErrorClass.CONTRACT_VIOLATION: (502, ErrorType.API, "upstream_contract_violation"),
    ErrorClass.BLOCKED_ADDRESS: (500, ErrorType.API, "provider_address_refused"),
    ErrorClass.KEY_UNAVAILABLE: (500, ErrorType.API, "provider_key_unavailable"),
    ErrorClass.CONFIGURATION_UNUSABLE: (500, ErrorType.API, "provider_configuration_unusable"),
    ErrorClass.ADMISSION_REFUSED: (503, ErrorType.API, "provider_admission_refused"),
}

DISPATCH_MESSAGES: dict[ErrorClass, str] = {
    ErrorClass.RATE_LIMITED: "The upstream provider rate limited this request.",
    ErrorClass.CREDENTIAL_REJECTED: "The upstream provider rejected the stored credential.",
    ErrorClass.MODEL_UNAVAILABLE: "The upstream provider does not serve the bound model.",
    ErrorClass.INVALID_REQUEST: "The upstream provider refused the request.",
    ErrorClass.CONTENT_POLICY: "The upstream provider refused the request on content policy.",
    ErrorClass.UPSTREAM_UNAVAILABLE: "The upstream provider is unavailable.",
    ErrorClass.UPSTREAM_TIMEOUT: "The upstream provider did not answer within the deadline.",
    ErrorClass.CONTRACT_VIOLATION: "The upstream provider answered outside the expected shape.",
    ErrorClass.BLOCKED_ADDRESS: "The provider configuration names an address Prope refuses.",
    ErrorClass.KEY_UNAVAILABLE: "The provider credential cannot be decrypted.",
    ErrorClass.CONFIGURATION_UNUSABLE: "The provider configuration cannot serve this call.",
    ErrorClass.ADMISSION_REFUSED: "Prope's provider admission gate refused this dispatch.",
}


def translate_dispatch_error(error: DispatchError) -> GatewayError:
    status_code, error_type, code = DISPATCH_TRANSLATION[error.error_class]
    headers = {"retry-after": "1"} if status_code == 429 else None
    return GatewayError(
        status_code,
        error_type,
        code,
        DISPATCH_MESSAGES[error.error_class],
        headers=headers,
    )


def install_openai_errors(application: FastAPI) -> None:
    @application.exception_handler(GatewayError)
    async def _gateway_error(_: Request, error: GatewayError) -> JSONResponse:
        return openai_response(
            error.status_code,
            error.error_type,
            error.code,
            error.message,
            param=error.param,
            headers=error.headers or None,
            background=error.background,
        )

    @application.exception_handler(RequestValidationError)
    async def _validation_failed(_: Request, error: RequestValidationError) -> JSONResponse:
        first = error.errors()[0] if error.errors() else None
        param = ".".join(str(part) for part in first["loc"][1:]) if first else None
        return openai_response(
            422,
            ErrorType.INVALID_REQUEST,
            "invalid_request",
            "The request body did not match the chat completions schema.",
            param=param or None,
        )

    @application.exception_handler(StarletteHTTPException)
    async def _http_exception(_: Request, error: StarletteHTTPException) -> JSONResponse:
        if error.status_code == 404:
            return openai_response(
                404,
                ErrorType.INVALID_REQUEST,
                "unknown_url",
                "Unknown request URL.",
            )
        if error.status_code == 405:
            return openai_response(
                405,
                ErrorType.INVALID_REQUEST,
                "method_not_allowed",
                "Not allowed on this endpoint.",
            )
        return openai_response(
            error.status_code,
            ErrorType.INVALID_REQUEST if error.status_code < 500 else ErrorType.API,
            "request_refused",
            "The request was refused.",
        )

    @application.exception_handler(Exception)
    async def _unhandled(_: Request, error: Exception) -> JSONResponse:
        log.warning("gateway.unhandled", reason=type(error).__name__)
        return openai_response(
            500,
            ErrorType.API,
            "internal_error",
            "The server had an error while processing your request.",
        )
