"""Сэмплирование и валидация gold-набора (README, раздел 4).

Gold-набор — малый ручной эталон карточек для метрик Precision/Recall/F1 по
атрибутам и подбора порогов. Сэмпл детерминирован (фиксированный seed) и
стратифицирован: карточки выбираются случайно, но с ограничением доли одной
категории и одного продавца, чтобы представленные категории были разнообразны.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Mapping, Sequence

from attribute_extractor.field_catalog_seed import CANONICAL_FIELDS
from attribute_extractor.grounding import GroundingValidator
from specflow_contracts import AttributeCandidate, ExtractionMethod, ProductCard

GOLD_SCHEMA_VERSION = "1.0.0"
"""Версия формата gold-записи (растёт при изменении структуры)."""

GOLD_SEED = 20261017
"""Seed сэмплирования карточек (воспроизводимость состава gold-набора)."""

GOLD_SAMPLE_SIZE = 100
"""Размер gold-сэмпла (число карточек)."""

GOLD_CATEGORY_QUOTAS = {
    "Смартфоны": 26,
    "iPhone": 12,
    "Ноутбуки": 26,
    "Планшеты": 10,
    "Телевизоры": 8,
    "Мониторы": 6,
    "Наушники": 6,
    "Роботы-пылесосы": 6,
}
"""Страта gold-набора: категории с обязательными полями организаторов.

