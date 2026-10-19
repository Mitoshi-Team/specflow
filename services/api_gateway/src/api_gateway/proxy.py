"""Прозрачный прокси публичных маршрутов шлюза в сервис извлечения атрибутов.

Шлюз не содержит логики извлечения (``openspec/specs/architecture.md``,
``openspec/changes/rework-extraction-pipeline/proposal.md``): он принимает
запрос под ``API_PREFIX`` и передаёт его «как есть» в ``attribute_extractor``,
возвращая ответ upstream без изменений. Благодаря этому публичный контракт
(``openspec/specs/api_contract.md``) обслуживается с одного origin, а клиент не
знает о внутреннем разбиении на сервисы.
"""

import logging
from collections.abc import Mapping

import httpx
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response

from api_gateway.constants import (
    EXCLUDED_PROXY_REQUEST_HEADERS,
    EXCLUDED_PROXY_RESPONSE_HEADERS,
    HTTP_502_BAD_GATEWAY,
    PROXY_ACCEPT_ENCODING,
    PROXY_METHODS,
    UPSTREAM_UNAVAILABLE_DETAIL,
)
from specflow_contracts import ErrorCode, ErrorResponse

logger = logging.getLogger(__name__)


def _forward_headers(headers: Mapping[str, str], excluded: frozenset[str]) -> dict[str, str]:
    """Копирует заголовки, отбрасывая исключённые (регистронезависимо)."""
    return {name: value for name, value in headers.items() if name.lower() not in excluded}


def _upstream_url(request: Request, base_url: str) -> str:
    """Собирает URL upstream, сохраняя путь запроса и query-параметры.

    Сервис извлечения публикует маршруты под тем же ``API_PREFIX``, поэтому
    путь передаётся без переписывания — только с другим origin.
    """
    url = f"{base_url.rstrip('/')}{request.url.path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"
    return url


def _upstream_unavailable_response() -> JSONResponse:
    """Ответ 502 в контрактной форме ErrorResponse, когда upstream недоступен."""
    body = ErrorResponse(detail=UPSTREAM_UNAVAILABLE_DETAIL, code=ErrorCode.HTTP_ERROR)
    return JSONResponse(status_code=HTTP_502_BAD_GATEWAY, content=jsonable_encoder(body))


def register_proxy(app: FastAPI, base_url: str, prefix: str) -> None:
    """Регистрирует catch-all маршрут ``{prefix}/*`` → ``base_url``.

    Регистрировать нужно после собственных эндпоинтов шлюза (например,
    ``/health``): конкретные пути имеют приоритет над catch-all.
    """

    @app.api_route(
        f"{prefix}/{{path:path}}",
        methods=PROXY_METHODS,
        include_in_schema=False,
    )
    async def proxy(request: Request, path: str) -> Response:
        """Пересылает запрос в сервис извлечения и возвращает его ответ."""
        client: httpx.AsyncClient = request.app.state.upstream_client
        url = _upstream_url(request, base_url)
        headers = _forward_headers(request.headers, EXCLUDED_PROXY_REQUEST_HEADERS)
        headers["accept-encoding"] = PROXY_ACCEPT_ENCODING
        try:
            upstream = await client.request(
                request.method,
                url,
                content=await request.body(),
                headers=headers,
            )
        except httpx.HTTPError as exc:
            # Сетевые сбои upstream — не 500 шлюза: клиенту нужен явный сигнал
            # «сервис извлечения недоступен», чтобы отличить от ошибки данных.
            logger.warning("Upstream %s %s недоступен: %s", request.method, url, exc)
            return _upstream_unavailable_response()
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            headers=_forward_headers(upstream.headers, EXCLUDED_PROXY_RESPONSE_HEADERS),
        )
