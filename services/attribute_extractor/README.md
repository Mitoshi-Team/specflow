# Attribute Extractor

Сервис извлечения атрибутов товаров из карточек (title, description,
`seller_attributes`) на FastAPI.

Пайплайн — **целевой гибрид без LLM**: чистка → structured → правила → NER →
векторный матч полей → нормализация → rules-fallback → мёржа → grounding →
уверенность. Генеративные модели не используются; главный инвариант —
«не выдумывать характеристики».

## 1. Разделение ответственности

Работа над модулем разделена между двумя зонами: Матвей (NER, эмбеддинги,
RAG-кластеризация, gold-набор и метрики) и Савелий (детерминированные проверки).

| Этап / компонент | Владелец | Примечание |
| --- | --- | --- |
| Этап 0. Чистка и препроцессинг | Савелий | HTML, мусор, нормализация текста, язык |
| Этап 1. Резолв схемы категории | Савелий | `SchemaRegistry`, generic-fallback |
| Этап 2. Structured (`seller_attributes`) | Савелий | key→value детерминирован |
| Этап 3. Ядро правил (регэкспы, единицы) | Савелий | explainable, ядро |
| Этап 4. NER (`CHARACTERISTIC` + `PROPERTY`) | Матвей | модель, пейринг, `ner_score` |
| Этап 5. Резолв поля — блоклист | Савелий | стоп-слова служебных «атрибутов» |
| Этап 5. Резолв поля — векторный матч | Матвей | `VectorIndex`, `FieldResolver` |
| RAG-кластеризация характеристик в поля | Матвей | канонизация длинного хвоста |
| Этап 6. Нормализация значений | Савелий | синонимы, единицы, enum |
| Этап 7. Rules-fallback | Савелий | только незакрытые обязательные поля |
| Этап 8. Мёржа и дедупликация | Савелий | группировка, max confidence, конфликт |
| Этап 9. Grounding (hard filter) | Савелий | `is_confirmed_in_text == true` |
| Этап 10. Уверенность/пороги/статус | Савелий | константы и пороги |
| Этап 11. Формирование результата | Савелий | сборка `ExtractionResult` |
| Weak-датасет NER (distant supervision) | Матвей | из `skus.pkl` + `sku_desc.parquet` |
| Обучение/оценка NER-модели | Матвей | версия модели, гиперпараметры |
| `FieldBlocklist` (бутстрап из EDA) | Савелий | источник стоп-слов |
| Gold-набор (ручной) | Матвей | входной текст + ожидаемый вывод |
| Метрики/приёмка на gold-наборе | Матвей | Precision/Recall/F1, пороги |

**Принцип границы:** детерминированные и NER/RAG-компоненты обмениваются
данными через общие контракты (раздел 3), а не через внутренности друг друга.
Это позволяет конфигурировать пайплайн (порядок, включение этапов, пороги) под
эксперименты без переписывания компонентов.

## 2. Полная схема системы

