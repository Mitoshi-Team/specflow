# План рефакторинга сервиса attribute_extractor под новую спеку (без LLM)

## 1. Цель

Переработать `services/attribute_extractor` согласно новой спецификации (`openspec/specs/attribute_extractor.md`, `domain-model.md`, `architecture.md`, `api_contract.md`) и change-дизайну. Цель — реализовать целевой гибрид без LLM: структурированный путь (`seller_attributes`) → правила (ядро) → NER (хвост с 2 метками `CHARACTERISTIC`/`PROPERTY`) → векторный матч к `FieldCatalog` + `FieldBlocklist` → нормализация → rules-fallback → мёржа → grounding → расчёт уверенности.

**Важно:** План сфокусирован **только на `services/attribute_extractor`**. Контракты (`services/contracts`) изменятся (по `tasks.md` §3), но в рамках этого плана они рассматриваются как **предполагаемо обновлённые/допущение**.

## 2. Базовые предпосылки

- Спецификации: attribute_extractor.md (этапы 0–11), domain-model.md (сущности), architecture.md (компоненты, `.env`), api_contract.md.
- EDA завершена (см. `EDA/`): 10 708 уникальных имён атрибутов, шум-список (`Подборки`, `Продавец`, BI-поля, `Гарантия предоставляется`, `Потратить бонусы`), ограничение `color 16.8%` присутствует в тексте.
- Текущий код: `BaseExtractor`, `ExtractorRegistry`, `RuleExtractor`, `NERExtractor` — заглушки; рабочие: `preprocessing.py`, `normalization.py`, `grounding.py`, `merging.py`, `references.py`, `config.py`, `constants.py`.
- Целевые коды: `brand, model, color, storage, diagonal, battery_capacity, ram, drive, processor`.

## 3. Объём плана (только attribute_extractor)

План покрывает исключительно модуль `services/attribute_extractor`:
- `constants.py`/`config.py`
- `preprocessing.py` (расширить чистку)
- новые модули: `cleaning.py`, `fields.py`, `vector_index.py`, `catalog_store.py`, `slugify.py`, `candidates.py` (или internal DTO), `confidence.py`, `pipeline.py`
- `extractors/*`: `structured.py`, `rule.py`, `ner.py`; удалить `dictionary.py`, `classifier.py`, `transformer.py`, `llm.py`
- `merging.py`, `grounding.py`, `normalization.py`, `references.py`
- `main.py` (минимум для health + возможное подключение пайплайна; маршруты extract/info/config — вопрос интеграции с api_gateway)
- `tests/` (обновить под новую модель, добавить новые тесты)

Контракты (`ExtractionMethod` → `{structured,rule,ner}`, `AttributeCandidate` + `ner_score`/`match_score`/`is_new_field`, схемы API) — предполагаются уже приведёнными в соответствие спецификации (или планируется отдельным шагом). При реализации эксплуатируем текущие типы контрактов при их соответствии; если требуется, координируемся вне этого плана.

## 4. Целевой порядок пайплайна

Согласно attribute_extractor.md §4:

1. **Этап 0.** Чистка и препроцессинг (clean) — `card → raw_text → clean_text`
2. **Этап 1.** Резолв схемы категории — `SchemaRegistry.resolve`
3. **Этап 2.** Structured-путь (`seller_attributes`) — `StructuredExtractor` → candidates
4. **Этап 3.** Ядро правил (title/description) — `RuleExtractor`
5. **Этап 4.** NER (`CHARACTERISTIC`/`PROPERTY`, пейринг в окне) → `NERExtractor`
6. **Этап 5.** Резолв поля (векторный матч + блоклист) → `FieldResolver` (конвертация характеристик в канонический код)
7. **Этап 6.** Нормализация значений → `ValueNormalizer`
8. **Этап 7.** Rules-fallback (только незакрытые обязательные поля схемы) → повторный запрос к правилам
9. **Этап 8.** Мёржа и дедупликация → `CandidateMerger`
10. **Этап 9.** Grounding (hard filter) → `GroundingValidator`
11. **Этап 10.** Уверенность, пороги, статус → `ConfidenceCalculator`
12. **Этап 11.** Формирование результата → `ExtractionResult`

## 5. Константы, конфиг, семантика

### 5.1 constants.py (переработка)

