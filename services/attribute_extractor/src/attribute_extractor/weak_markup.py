"""Слабая разметка NER от seller-атрибутов (distant supervision, Этап 4).

Продавец указывает характеристики структурно (пары «имя параметра» →
«значение»); та же информация часто присутствует и в заголовке/описании.
Совпадение значения и имени параметра с текстом даёт спаны двух меток
``CHARACTERISTIC`` (имя параметра) и ``PROPERTY`` (значение) с кодом поля —
обучающая выборка для token-classification без ручной разметки.

Помимо канонических полей размечаются и неканонические параметры
(``include_uncoded``): их спаны несут ``attribute_code=None`` — метки NER от
кода не зависят, а код назначается полю только после ручного аудита
(авто-новые поля резолвера кода в слабой разметке не получают).

Формат записи: ``{"text", "spans": [{"start", "end", "label",
"attribute_code"}], "sku_id", "category_name"}``; текст — тот же вид, что
увидит NER в пайплайне (``normalize_text`` контрактного ``raw_text``).

Модуль свободен от pandas: загрузку данных делает CLI-скрипт
``scripts/make_ner_weak_dataset.py``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping
from dataclasses import dataclass, field
from functools import lru_cache

from attribute_extractor.constants import (
    NER_LABEL_CHARACTERISTIC,
    NER_LABEL_PROPERTY,
)
from attribute_extractor.fields import FieldResolver
from attribute_extractor.grounding import canonicalize_text
from attribute_extractor.preprocessing import normalize_text
from specflow_contracts.constants import RAW_DESCRIPTION_LABEL, RAW_TITLE_LABEL

# Значения-параметры, не несущие смысла значения (булевы флаги продавца).
_TRIVIAL_VALUES = frozenset({"да", "нет", "есть", "true", "false", "-", "—"})
_MIN_VALUE_LENGTH = 2
_MAX_TEXT_LENGTH = 4000
# Технические дубли имён параметров организаторов («Диагональ_search» и т.п.).
_TECHNICAL_NAME_SUFFIX = "_search"


@dataclass
class WeakSpan:
    """Спан слабой разметки в нормализованном тексте карточки.

    ``attribute_code`` — код канонического поля либо ``None`` для
    неканонического параметра; ``parameter_name`` — служебный контекст для
    статистики генератора, в JSONL не сериализуется.
    """

    label: str
    attribute_code: str | None
    start: int
    end: int
    text: str
    parameter_name: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "start": self.start,
            "end": self.end,
            "label": self.label,
            "attribute_code": self.attribute_code,
        }


@dataclass
class WeakRecord:
    """Запись weak-датасета: текст карточки и найденные спаны."""

    text: str
    sku_id: str | None
    category_name: str | None
    spans: list[WeakSpan] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "text": self.text,
            "spans": [span.as_dict() for span in self.spans],
            "sku_id": self.sku_id,
            "category_name": self.category_name,
        }


@lru_cache(maxsize=65536)
def _token_canonical(token: str) -> str:
    """Канон одного токена: casefold, ё→е, хвостовая пунктуация (кэшируется)."""
    return canonicalize_text(token)


@lru_cache(maxsize=8192)
def _canon_fragments(text: str) -> tuple[tuple[str, int, int], ...]:
    """Канон-фрагменты токенов текста: ``(фрагмент, начало, конец)``.

    Канонизация одного токена может дать несколько слов («128GB» → «128
    gb»); фрагменты несут координаты родительского токена, поэтому спан
    значения охватывает токен целиком — для слабой разметки достаточно.
    """
    fragments: list[tuple[str, int, int]] = []
    offset = 0
    for raw_token in text.split():
        token_start, token_end = offset, offset + len(raw_token)
        cursor = 0
        for word in _token_canonical(raw_token).split():
            position = _token_canonical(raw_token).find(word, cursor)
            fragments.append((word, token_start + min(position, len(raw_token)), token_end))
            cursor = position + len(word)
        offset = token_end + 1
    return tuple(fragments)


def find_value_span(
    text: str,
    value: str,
    fragments: tuple[tuple[str, int, int], ...] | None = None,
) -> tuple[int, int] | None:
    """Спан значения в нормализованном тексте (сопоставление канон-токенов).

    Значение ищется как последовательность канон-токенов (регистр/ё/единицы
    нормализуются: «128GB» ≡ «128 ГБ»); координаты — в исходном тексте.
    Однотокенные значения короче ``_MIN_VALUE_LENGTH`` слишком шумны.
    ``fragments`` — заранее посчитанные канон-фрагменты текста (один раз на
    карточку: тексты уникальны, кэш по тексту не работает).
    """
    value_tokens = _token_canonical(value).split()
    if not value_tokens or (len(value_tokens) == 1 and len(value_tokens[0]) < _MIN_VALUE_LENGTH):
        return None
    if fragments is None:
        fragments = _canon_fragments(text)
    canon_words = [fragment[0] for fragment in fragments]
    window = len(value_tokens)
    for index in range(len(canon_words) - window + 1):
        if canon_words[index : index + window] == value_tokens:
            return fragments[index][1], fragments[index + window - 1][2]
    return None


@dataclass(frozen=True)
class ParamResolution:
    """Резолв имени параметра для слабой разметки.

    ``code`` — код канонического поля либо ``None`` (неканонический параметр:
    имя вне каталога, в том числе авто-новое поле резолвера). ``skip`` —
    параметр отбрасывается целиком: блоклист либо техническое имя ``_search``.
    """

    code: str | None
    skip: bool


def is_noise_parameter(parameter_name: str) -> bool:
    """Служебное имя параметра, не являющееся характеристикой товара."""
    return parameter_name.strip().casefold().endswith(_TECHNICAL_NAME_SUFFIX)


def resolve_parameter(parameter_name: str, resolver: FieldResolver) -> ParamResolution:
    """Резолв имени параметра в код поля для слабой разметки.

    Канонический матч даёт код поля; имя вне каталога (резолвер при этом
    авто-добавляет новое поле в память) даёт ``code=None`` — канон назначает
    полю только ручной аудит; заблокированные и технические имена дают
    ``skip=True``.
    """
    if is_noise_parameter(parameter_name):
        return ParamResolution(code=None, skip=True)
    match = resolver.resolve(parameter_name)
    if match.blocked:
        return ParamResolution(code=None, skip=True)
    if match.matched_code is not None and not match.is_new_field:
        return ParamResolution(code=match.matched_code, skip=False)
    return ParamResolution(code=None, skip=False)


def build_record(
    title: str | None,
    description: str | None,
    seller_params: Iterable[Mapping],
    resolver: FieldResolver,
    *,
    sku_id: str | None = None,
    category_name: str | None = None,
    resolve_cache: MutableMapping[str, ParamResolution] | None = None,
    include_uncoded: bool = False,
) -> WeakRecord | None:
    """Запись weak-датасета из текста карточки и seller-параметров.

    Текст — ``normalize_text`` контрактного ``raw_text`` (с метками секций:
    в пайплайне NER увидит тот же вид). Для каждого параметра, чьё имя
    резолвится в каноническое поле, в тексте ищутся спаны значения
    (``PROPERTY``) и имени (``CHARACTERISTIC``); параметры без вхождения
    значения в текст пропускаются — «истина только в П» не размечается.

    ``include_uncoded=True`` добавляет спаны и для неканонических параметров
    (``attribute_code=None``): метки CHARACTERISTIC/PROPERTY от кода не
    зависят. ``resolve_cache`` — опциональный memo имён параметров: имена
    повторяются от карточки к карточке, векторный резолв каждого заново
    избыточен. Одинаковые спаны дедуплицируются (разные имена одного поля
    часто указывают на одно значение); при совпадении приоритет у спана
    с каноническим кодом.
    """
    text = normalize_text(
        f"{RAW_TITLE_LABEL} {title or ''}\n{RAW_DESCRIPTION_LABEL} {description or ''}"
    )
    if not text or len(text) > _MAX_TEXT_LENGTH:
        return None
    record = WeakRecord(text=text, sku_id=sku_id, category_name=category_name)
    resolved: list[tuple[str, str, str | None]] = []
    for parameter in seller_params:
        name = str(parameter.get("name", "")).strip()
        value = str(parameter.get("value", "")).strip()
        if not name or not value or value.casefold() in _TRIVIAL_VALUES:
            continue
        if len(value) < _MIN_VALUE_LENGTH:
            continue
        if resolve_cache is None or name not in resolve_cache:
            resolution = resolve_parameter(name, resolver)
            if resolve_cache is not None:
                resolve_cache[name] = resolution
        else:
            resolution = resolve_cache[name]
        if resolution.skip or (resolution.code is None and not include_uncoded):
            continue
        resolved.append((name, value, resolution.code))
    if not resolved:
        return None
    fragments = _canon_fragments(text)
    spans: dict[tuple[str, int, int], WeakSpan] = {}
    for name, value, code in resolved:
        value_span = find_value_span(text, value, fragments)
        if value_span is None:
            continue
        candidates = [
            WeakSpan(
                label=NER_LABEL_PROPERTY,
                attribute_code=code,
                start=value_span[0],
                end=value_span[1],
                text=text[value_span[0] : value_span[1]],
                parameter_name=name,
            )
        ]
        name_span = find_value_span(text, name, fragments)
        if name_span is not None:
            candidates.append(
                WeakSpan(
                    label=NER_LABEL_CHARACTERISTIC,
                    attribute_code=code,
                    start=name_span[0],
                    end=name_span[1],
                    text=text[name_span[0] : name_span[1]],
                    parameter_name=name,
                )
            )
        for span in candidates:
            key = (span.label, span.start, span.end)
            existing = spans.get(key)
            # Канонический код важнее некодированного дубля того же спана.
            if existing is None or (existing.attribute_code is None and code is not None):
                spans[key] = span
    record.spans = list(spans.values())
    if not record.spans:
        return None
    return record


def parse_seller_params(seller: object) -> list[dict[str, str]]:
    """Параметры из контрактного ``seller_attributes`` (dict либо список dict).

    Терпим к формам: ``{"Цвет": "черный", ...}``, YML-форма датасета
    ``[{"@name": ..., "#text": ...}, ...]``, ``[{"name": ..., "value": ...}]``.
    """
    if isinstance(seller, Mapping):
        return [{"name": str(name), "value": str(value)} for name, value in seller.items()]
    params: list[dict[str, str]] = []
    if isinstance(seller, list):
        for item in seller:
            if not isinstance(item, Mapping):
                continue
            name = item.get("@name") or item.get("name")
            value = item.get("#text") or item.get("@value") or item.get("value")
            if name is not None and value is not None:
                params.append({"name": str(name), "value": str(value)})
    return params


def stratified_split(
    records: list[WeakRecord], *, val_share: float = 0.1, seed: int = 20261017
) -> tuple[list[WeakRecord], list[WeakRecord]]:
    """Детерминированный train/val split со стратификацией по категории."""
    import random

    rng = random.Random(seed)
    by_category: dict[str, list[WeakRecord]] = {}
    for record in records:
        by_category.setdefault(record.category_name or "", []).append(record)
    train: list[WeakRecord] = []
    val: list[WeakRecord] = []
    for category in sorted(by_category):
        group = sorted(by_category[category], key=lambda record: (record.sku_id or "", record.text))
        rng.shuffle(group)
        cut = int(len(group) * val_share)
        val.extend(group[:cut])
        train.extend(group[cut:])
    return train, val
