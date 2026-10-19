"""Глобальная обработка ошибок API в формате ErrorResponse (api_contract.md, 3.8).

Единая точка трансляции исключений в HTTP-ответы: эндпоинты не дублируют
try/except, а выбрасывают доменные исключения (``errors.py``). Все ответы об
ошибке имеют форму ``{"detail", "code", "errors"}``, поэтому клиент может
градировать ошибки по ``code``, не парся текст сообщения. Неизвестные
исключения логируются с traceback, наружу уходит только сводная деталь.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from attribute_extractor.constants import (
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_STATUS_ERROR_CODES,
    INTERNAL_ERROR_DETAIL,
    VALIDATION_ERROR_DETAIL,
)
from attribute_extractor.errors import ApiError
from specflow_contracts import ErrorCode, ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)


def error_response(
    status_code: int,
    detail: str,
    code: ErrorCode,
    errors: list[ErrorDetail] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Собирает JSON-ответ об ошибке в контрактной форме ErrorResponse."""
    body = ErrorResponse(detail=detail, code=code, errors=errors)
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(body),
        headers=headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    """Регистрирует глобальные обработчики исключений на приложении."""

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Ошибки валидации Pydantic/FastAPI → 422 с перечнем полей в ``errors``."""
        error_details = [
            ErrorDetail(msg=item["msg"], type=item["type"], loc=list(item["loc"]))
            for item in exc.errors()
        ]
        logger.info(
            "Validation error on %s %s: %d problem(s)",
            request.method,
            request.url.path,
            len(error_details),
        )
        return error_response(
            status_code=HTTP_422_UNPROCESSABLE_ENTITY,
            detail=VALIDATION_ERROR_DETAIL,
            code=ErrorCode.VALIDATION_ERROR,
            errors=error_details,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """HTTPException (в т.ч. 404/405 маршрутизации) → ErrorResponse с кодом по статусу."""
        code = HTTP_STATUS_ERROR_CODES.get(exc.status_code, ErrorCode.HTTP_ERROR)
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return error_response(
            status_code=exc.status_code,
            detail=detail,
            code=code,
            headers=exc.headers,
        )

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        """Доменные ошибки сервиса → ErrorResponse с их статусом и кодом."""
        # 5xx логируем как ошибку (с контекстом запроса), 4xx — как предупреждение.
        is_server_error = exc.status_code >= HTTP_500_INTERNAL_SERVER_ERROR
        logger.log(
            logging.ERROR if is_server_error else logging.WARNING,
            "API error %d (%s) on %s %s: %s",
            exc.status_code,
            exc.code,
            request.method,
            request.url.path,
            exc.detail,
        )
        return error_response(status_code=exc.status_code, detail=exc.detail, code=exc.code)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        """Любое необработанное исключение → 500 без утечки внутренностей.

        Traceback целиком уходит в лог (logger.exception), клиенту — только
        стабильная сводная деталь ``INTERNAL_ERROR_DETAIL``.
        """
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return error_response(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=INTERNAL_ERROR_DETAIL,
            code=ErrorCode.INTERNAL_ERROR,
        )
