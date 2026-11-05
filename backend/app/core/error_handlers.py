import logging
from collections.abc import Mapping
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import RequestResponseEndpoint

from app.schemas.errors import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: list[ErrorDetail] | None = None,
    request_id: str | None = None,
) -> JSONResponse:
    response = JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            error={
                "code": code,
                "message": message,
                "details": details or [],
            }
        ).model_dump(mode="json"),
    )
    if request_id:
        response.headers["X-Request-ID"] = request_id
    return response


def _http_error_code(status_code: int) -> str:
    return {
        404: "not_found",
        413: "file_too_large",
        415: "unsupported_media_type",
    }.get(status_code, "http_error")


def register_error_handlers(application: FastAPI) -> None:
    @application.middleware("http")
    async def add_request_id(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @application.exception_handler(HTTPException)
    async def handle_http_error(
        request: Request,
        exception: HTTPException,
    ) -> JSONResponse:
        detail = exception.detail
        code = _http_error_code(exception.status_code)
        message = str(detail)
        details: list[ErrorDetail] = []
        if isinstance(detail, Mapping):
            code = str(detail.get("code", code))
            message = str(detail.get("message", "The request could not be completed."))
            raw_details = detail.get("details", [])
            if isinstance(raw_details, list):
                details = [
                    ErrorDetail.model_validate(item)
                    for item in raw_details
                    if isinstance(item, Mapping)
                ]
        return _error_response(
            exception.status_code,
            code,
            message,
            details,
            getattr(request.state, "request_id", None),
        )

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exception: RequestValidationError,
    ) -> JSONResponse:
        details = [
            ErrorDetail(
                field=".".join(str(part) for part in error["loc"]),
                message=error["msg"],
                type=error["type"],
            )
            for error in exception.errors()
        ]
        return _error_response(
            422,
            "validation_error",
            "The request contains invalid values.",
            details,
            getattr(request.state, "request_id", None),
        )

    @application.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request,
        exception: Exception,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        logger.exception("Unhandled request error request_id=%s", request_id)
        return _error_response(
            500,
            "internal_server_error",
            "An unexpected server error occurred.",
            request_id=request_id,
        )
