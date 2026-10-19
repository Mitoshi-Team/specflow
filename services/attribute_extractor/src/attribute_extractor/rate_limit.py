"""Ограничение частоты запросов (in-memory sliding window, api_contract.md, 2).

На каждый IP-адрес клиента приходится не более ``requests`` запросов за
скользящее окно ``window_seconds``; превышение → 429 в формате ErrorResponse
с заголовком ``Retry-After``. Состояние — in-memory (сервис stateless,
шаринг между инстансами не требуется; при горизонтальном масштабировании
лимит действует на инстанс). Ответ формируется прямо в middleware, а не
исключением: middleware расположен вне ``ExceptionMiddleware`` и исключения
из него не попали бы в глобальные обработчики приложения.
"""

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from attribute_extractor.constants import (
    HTTP_429_TOO_MANY_REQUESTS,
    RATE_LIMIT_MAX_TRACKED_CLIENTS,
    RATE_LIMITED_DETAIL,
)
from attribute_extractor.error_handlers import error_response
from specflow_contracts import ErrorCode


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Скользящее окно запросов на клиента; при превышении — 429 rate_limited."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        requests: int,
        window_seconds: float,
        exclude_paths: set[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._max_requests = requests
        self._window_seconds = window_seconds
        self._exclude_paths = exclude_paths or set()
        # Времена запросов каждого клиента внутри текущего окна.
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        client_key = request.client.host if request.client else "unknown"
        if request.url.path in self._exclude_paths:
            return await call_next(request)

        now = time.monotonic()
        window = self._hits[client_key]
        while window and now - window[0] >= self._window_seconds:
            window.popleft()

        if len(window) >= self._max_requests:
            retry_after = max(1, int(self._window_seconds - (now - window[0])) + 1)
            return error_response(
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                detail=RATE_LIMITED_DETAIL,
                code=ErrorCode.RATE_LIMITED,
                headers={"Retry-After": str(retry_after)},
            )

        window.append(now)
        self._prune(now)
        return await call_next(request)

    def _prune(self, now: float) -> None:
        """Чистит протухшие окна при числе отслеживаемых клиентов выше лимита."""
        if len(self._hits) <= RATE_LIMIT_MAX_TRACKED_CLIENTS:
            return
        stale = [
            key
            for key, hits in self._hits.items()
            if not hits or now - hits[-1] >= self._window_seconds
        ]
        for key in stale:
            del self._hits[key]