Удалить: `DEFAULT_METHOD_WEIGHTS`, штрафы `ENUM_OUT_OF_VOCAB_PENALTY`, `CONFLICTING_VALUES_PENALTY`, `WEAK_EVIDENCE_PENALTY`, `MERGED_METHOD=HYBRID`, `DEFAULT_HYBRID_STRATEGY`, блок LLM (`DEFAULT_ENABLE_LLM`, `DEFAULT_LLM_*`), `TRANSFORMER_*`, `CLASSIFIER_*`, `DICT_*` при их остатках. Удалить `EXTRACTOR_*` приоритеза и имена для удаляемых методов.

Добавить:
- `DEFAULT_MATCH_THRESHOLD = 0.75`
- `DEFAULT_DETERMINISTIC_CONFIDENCE = 0.90`
- `AUTO_THRESHOLD = 0.80`, `REVIEW_THRESHOLD = 0.60` (или через config)
- пути: `DEFAULT_FIELD_CATALOG_PATH = "data/field_catalog.json"`, `DEFAULT_FIELD_BLOCKLIST_PATH = "data/field_blocklist.txt"`, `DEFAULT_NER_MODEL_PATH = "models/ner"`
- векторный индекс: `DEFAULT_VECTOR_K = 5`, `DEFAULT_VECTOR_BACKEND = "auto"`
- `MAX_NEW_FIELDS = 1000` (защита от дрейфа), `NEW_FIELD_SALT` не требуется
- HTML/очистка: `HTML_TAG_RE`, `BOILERPLATE_RE` (опц.)
- NER: `NER_LABEL_CHARACTERISTIC = "CHARACTERISTIC"`, `NER_LABEL_PROPERTY = "PROPERTY"`, `NER_PAIR_WINDOW = 32` (фрагмент/предложение)
- слугификация: допустимые символы `SLUG_RE`
- feature keys: `FEATURE_CHARACTERISTIC = "characteristic"`, `FEATURE_MATCH_SCORE = "match_score"`, `FEATURE_IS_NEW_FIELD = "is_new_field"`

Сохранять язык, кавычки, тире, единицы, `WHITESPACE_*`, `JUNK_CHARS_*`.

### 5.2 config.py (переработка)

Удалить: `method_weights`, `hybrid_strategy`, `enable_llm`, `llm_*`, `transformer_model_version`.
Добавить:
- `match_threshold: float = Field(DEFAULT_MATCH_THRESHOLD, ge=0, le=1)`
- `deterministic_confidence: float = Field(DEFAULT_DETERMINISTIC_CONFIDENCE, ge=0, le=1)`
- `auto_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD` (уже есть, но переименовать/синхронизировать → `AUTO_THRESHOLD=0.80` в spec)
- `review_threshold: float = REVIEW_CONFIDENCE_THRESHOLD`
- `field_catalog_path: Path | str`, `field_blocklist_path: Path | str`
- `ner_model_path: Path | str`, `vector_backend`, `vector_k`, `max_new_fields`, `catalog_persist: bool = True`

Убрать валидацию `method_weights`. Валидировать `auto >= review`.

## 6. Новые модули

### 6.1 `slugify.py`
`slugify(name: str) -> str`: нижний регистр, синонимов нет; замена пробелов/дефисов на `_`, удаление прочего. Код поля — `snake_case`.

### 6.2 `cleaning.py`
`strip_html(s: str)`, `clean_text(s: str)` (служебные вставки/водяные знаки по мере необходимости, мусорные символы, кавычки, дефисы, пробелы). Интегрировать в `preprocessing` (Этап 0).

### 6.3 `candidates.py` (internal DTO, см. §4.2.1 рассуждение)
`CharacteristicCandidate` (pydantic/dataclass):
- `characteristic: str | None` (ключ из seller_attributes либо NER-спан)
- `attribute_code: str | None` (код известен сразу — rule/exact; либо None для unresolved)
- `raw_value: str`
- `normalized_value: str | None`
- `method: ExtractionMethod` (`structured`, `rule`, `ner`)
- `confidence: float | None`
- `ner_score: float | None`
- `match_score: float | None`
- `is_new_field: bool | None`
- `source_spans: list[Span]`, `evidence_text: str | None`, `features: dict`
`to_attribute_candidate(...)` — для финальной трансформации.

### 6.4 `fields.py`
- `FieldCatalogEntry`: code, name_ru, synonyms, value_type, unit, is_new_field (по spec §3.8)
- `FieldCatalog`: `load(save)`, `all()`, `get(code)`, `has(code)`, `add_new(entry)`; индекс в `VectorIndex`
- `FieldBlocklist`: `add_entry`, `is_blocked(name: str)` (normalised)
- `FieldResolver`: `resolve(characteristic: str) -> CharacteristicMatch` (по spec §3.11): `vector.search` → `match_score >= threshold` → existing; иначе `is_blocked` → discard; else → `create_new_field` (slugified name), `is_new_field=True`, persist. Возвращает match_result + resolved code.

