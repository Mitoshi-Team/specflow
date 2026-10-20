"""Доменные исключения API сервиса извлечения атрибутов.

Каждое исключение несёт HTTP-статус, машиночитаемый ``ErrorCode`` и
безопасную деталь для ``ErrorResponse`` (api_contract.md, 3.8). Глобальные
обработчики (``error_handlers.py``) транслируют их в ответы без дублирования
try/except в эндпоинтах.
"""

from attribute_extractor.constants import (
    BATCH_HISTORY_UNAVAILABLE_DETAIL,
    BATCH_NOT_FOUND_DETAIL,
    BATCH_SIZE_MISMATCH_DETAIL,
    CATEGORY_NOT_FOUND_DETAIL,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_503_SERVICE_UNAVAILABLE,
    RATE_LIMITED_DETAIL,
)
from specflow_contracts import ErrorCode


class ApiError(Exception):
    """Базовое доменное исключение API с градацией статус/код/деталь."""

    status_code: int = HTTP_500_INTERNAL_SERVER_ERROR
    code: ErrorCode = ErrorCode.INTERNAL_ERROR

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class CategoryNotFoundError(ApiError):
    """Запрошенная категория не найдена (404)."""

    status_code = HTTP_404_NOT_FOUND
    code = ErrorCode.NOT_FOUND

    def __init__(self, category: str) -> None:
        super().__init__(f"{CATEGORY_NOT_FOUND_DETAIL}: {category}")


class BatchSizeMismatchError(ApiError):
    """Заявленный ``batch_size`` не совпадает с числом карточек ``items`` (400)."""

    status_code = HTTP_400_BAD_REQUEST
    code = ErrorCode.BAD_REQUEST

    def __init__(self, declared: int, actual: int) -> None:
        super().__init__(f"{BATCH_SIZE_MISMATCH_DETAIL}: {declared} != {actual}")


class BatchNotFoundError(ApiError):
    """Запрошенный ``batch_id`` не найден в истории батчей (404)."""

    status_code = HTTP_404_NOT_FOUND
    code = ErrorCode.NOT_FOUND

    def __init__(self, batch_id: str) -> None:
        super().__init__(f"{BATCH_NOT_FOUND_DETAIL}: {batch_id}")


class BatchHistoryUnavailableError(ApiError):
    """Хранилище истории батчей недоступно (503).

    Сбой внешней зависимости виден клиенту явно, а не маскируется пустым
    списком: причина (traceback) фиксируется в логе при выбросе.
    """

    status_code = HTTP_503_SERVICE_UNAVAILABLE
    code = ErrorCode.HTTP_ERROR

    def __init__(self) -> None:
        super().__init__(BATCH_HISTORY_UNAVAILABLE_DETAIL)


class TextCleanupInvariantError(ApiError):
    """Нарушен инвариант очистки текста (Этап 0): вход для правил/NER недоверен (500).

    Ошибка данных/кода сервиса, а не запроса: клиент не может её исправить,
    поэтому наружу уходит только сводная деталь, traceback — в лог.
    """

    status_code = HTTP_500_INTERNAL_SERVER_ERROR
    code = ErrorCode.INVARIANT_VIOLATION


class RateLimitExceededError(ApiError):
    """Превышен лимит частоты запросов (429)."""

    status_code = HTTP_429_TOO_MANY_REQUESTS
    code = ErrorCode.RATE_LIMITED

    def __init__(self, detail: str = RATE_LIMITED_DETAIL) -> None:
        super().__init__(detail)