```mermaid
flowchart TD
    classDef ours fill:#d7f5dd,stroke:#2e7d32,color:#1b5e20;
    classDef det fill:#dbeafe,stroke:#1d4ed8,color:#1e3a8a;
    classDef infra fill:#f3f4f6,stroke:#6b7280,color:#374151;
    classDef data fill:#fef3c7,stroke:#b45309,color:#78350f;

    UI["Frontend / External (CSV / JSON)"]:::infra
    NG["nginx<br/>reverse proxy"]:::infra
    GW["API Gateway<br/>FastAPI /api/v1"]:::infra

    subgraph ORCH["Pipeline Orchestrator"]
        direction TB
        S0["Этап 0. Чистка и препроцессинг"]:::det
        S1["Этап 1. Резолв схемы категории"]:::det
        S2["Этап 2. Structured (seller_attributes)"]:::det
        S3["Этап 3. Ядро правил"]:::det
        S4["Этап 4. NER: CHARACTERISTIC + PROPERTY"]:::ours
        S5["Этап 5. Резолв поля:<br/>блоклист + векторный матч"]:::ours
        S6["Этап 6. Нормализация значений"]:::det
        S7["Этап 7. Rules-fallback"]:::det
        S8["Этап 8. Мёржа и дедупликация"]:::det
        S9["Этап 9. Grounding (hard filter)"]:::det
        S10["Этап 10. Уверенность / пороги / статус"]:::det
        S11["Этап 11. Формирование результата"]:::det
    end

    subgraph ML["Компоненты Матвея: NER / Vector / RAG-кластеризация"]
        NER["NER-модель<br/>multilingual encoder"]:::ours
        VI["VectorIndex<br/>embed / add / search"]:::ours
        CAT["FieldCatalog"]:::ours
        CLUS["RAG-кластеризация<br/>характеристик в поля"]:::ours
        WD["Weak-датасет<br/>distant supervision"]:::data
    end

    subgraph DETCOMP["Детерминированные ресурсы (Савелий)"]
        BL["FieldBlocklist"]:::det
        RULES["Правила / регэкспы, UnitRules"]:::det
        VOC["BrandVocab / AttributeVocab"]:::det
        SCH["CategorySchema / SchemaRegistry"]:::det
    end

    subgraph GOLD["Gold-набор (владелец: Матвей)"]
        G["Входной текст +<br/>ожидаемый вывод по канону"]:::data
    end

    UI --> NG --> GW --> S0
    S0 --> S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7 --> S8 --> S9 --> S10 --> S11
    S11 --> GW

    S1 -.-> SCH
    S3 -.-> RULES
    S6 -.-> VOC
    S5 -.-> BL
    S4 -.-> NER
    S4 -.-> VI
    S5 -.-> VI
    S5 -.-> CAT
    CLUS -.-> CAT
    WD -.-> NER
    G -.-> S10

    S4 -.->|"graceful degradation без модели"| S5
```

**Легенда:** зелёным — компоненты Матвея; синим — детерминированные (Савелий);
жёлтым — данные (weak/gold); серым — инфраструктура. Пунктир — использование
ресурса; сплошные стрелки — поток кандидатов по этапам.

## 3. Обязательные контракты компонентов

Компоненты делятся на **универсальные функции/интерфейсы** с явным вводом и
выводом. Ниже — нормативный контракт. Статус: ✅ реализовано, 🚧 заглушка,
🎯 целевой контракт (ещё не реализован).

### 3.1 Общие типы данных

```python
from dataclasses import dataclass


@dataclass
class CleanedCard:
    """Очищенная карточка (Этап 0). Source of truth для grounding."""
    sku_id: str
    title: str
    description: str
    seller_attributes: dict[str, str]
    language: str          # "ru" | "en" | "mixed"
    raw_text: str          # очищенный конкат текста


@dataclass
class NormalizedValue:
    """Результат нормализации значения (Этап 6)."""
    raw: str
    normalized: str
    unit: str | None
    value_type: str | None
    in_vocab: bool


@dataclass
class CharacteristicCluster:
    """Кластер близких характеристик, сведённых к каноническому полю (RAG)."""
    canonical_name: str          # формулировка-канон
    matched_code: str | None     # код FieldCatalog, если найден
    members: list[str]           # наблюдённые варианты-синонимы
    score: float                 # близость внутри кластера


@dataclass
class ConfidenceConfig:
    auto_threshold: float          # DEFAULT_CONFIDENCE_THRESHOLD
    review_threshold: float        # REVIEW_CONFIDENCE_THRESHOLD
    match_threshold: float         # DEFAULT_MATCH_THRESHOLD
    deterministic_confidence: float  # DEFAULT_DETERMINISTIC_CONFIDENCE
```

`AttributeCandidate`, `Span`, `ProductCard`, `CategorySchema`, `ExtractionResult`
— из `specflow_contracts` (см. `domain-model.md`).

### 3.2 Детерминированные функции (владелец: Савелий)

Чистые функции без побочных эффектов; ввод/вывод — только типы из 3.1 и
`specflow_contracts`.

