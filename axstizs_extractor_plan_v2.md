# План реализации NER и эмбеддингов для attribute_extractor

## 1. Цель
Сфокусироваться только на **NER** и **эмбеддингах/векторном индексе** для соответствия новой спеке.
Рабочий минимум: 
- NER с двумя метками `CHARACTERISTIC` и `PROPERTY`, пейринг в окне
- `VectorIndex` (абстрактный интерфейс) + MVP-реализация с graceful degradation
- интеграция в текущую архитектуру модуля attribute_extractor (минимальные правки)

## 2. Понятный вход и выход
**Вход:** очищенный текст карточки (`title`, `description`), `seller_attributes` (для weak-датасета).
**Выход (для NER):** список пар `(CHARACTERISTIC span, PROPERTY span)` с `ner_score`.
**Выход (для VectorIndex/FieldResolver):** `match_score` при сопоставлении характеристики с `FieldCatalog`; при недоступности эмбеддингов — lexical fallback (точное совпадение + мягкое).

## 3. Что трогаем (только это)
- `services/attribute_extractor/src/attribute_extractor/extractors/ner.py` — переписать (реализация + загрузка модели + пейринг)
- `services/attribute_extractor/src/attribute_extractor/vector_index.py` — новый (Protocol + InMemoryVectorIndex + Lexical fallback)
- `services/attribute_extractor/src/attribute_extractor/fields.py` — FieldResolver + FieldCatalog/FieldBlocklist (минимум для работы резолва)
- `services/attribute_extractor/src/attribute_extractor/constants.py` — добавить NER/Vector константы
- `services/attribute_extractor/src/attribute_extractor/config.py` — добавить пути/параметры
- `services/attribute_extractor/src/attribute_extractor/catalog_store.py` — персистентность FieldCatalog/FieldBlocklist
- `services/attribute_extractor/src/attribute_extractor/slugify.py` — для авто-добавления полей
- `services/attribute_extractor/tests/test_attribute_extractor_ner.py` — новый тест (минимум)
- `services/attribute_extractor/tests/test_attribute_extractor_vector_index.py` — новый тест (минимум)

Остальное (structured/rule/merging/grounding/confidence/pipeline) не трогаем прямо сейчас.

## 4. NER
### 4.1 Модель и метки
- Метки: `CHARACTERISTIC`, `PROPERTY` (BIO или обычные span-метки)
- Encoder: мультиязычный (XLM-RoBERTa-base/distil-модель). Загрузка лениво с graceful degradation.
- Путь: `models/ner/` (HF или директория с `config.json`, `tokenizer`, `model`)

### 4.2 Weak-датасет (distant supervision)
Источники: `EDA/dataset/sku_desc.parquet`, `EDA/dataset/skus.pkl`. Join по `sku_id`.
Алгоритм:
1. Взять пары key→value из `seller_attributes`
2. Искать значение `value` в очищенном `title`/`description` (нормализация: case-insensitive, кавычки/тире/пробелы, GB↔ГБ, 6,7↔6.7)
3. При совпадении пометить спан значения как `PROPERTY`, ближайший контекст-ключ как `CHARACTERISTIC`
4. Сохранить пары `(characteristic_span, property_span, text, window)`

Фильтры: блоклист шум-ключей из EDA, исключить неоднозначные множественные совпадения, слишком короткие спаны.

Формат вывода: `data/ner/weak.jsonl` или CoNLL (фиксируем перед обучением). **Тяжёлое не коммитим**.

### 4.3 Инференс и пейринг
- Предсказываем спаны `CHARACTERISTIC`/`PROPERTY` с `score`
- Пейринг: для каждого `PROPERTY` ищем ближайшую `CHARACTERISTIC` в пределах окна (по умолчанию 32 токена/предложение). Ближайшая по расстоянию.
- Возвращаем список пар с `ner_score = property_score` (или среднее). Храним `source_spans` для обоих.

