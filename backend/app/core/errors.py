"""Error envelope (S02): {"error": {"code", "message", "retryable", "details?"}}."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)

_STATUS_CODES = {
    401: "unauthorized",
    404: "not_found",
    405: "not_found",
    409: "conflict",
    429: "rate_limited",
}


class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, retryable: bool = False):
        super().__init__(message)
        self.code, self.message, self.status, self.retryable = code, message, status, retryable


def not_found(what: str = "Resource") -> AppError:
    return AppError("not_found", f"{what} not found", status=404)


def _body(code: str, message: str, retryable: bool = False, details: list | None = None) -> dict:
    error: dict = {"code": code, "message": message, "retryable": retryable}
    if details is not None:
        error["details"] = details
    return {"error": error}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(_body(exc.code, exc.message, exc.retryable), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"loc": list(e.get("loc", [])), "msg": e.get("msg", ""), "type": e.get("type", "")}
            for e in exc.errors()
        ]
        return JSONResponse(
            _body("validation_error", "Invalid request", details=details), status_code=422
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "internal")
        return JSONResponse(_body(code, str(exc.detail)), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error")
        return JSONResponse(
            _body("internal", "Something went wrong", retryable=True), status_code=500
        )