```python
def clean(card: ProductCard) -> CleanedCard                                    # 🎯 (сейчас CardPreprocessor.preprocess)
def resolve_schema(card: ProductCard, registry: SchemaRegistry) -> CategorySchema  # ✅ SchemaRegistry.resolve
def extract_structured(card: CleanedCard, schema: CategorySchema) -> list[AttributeCandidate]  # 🎯
def extract_rules(card: CleanedCard, schema: CategorySchema) -> list[AttributeCandidate]       # 🚧 RuleExtractor.extract
def normalize_value(raw: str, field: FieldCatalogEntry | None) -> NormalizedValue              # ✅ ValueNormalizer.normalize
def rules_fallback(card: CleanedCard, schema: CategorySchema, missing: set[str]) -> list[AttributeCandidate]  # 🎯
def merge(candidates: list[AttributeCandidate]) -> list[AttributeCandidate]    # ✅ CandidateMerger.merge
def ground(candidates: list[AttributeCandidate], card: CleanedCard) -> list[AttributeCandidate]  # ✅ GroundingValidator.filter
def score(candidates: list[AttributeCandidate], config: ConfidenceConfig) -> list[AttributeCandidate]  # 🎯
def build_result(candidates: list[AttributeCandidate], card: CleanedCard, schema: CategorySchema) -> ExtractionResult  # 🎯
def is_blocked(name: str, blocklist: FieldBlocklist) -> bool                   # ✅ FieldBlocklist.is_blocked
```

**Правила:** функции не зависят от глобального состояния; конфигурация
передаётся аргументом (`ConfidenceConfig`, пороги, схемы). Порядок вызова
задаёт оркестратор.

### 3.3 NER-функции (владелец: Матвей)

```python
def predict(text: str) -> list[NERSpan]                     # 🎯 сырой инференс модели (CHARACTERISTIC/PROPERTY)
def pair(spans: list[NERSpan], window: int) -> list[NERPair]  # ✅ NERExtractor.extract_pairs, NER_PAIR_WINDOW
def extract_ner(card: CleanedCard, schema: CategorySchema) -> list[AttributeCandidate]  # ✅ NERExtractor.extract (возвращает [] до подключения модели)
```

`NERSpan = {text, label, start, end, score}`; `NERPair = {characteristic,
property, ner_score}`. `ner_score` — entity-level вероятность пары.

### 3.4 Векторный матч и RAG-кластеризация (владелец: Матвей)

```python
def embed(text: str) -> list[float]                                  # ✅ VectorIndex.embed
def add(key: str, vector: list[float] | None = None) -> None         # ✅ VectorIndex.add
def search(vector: list[float], k: int) -> list[tuple[str, float]]   # ✅ VectorIndex.search
def resolve_field(characteristic: str, resolver: FieldResolver) -> CharacteristicMatch  # ✅ FieldResolver.resolve
def cluster_characteristics(names: list[str], k: int | None = None) -> list[CharacteristicCluster]  # 🎯 RAG-кластеризация
```

`VectorIndex` — `Protocol`, конкретная реализация (FAISS/Qdrant/Chroma/
in-memory/lexical) не фиксируется. `resolve_field` возвращает `matched_code`,
`match_score`, `is_new_field`, `blocked`; при `match_score < match_threshold`
поле авто-добавляется в `FieldCatalog` (персистируется), шум отбрасывается по
блоклисту.

### 3.5 Точки конфигурации пайплайна

Оркестратор собирается из перечисленных функций, поэтому подгонка под тестовые
данные — это подмена реализации/порядка, без правки компонентов:

- **Включение/выключение этапов:** NER и векторный матч — опциональны (graceful
  degradation до structured/rules).
- **Пороги:** `MATCH_THRESHOLD`, `AUTO_THRESHOLD`, `REVIEW_THRESHOLD`,
  `DETERMINISTIC_CONFIDENCE` — через `ConfidenceConfig`/Pydantic Settings.
- **Реализации:** `VectorIndex`, NER-модель, блоклист, каталог — инъекция (DI).
- **Пространство реестров:** `ExtractorRegistry` (порядок по `priority`),
  `SchemaRegistry`.

## 4. Gold-набор (владелец: Матвей)

Малый ручной эталон для метрик и подбора порогов: `gold/gold.jsonl` —
100 карточек, стратифицированных по категориям с обязательными полями
организаторов. Сэмпл детерминирован (`GOLD_SEED = 20261017`), квоты категорий —
`GOLD_CATEGORY_QUOTAS` в `gold_sampling.py`; собрать черновик карточек:
`scripts/sample_gold_cards.py --out services/attribute_extractor/gold/gold.jsonl`.
Формат — JSONL, один объект на карточку: **входной текст** + **ожидаемый
вывод по канону**.