### 4.4 Модуль ner.py
Класс/функции:
- `NERModel` (ленивая загрузка, `load()`, `predict(text) -> list[NERPair]`)
- `NERPair(characteristic_span, property_span, ner_score, source_spans)`
- `NERExtractor` (реализует интерфейс экстрактора) — возвращает кандидаты/characteristic-candidates согласно принятому в сервисе подходу (минимум: логика пейринга + graceful при отсутствии модели)

Graceful: модель отсутствует/не грузится → возвращает пустой список, логирует warning.

## 5. Эмбеддинги и VectorIndex
### 5.1 Интерфейс
```python
class VectorIndex(Protocol):
    def embed(self, text: str) -> list[float]: ...
    def add(self, key: str, vector: list[float]) -> None: ...
    def search(self, vector: list[float], k: int) -> list[tuple[str, float]]:  # (code, match_score)
```

### 5.2 Реализации
- `InMemoryVectorIndex` — хранит mapping key→vector. Embedder подключаемый.
- `LexicalVectorIndex` — fallback без эмбеддингов: нормализация, token-overlap + простой скоринг (Jaccard-подобный). Работает при недоступности embedder.

Embedder: `EmbeddingModel` Protocol. Опц. sentence-transformers (multilingual). Если недоступен — fallback на lexical.

### 5.3 FieldCatalog/FieldResolver (минимум)
- `FieldCatalogEntry` (code, name_ru, synonyms, value_type, unit, is_new_field)
- `FieldCatalog` — загрузка/сохранение, индексирование в VectorIndex
- `FieldBlocklist` — проверка шума
- `FieldResolver.resolve(characteristic)` → возвращает match: `matched_code or None`, `match_score`, `is_new_field`, `blocked`
  - blocked если в блоклисте
  - иначе поиск в VectorIndex: если `match_score >= MATCH_THRESHOLD` → существующий код
  - иначе → авто-добавление нового поля (slugify), `is_new_field=True`, persist в `FieldCatalog`

### 5.4 Константы/конфиг
constants.py: `MATCH_THRESHOLD=0.75`, `DETERMINISTIC_CONFIDENCE=0.90`, `AUTO_THRESHOLD=0.80`, `REVIEW_THRESHOLD=0.60`, `NER_LABEL_CHARACTERISTIC`, `NER_LABEL_PROPERTY`, `NER_PAIR_WINDOW=32`, пути `FIELD_CATALOG_PATH`, `FIELD_BLOCKLIST_PATH`, `NER_MODEL_PATH`, `VECTOR_K`, `VECTOR_BACKEND`, `MAX_NEW_FIELDS`.
config.py: добавить соответствующие поля + валидация.

catalog_store.py: атомарное сохранение `field_catalog.json`, `field_blocklist.txt`.

slugify.py: snake_case для новых кодов.

## 6. Порядок работы
1. constants/config + минимальные модули (slugify, catalog_store)
2. vector_index.py + fields.py (FieldResolver с lexical fallback)
3. ner.py (загрузка модели + пейринг + graceful)
4. weak-датасет скрипт `scripts/build_weak_ner.py` (отдельный, не коммитим тяжёлое) + формат
5. тесты vector_index и ner (минимум)
6. интеграция NERExtractor в registry (если уже есть) — минимальная правка

## 7. Критерии приёмки
- VectorIndex Protocol + InMemory + Lexical fallback работают; `match_score` в [0,1]
- FieldResolver: блоклист отбрасывает шум, ниже порога → новое поле с `is_new_field`, >= порога → существующий
- NER: пейринг CHARACTERISTIC↔PROPERTY в окне, `ner_score` проставлен
- Graceful degradation: без модели/без эмбеддингов пайплайн не падает
- Тесты `test_attribute_extractor_vector_index.py`, `test_attribute_extractor_ner.py` зелёные
- Ruff check проходит