Сумма квот равна ``GOLD_SAMPLE_SIZE``; при нехватке карточек в страте
недостающие добираются из остальных категорий (см. ``select_diverse``).
"""

MAX_PER_CATEGORY = 10
"""Максимум карточек одной категории в сэмпле."""

MAX_PER_VENDOR = 6
"""Максимум карточек одного продавца в сэмпле."""

MIN_DESCRIPTION_CHARS = 40
"""Минимальная длина описания, если атрибутов продавца мало."""

MIN_SELLER_ATTRS = 3
"""Достаточное число атрибутов продавца при коротком описании."""

CANONICAL_CODES = frozenset(entry.code for entry in CANONICAL_FIELDS)
"""Канонические коды атрибутов, допустимые в gold-наборе."""


def parse_offer_params(offer: Mapping) -> dict[str, str]:
    """Разобрать ``param`` YML-оффера в seller_attributes (имя → значение)."""
    attributes: dict[str, str] = {}
    for param in offer.get("param") or []:
        if not isinstance(param, Mapping):
            continue
        name = str(param.get("@name") or "").strip()
        value = param.get("#text")
        if name and value is not None:
            attributes[name] = str(value).strip()
    return attributes


def is_usable(card: Mapping) -> bool:
    """Годится ли карточка для разметки: есть текст и достаточно сигнала."""
    title = str(card.get("title") or "").strip()
    description = str(card.get("description") or "").strip()
    seller_attributes = card.get("seller_attributes") or {}
    if not title and not description:
        return False
    return len(description) >= MIN_DESCRIPTION_CHARS or len(seller_attributes) >= MIN_SELLER_ATTRS


def _bucket_key(card: Mapping, field: str) -> str:
    return str(card.get(field) or "")


def select_diverse(
    cards: Sequence[Mapping],
    count: int = GOLD_SAMPLE_SIZE,
    *,
    seed: int = GOLD_SEED,
    max_per_category: int = MAX_PER_CATEGORY,
    max_per_vendor: int = MAX_PER_VENDOR,
    quotas: Mapping[str, int] | None = None,
) -> list[Mapping]:
    """Детерминированно отобрать ``count`` карточек, разнообразных по категориям.

    Карточки перемешиваются (seed) и выбираются с лимитами на категорию и
    продавца. Если заданы ``quotas`` (название категории → число карточек),
    сначала наполняются квоты страт, затем недостающие добираются из остальных
    категорий; если лимиты продавца блокируют набор, недостающие карточки
    добираются без лимитов.
    """
    rng = random.Random(seed)
    pool = list(cards)
    rng.shuffle(pool)

    if quotas:

        def key(card: Mapping) -> str:
            return _bucket_key(card, "category_name")

    else:

        def key(card: Mapping) -> str:
            return _bucket_key(card, "category_id")

    by_category: dict[str, list[Mapping]] = {}
    for card in pool:
        by_category.setdefault(key(card), []).append(card)
    categories = list(by_category)
    rng.shuffle(categories)

    selected: list[Mapping] = []
    taken: set[int] = set()
    category_used: Counter[str] = Counter()
    vendor_used: Counter[str] = Counter()
    positions = dict.fromkeys(categories, 0)

    def category_limit(category: str) -> int:
        if quotas and category in quotas:
            return quotas[category]
        return max_per_category

    def take(card: Mapping) -> None:
        selected.append(card)
        taken.add(id(card))
        category_used[key(card)] += 1
        vendor_used[_bucket_key(card, "vendor")] += 1

    def take_next(category: str, *, respect_limits: bool) -> bool:
        bucket = by_category.get(category, [])
        index = positions.get(category, 0)
        while index < len(bucket):
            card = bucket[index]
            index += 1
            if id(card) in taken:
                continue
            if respect_limits and vendor_used[_bucket_key(card, "vendor")] >= max_per_vendor:
                continue
            positions[category] = index
            take(card)
            return True
        positions[category] = index
        return False

    for category, quota in (quotas or {}).items():
        while len(selected) < count and category_used[category] < quota:
            if not take_next(category, respect_limits=True):
                break

    progress = True
    while len(selected) < count and progress:
        progress = False
        for category in categories:
            if len(selected) >= count:
                break
            if category_used[category] >= category_limit(category):
                continue
            if take_next(category, respect_limits=True):
                progress = True

    if len(selected) < count:
        for category in categories:
            while len(selected) < count and take_next(category, respect_limits=False):
                pass
            if len(selected) >= count:
                break

    return selected


def validate_gold(records: Sequence[Mapping]) -> list[str]:
    """Проверить структуру gold-записей; вернуть список ошибок (пусто — ок)."""
    errors: list[str] = []
    seen_skus: set[str] = set()
    for index, record in enumerate(records):
        card = record.get("card")
        if not isinstance(card, Mapping):
            errors.append(f"record {index}: нет объекта card")
            continue
        sku_id = str(card.get("sku_id") or "").strip()
        if not sku_id:
            errors.append(f"record {index}: нет sku_id")
        elif sku_id in seen_skus:
            errors.append(f"record {index}: дубликат sku_id {sku_id}")
        else:
            seen_skus.add(sku_id)

        expected = record.get("expected")
        if not isinstance(expected, list) or not expected:
            errors.append(f"record {index}: expected пуст")
            continue
        codes: set[str] = set()
        for item in expected:
            if not isinstance(item, Mapping):
                errors.append(f"record {index}: элемент expected не объект")
                continue
            code = str(item.get("attribute_code") or "")
            if code not in CANONICAL_CODES:
                errors.append(f"record {index}: неизвестный код {code!r}")
            elif code in codes:
                errors.append(f"record {index}: дубликат кода {code!r}")
            else:
                codes.add(code)
            if not str(item.get("normalized_value") or "").strip():
                errors.append(f"record {index}: пустое значение для {code!r}")
    return errors


def grounding_errors(records: Sequence[Mapping]) -> list[str]:
    """Проверить, что gold-значения подтверждаются текстом карточки (grounding)."""
    validator = GroundingValidator()
    errors: list[str] = []
    for index, record in enumerate(records):
        card_data = record.get("card") or {}
        card = ProductCard(
            product_id=str(card_data.get("sku_id") or ""),
            title=card_data.get("title"),
            description=card_data.get("description"),
            seller_attributes=card_data.get("seller_attributes"),
            category_id=card_data.get("category_id"),
            category_name=card_data.get("category_name"),
        )
        for item in record.get("expected") or []:
            code = str(item.get("attribute_code") or "")
            value = str(item.get("normalized_value") or "")
            candidate = AttributeCandidate(
                attribute_code=code,
                raw_value=value,
                normalized_value=value,
                confidence=1.0,
                extraction_method=ExtractionMethod.RULE,
                is_confirmed_in_text=False,
            )
            if not validator.is_grounded(candidate, card):
                errors.append(f"record {index}: {code}={value!r} не подтверждён текстом карточки")
    return errors