```json
{
  "card": {
    "sku_id": "123456",
    "title": "Смартфон Acme X 8/256 ГБ, чёрный",
    "description": "Экран 6.7 дюйма, батарея 5000 мА·ч",
    "seller_attributes": {"Бренд": "Acme", "Объём памяти": "256 ГБ"}
  },
  "expected": [
    {"attribute_code": "brand", "normalized_value": "Acme"},
    {"attribute_code": "storage", "normalized_value": "256 ГБ"},
    {"attribute_code": "diagonal", "normalized_value": "6,7 дюйм"},
    {"attribute_code": "battery_capacity", "normalized_value": "5000 мА·ч"},
    {"attribute_code": "color", "normalized_value": "черный"}
  ],
  "notes": "color присутствует только в title"
}
```

**Конвенции значений** (как в словарях/единицах нормализации): `256 ГБ`,
`5000 мА·ч`, `6,7 дюйм` (десятичная запятая), цвет — строчными («черный»,
ё→е); brand/model/processor — как в тексте карточки. Ожидаются только
реально присутствующие в тексте значения (grounding): точные значения из
параметров `*_search` допустимы, диапазоны продавца (`3000-5000 мАч`) — нет;
источник спорного значения фиксируется в `notes`.

**Валидация:** `validate_gold` (структура, дубликаты sku, канонические коды)
и `grounding_errors` (подтверждение текстом карточки); регрессионный тест на
файл — `TestGoldDataset` в `test_attribute_extractor_gold_sampling.py`. Gold
используется для Precision/Recall/F1 по атрибутам и настройки
`MATCH_THRESHOLD`/`AUTO_THRESHOLD` (см. метрики в `attribute_extractor.md`).

## 5. Устройство

- `src/attribute_extractor/main.py` — фабрика приложения `create_app()` и `app`.
- `src/attribute_extractor/config.py` — настройки Pydantic (`EXTRACTOR_*`):
  пороги уверенности, лимиты батча, таймауты, параметры NER/вектора.
- `src/attribute_extractor/constants.py` — значения по умолчанию и доменные
  константы (пороги, имена/приоритеты экстракторов, метки NER, версии).
- `src/attribute_extractor/preprocessing.py` — препроцессинг карточки (Этап 0):
  сбор `raw_text`, нормализация (HTML, мусорные символы, служебные вставки и
  водяные знаки), проверка инварианта очистки (`cleaning_invariant_violations`:
  очистка не меняет числа и единицы, иначе `ValueError`), язык, токенизация,
  резолв `CategorySchema`.
- `src/attribute_extractor/extractors/` — `BaseExtractor`, `ExtractorRegistry`,
  `RuleExtractor` (🚧), `NERExtractor` (пейринг + `ner_score`).
- `src/attribute_extractor/vector_index.py` — `VectorIndex` (Protocol) и
  `LexicalVectorIndex`/`InMemoryVectorIndex` (graceful degradation).
- `src/attribute_extractor/fields.py` — `FieldCatalog`, `FieldBlocklist`,
  `FieldResolver` (векторный матч + авто-добавление полей).
- `src/attribute_extractor/catalog_store.py` — атомарная персистентность
  каталога и блоклиста.
- `src/attribute_extractor/slugify.py` — генерация кодов полей (snake_case).
- `src/attribute_extractor/merging.py` — мёржа кандидатов (Этап 8): группировка
  по `(attribute_code, normalized_value)`, max confidence, конфликт → флаг.
- `src/attribute_extractor/grounding.py` — подтверждение в тексте (Этап 9).
- `src/attribute_extractor/normalization.py` — нормализация значений (Этап 6):
  регистр, синонимы, единицы, форматирование, enum-валидация.
- `src/attribute_extractor/references.py` — справочники (`AttributeVocab`,
  `UnitRule`, `BrandVocab`, `ReferenceCatalog`).
- `tests/` — unit-тесты.

## 6. Запуск

Из корня репозитория:

```bash
uv run uvicorn attribute_extractor.main:app --port 8001 --reload
```

## 7. Эндпоинты

| Метод | Путь | Описание |
| --- | --- | --- |
| GET | `/api/v1/health` | Проверка работоспособности |

В docker-сети сервис доступен API Gateway по адресу
`http://attribute_extractor:8001`.