### 6.5 `vector_index.py`
`VectorIndex` Protocol: `embed(text) -> list[float]`, `add(key, vec) -> None`, `search(vec, k) -> list[(key, score)]`.
Реализация `InMemoryVectorIndex` с возможность подключения локального embedder (sentence-transformers/multilingual-e5). При недоступности embedder — `LexicalIndex` (token-overlap/rapidfuzz с нормализацией). Graceful degradation.

### 6.6 `catalog_store.py`
`CatalogStore` для персистентности `FieldCatalog` и `FieldBlocklist` на диск (atomic write: write→rename, JSON). Тредобезопасность не критично; версионирование каталога (`catalog_version`).

### 6.7 `confidence.py`
`ConfidenceCalculator`:
- `candidate_conf(c: AttributeCandidate)` → confidence
  - structured/rule → `deterministic_confidence`
  - ner → `ner_score` (требуется присутствие; если нет — low_confidence или взять константу с логгированием warning)
- пороги `AUTO_THRESHOLD`, `REVIEW_THRESHOLD`
- статус карточки, `needs_review`, `low_confidence_count`, `coverage` по required-атрибутам схемы

## 7. Extractors

### 7.1 `extractors/base.py` (минимальная правка)
Сохранить интерфейс. Для новой архитектуры экстракторы возвращают `CharacteristicCandidate` (service-internal). Поэтому BaseExtractor → обобщённый тип (вариант с внутренним типом). Но чтобы не ломать тесты скелетов, временно позволяем возвращать list; в реализации — перейти на внутренний тип. Иначе следуем spec §3.1 в финальном слое. Описание решения: используем внутренний DTO (преобразуемся на границе этапа 5/6), не переписывая BaseExtractor сигнатуру радикально.

### 7.2 `extractors/structured.py` (новый)
Priority 0. Разбор `seller_attributes`:
- dict[str, Any]: пар ключ-значение
- list[Any]: элементы с ключами `key`/`name`/`attr` и `value`
- восстановить в `key → value`
Ключ = характеристика (неизвестный код) → `CharacteristicCandidate(method=structured, characteristic=key, raw_value=value, source_spans` указывают `SELLER_ATTRIBUTES` с текстом пары или ключа).

### 7.3 `extractors/rule.py` (рефакторинг)
Priority 1. Стратегии по кодам целевого домена (`brand`, `model`, `color`, `storage`, `diagonal`, `battery_capacity`, `ram`, `drive`, `processor`). Реализовать: парсинг с единицами, ключевые фразы, бренды с word-boundary, модель (после бренда/паттерн). Возвращает `CharacteristicCandidate` с `attribute_code` известен (rule-ветка) или `AttributeCandidate`-стиль; унифицируем через внутренний DTO.
Также метод `extract_for_missing(required_codes, text, schema)` для stage 7 (rules-fallback) — возвращает кандидатов только по указанным кодам, не дублируя существующие.

### 7.4 `extractors/ner.py` (рефакторинг)
Priority 10. Загрузка токен-классификатора: метки `CHARACTERISTIC` и `PROPERTY`. Предсказания с `ner_score` на сущность. Пейринг `PROPERTY` → ближайшая `CHARACTERISTIC` в пределах окна (`NER_PAIR_WINDOW` или предложение). Для пары → `characteristic=CHARACTERISTIC.text`, `raw_value=PROPERTY.text`, `method=ner`, `ner_score=PROPERTY.prob` (или среднее), `source_spans` включают оба.

Graceful: модель не загружена → пустой список, предупредительный лог.

### 7.5 Удаление
`dictionary.py`, `classifier.py`, `transformer.py`, `llm.py`. Обновить `extractors/__init__.py`, `extractors/registry.py` (default registry содержит structured/rules/ner). Убрать из build_default_registry и экспортов.

## 8. Корневые модули (existing → рефакторинг)

### 8.1 preprocessing.py
- Ввести чистку HTML (если нет в cleaning.py, добавить). Интегрировать `strip_html`, убрать мусор, сжать пробелы.
- `PreprocessedCard` расширить: `clean_title`, `clean_description`, `clean_text_full` (title+description+seller_attributes string), `tokens`, `language`.
- Определение языка — без изменений. Seller_attributes чистятся (str) перед merge.

