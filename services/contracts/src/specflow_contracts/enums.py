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
