"""Версионируемый seed каталога полей и блоклиста.

Источник истины для 9 целевых кодов (``attribute_extractor.md`` §3.2) и
шумовых имён атрибутов (выведены из EDA). Генератор
``scripts/build_field_catalog.py`` разворачивает этот seed в персистентные
``data/field_catalog.json`` и ``data/field_blocklist.txt``.
"""

from __future__ import annotations

from dataclasses import dataclass

FIELD_CATALOG_VERSION = "1.0.0"
"""Версия каталога полей (растёт при изменении состава/синонимов)."""


@dataclass(frozen=True)
class FieldSeed:
    """Запись каталога: канонический код, имя и наблюдаемые синонимы."""

    code: str
    name_ru: str
    synonyms: tuple[str, ...] = ()
    value_type: str | None = None
    unit: str | None = None


CANONICAL_FIELDS: tuple[FieldSeed, ...] = (
    FieldSeed(
        code="brand",
        name_ru="Бренд",
        synonyms=("Производитель", "Торговая марка", "Бренд товара"),
        value_type="string",
    ),
    FieldSeed(
        code="model",
        name_ru="Модель",
        synonyms=("Модель устройства", "Модель товара"),
        value_type="string",
    ),
    FieldSeed(
        code="color",
        name_ru="Цвет",
        synonyms=("Цвет корпуса", "Основной цвет"),
        value_type="enum",
    ),
    FieldSeed(
        code="storage",
        name_ru="Встроенная память",
        synonyms=(
            "Объем встроенной памяти",
            "Встроенная память (ROM)",
            "ROM",
        ),
        value_type="unit_value",
        unit="ГБ",
    ),
    FieldSeed(
        code="ram",
        name_ru="Оперативная память",
        synonyms=(
            "Оперативная память (RAM)",
            "Объем оперативной памяти",
            "ОЗУ",
            "RAM",
        ),
        value_type="unit_value",
        unit="ГБ",
    ),
    FieldSeed(
        code="diagonal",
        name_ru="Диагональ экрана",
        synonyms=("Диагональ", "Размер экрана", "Диагональ дисплея"),
        value_type="unit_value",
        unit="дюйм",
    ),
    FieldSeed(
        code="battery_capacity",
        name_ru="Ёмкость аккумулятора",
        synonyms=(
            "Емкость аккумулятора",
            "Ёмкость батареи",
            "Емкость батареи",
            "Аккумулятор",
        ),
        value_type="unit_value",
        unit="мА·ч",
    ),
    FieldSeed(
        code="drive",
        name_ru="Накопитель",
        synonyms=(
            "Объем накопителя",
            "Объём накопителя",
            "Общий объем накопителя",
            "Объем SSD",
            "Объём SSD",
            "Объем HDD",
            "Жесткий диск",
            "SSD",
        ),
        value_type="unit_value",
        unit="ГБ",
    ),
    FieldSeed(
        code="processor",
        name_ru="Процессор",
        synonyms=("Тип процессора", "Модель процессора", "CPU"),
        value_type="string",
    ),
)
"""Канонические поля, к которым резолвятся характеристики (Этап 5)."""


BLOCKLIST_SEED: tuple[str, ...] = (
    "подборки",
    "подборка",
    "продавец",
    "гарантия предоставляется",
    "потратить бонусы",
    "бонус",
    "кэшбэк",
    "промокод",
    "акция",
    "скидка",
    "рейтинг",
    "отзывы",
    "просмотр",
    "артикул продавца",
    "штрихкод",
    "витрина",
    "дата размещения",
    "общее количество",
)
"""Стоп-имена служебных «атрибутов» продавца (шум, отбрасывается резолвером)."""