### 8.2 normalization.py
- Убрать penalty-логику `enum_out_of_vocab` (штраф не применяется по новой модели). Enum вне vocab при `enum_strict=False` → оставить без штрафа, но с трассировкой в features? Однако новый дизайн не штрафует; просто нормализуем/оставляем как есть с `low_confidence` может выставляться позже. Подогнать под D6: попытка маппинга; при неуспехе — кандидат может быть маркирован, но штраф не добавлять.
- Единицы: унификация, форматирование (число + каноническая единица). Конверсия по `UnitRule` (пересчёт к `to_unit`) — оставить.
- Синонимы из `synonyms_map`.

### 8.3 grounding.py
- Hard filter: только кандидаты с `is_confirmed_in_text=True`. Проверка по `evidence_text` и по токенам `normalized_value`. Учет `6,7`↔`6.7`, единиц (`ГБ`↔`GB`) — оставить текущую логику канонизации.
- При отсутствии `source_spans` добавлять найденный span.
- `evidence_text` должен быть подтверждён в очищенном тексте.

### 8.4 merging.py
- Убрать метод-агрегация с весами. Правило по spec §8: группировка по `attribute_code`. Одинаковое `normalized_value` → объединить (лучший по confidence, объединить spans). Разные → выбрать максимум confidence, `needs_review=True`. Если `allow_multiple==false` → лучшее.
- Удалить `method_weights`, `conflicting_values_penalty`, `MERGED_METHOD=HYBRID`, взвешенное усреднение.
- Убрать штраф-конфликт (просто выставить `needs_review`, при необходимости добавить флаг в features).

### 8.5 references.py
- Сохранить `AttributeVocab`, `UnitRule`, `BrandVocab`, `ReferenceCatalog`. Добавить интерфейс `persist/load` при необходимости (не критично). Версии.

## 9. Pipeline orchestrator

### 9.1 `pipeline.py`
Класс `AttributeExtractionPipeline` с DI:
- `preprocessor`, `registry` (экстракторы structured/rule/ner), `field_resolver`, `normalizer`, `merger`, `grounding`, `confidence`, `catalog_store`, `settings`
- Метод `extract(card: ProductCard) -> ExtractionResult`
- Метод `extract_batch(cards: list[ProductCard]) -> list[ExtractionResult]`

Реализация этапов:
- 0–1: preprocess + schema
- 2: `StructuredExtractor.extract` → internal candidates
- 3: `RuleExtractor.extract` → internal
- 4: `NERExtractor.extract` → internal
- 5: `FieldResolver.resolve` по unresolved → заполняет `attribute_code`, `match_score`, `is_new_field`; сохраняет новые поля в `catalog_store` (persist). Отбрасывает заблокированные.
- 6: конвертация в `AttributeCandidate` (или использовать промежуточный слой), `ValueNormalizer.normalize_all`
- 7: найти обязательные коды схемы без кандидатов → `RuleExtractor.extract_for_missing` → stage 5+6 для них
- 8: merge
- 9: grounding (hard filter)
- 10: confidence → статус, counts, needs_review
- 11: assemble

Тайминги по этапам в `processing_time_ms` (optional). Логи структурные (candidates counts, new_fields, blocked, degraded).

Graceful degradation: NER недоступен → warning, пропускаем 4. VectorIndex недоступен → fallback на точное совпадение? Или `FieldResolver` переключается в режим exact-name match. Реализовать оба пути.

## 10. Main / API

`main.py`: оставить фабрику `create_app()`, `/health`. Расширение `/health` с `models_loaded` (per api_contract §4.2: `["structured", "rules", "ner", "vector_index"]`) — когда будет подключён пайплайн. Если не подключаем extract-эндпоинты в extractor (см. api_gateway), оставить минимально.

## 11. Тесты

### 11.1 Существующие тесты — обновить/удалить
- `test_attribute_extractor_config.py`: удалить проверки `method_weights`, `llm_*`, `enable_llm`; добавить проверки `match_threshold`, `deterministic_confidence`, путей, threshold order.
- `test_attribute_extractor_extractors.py`: default registry содержит `structured, rule, ner`? По spec: structured (priority 0), rule (1), ner (10). Удалить dict/classifier/transformer/llm проверки. Обновить names/priorities.
- `test_attribute_extractor_merging.py`: удалить весовую агрегацию, штрафы, `MERGED_METHOD=HYBRID`. Новый сценарий: merge by code, conflict → needs_review.
- `test_attribute_extractor_grounding.py`, `preprocessing.py`, `normalization.py`, `references.py`, `health.py` — пересмотреть под новые требования, не ломать без необходимости.

