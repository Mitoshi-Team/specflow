"""Перечисления доменной модели и API-контракта."""

from enum import StrEnum


class SpanField(StrEnum):
    """Поле исходной карточки, в котором найдено упоминание значения."""

    TITLE = "title"
    DESCRIPTION = "description"
    SELLER_ATTRIBUTES = "seller_attributes"


class ExtractionMethod(StrEnum):
    """Метод, которым получен кандидат значения атрибута."""

    STRUCTURED = "structured"
    RULE = "rule"
    NER = "ner"


class ExtractionStatus(StrEnum):
    """Итоговый статус обработки карточки."""

    OK = "ok"
    LOW_CONFIDENCE = "low_confidence"
    PARTIAL = "partial"
    ERROR = "error"
    SKIPPED = "skipped"


class AttributeValueType(StrEnum):
    """Тип значения атрибута в схеме категории."""

    STRING = "string"
    NUMBER = "number"
    ENUM = "enum"
    BOOLEAN = "boolean"
    UNIT_VALUE = "unit_value"


class HealthStatus(StrEnum):
    """Состояние работоспособности сервиса."""

    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"


class ErrorCode(StrEnum):
    """Машиночитаемый код ошибки в ``ErrorResponse.code`` (api_contract.md, 3.8).

    Позволяет клиенту градировать ошибки, не парся текст ``detail``.
    """

    BAD_REQUEST = "bad_request"
    """Семантическая ошибка запроса (например, batch_size не совпадает с items)."""

    VALIDATION_ERROR = "validation_error"
    """Ошибка валидации тела/параметров запроса (422)."""

    NOT_FOUND = "not_found"
    """Ресурс не найден (404)."""

    METHOD_NOT_ALLOWED = "method_not_allowed"
    """Метод не поддерживается для маршрута (405)."""

    RATE_LIMITED = "rate_limited"
    """Превышен лимит частоты запросов (429)."""

    INVARIANT_VIOLATION = "invariant_violation"
    """Нарушен внутренний инвариант обработки — ошибка данных/кода сервиса (500)."""

    INTERNAL_ERROR = "internal_error"
    """Непредвиденная ошибка сервиса (500)."""

    HTTP_ERROR = "http_error"
    """HTTP-ошибка без отдельного кода в перечислении."""