### 11.2 Новые тесты (минимум, согласно spec §7)
- Чистка текста: HTML, мусор, кавычки, тире, пробелы.
- StructuredExtractor: dict/list, резолв поля через векторный матч, нормализация значения.
- RuleExtractor: парсинг единиц, шаблоны, brand/model с boundaries, numeric formats.
- NERExtractor: 2 метки, пейринг `PROPERTY`↔`CHARACTERISTIC`, `ner_score`.
- FieldResolver: матч по порогу, ниже → новое поле, блоклист.
- Normalizer: unit-rules, синонимы, enum, форматирование.
- Grounding: `6,7` vs `6.7`, GB↔ГБ, hard-filter.
- Merger: группировка по коду, max confidence, конфликт → `needs_review`.
- Confidence: `DETERMINISTIC_CONFIDENCE` для structured/rule, `ner_score` для ner, пороги, статусы.
- Integration: полный путь, rules-fallback закрывает только оставшиеся обязательные, авто-добавление с блоклистом, graceful degradation (NER/вектор индекс недоступны), grounding hard filter.

## 12. Данные/артефакты

**Не генерируем датасет в код.** Необходимы артефакты (создаются вне сервиса):
- `FieldCatalog` (из 10 708 имён атрибутов + 9 целевых кодов), `FieldBlocklist` (стоп-слова из EDA) — сохраняем в `data/` (gitignored, кроме пустого шаблона). Path из конфига.
- NER-модель (HF/ONNX) в `models/ner/` (gitignored).
- `Embedding` модель опц.

## 13. Шаги выполнения (порядок в коде)

1. Редактировать `constants.py` и `config.py` под новый дизайн.
2. Создать модули `cleaning.py`, `slugify.py`, `candidates.py`, `fields.py`, `vector_index.py`, `catalog_store.py`.
3. Расширить `preprocessing.py` (чистка).
4. Создать `extractors/structured.py`, переработать `extractors/rule.py`, `extractors/ner.py`; удалить устаревшие extractors; обновить `registry/__init__`.
5. Обновить `normalization.py`, `grounding.py`, `merging.py`, `references.py`.
6. Создать `confidence.py`, `pipeline.py`.
7. Переработать `main.py` (минимум).
8. Обновить тесты: `test_attribute_extractor_config.py`, `test_attribute_extractor_extractors.py`, `test_attribute_extractor_merging.py`; добавить новые unit/integration для новых модулей.
9. Выполнить `uv run pytest services/attribute_extractor` (root/в workspace) — базовая валидация.

## 14. Риски и вопросы

- **Интерфейс экстракторов**: BaseExtractor возвращает list[AttributeCandidate] по spec §3.1, а structured/ner нуждаются в pre-resolution. Решение: хранить характеристику в `features["characteristic"]` или использовать внутренний `CharacteristicCandidate` + адаптация. Предлагается второй вариант (типизации + понятность), но тривиально держим внутри pipeline без изменения публичного базового интерфейса? Или конвертируем сразу.
- **Rules-fallback** (stage 7): какие поля считать «обязательными»? Брать из `CategorySchema.required_attributes`. Для generic-схемы список пустой — значит fallback не запускается.
- **Модель not found (NER/embeddings)**: graceful degradation. Не падать в health? `models_loaded` отражает фактическую загрузку.
- **Персистентность каталога**: нужно ли авто-применение новых полей к будущим запросам (persist) — да, per spec §11 D11. Учитывать многопоточность? MVP файл.
- **Пороги**: spec указывает `AUTO=0.80`, `REVIEW=0.60`. Синхронизировать с `ConfidenceConfig`.
- **Grounding в seller_attributes**: `seller_attributes` уже структурированы — по идее `structured` кандидаты должны быть подтверждены (grounding true). Проверка осуществляется.
- **Color 16.8%** — сознательно не решается архитектурно (trade-off).

## 15. Критерии приёмки

- Единое extract-поведение покрывает этапы 0–11 per spec.
- `extraction_method ∈ {structured, rule, ner}`.
- `confidence` — `ner_score` для ner; константа для structured/rule. Без взвешенной агрегации/штрафов.
- Grounding — hard-filter.
- Авто-добавление с блоклистом; `is_new_field` корректно выставляется.
- Rules-fallback заполняет только незакрытые обязательные поля.
- Тесты конфига/экстракторов/мерджа обновлены; базовый пайплайн-тест проходит.
- `uv run pytest services/attribute_extractor` зелёный (без регрессий имеющихся рабочих тестов, с правками по новой модели).

## 16. Комментарий

План написан строго под `services/attribute_extractor` (scope = only extractor). При реализации критичных отклонений от spec (интерфейс DTO) — зафиксировать в commit/body и обосновать, не меняя сами спецификации без явного разрешения.