# Спецификация: Модуль извлечения атрибутов (Attribute Extractor)

## 1. Назначение

Специфицировать ядро пайплайна извлечения характеристик товаров из текста карточки (title, description). Модуль отвечает за очистку текста, извлечение, нормализацию, валидацию grounding, расчёт уверенности и формирование структурированного результата.

Пайплайн построен как **целевой гибрид без LLM**: детерминированные правила на ядре, NER-трансформер на длинном хвосте и векторное сопоставление характеристик с каталогом полей. Генеративные модели не используются; главный инвариант — «не выдумывать характеристики». Характеристики, указанные продавцом только в структурированных полях (seller_attributes), не являются входом: вход ограничен заголовком и описанием.

## 2. Область применения

**Вход:** текст карточки товара (title, description). **Выход:** JSON со списком выделенных атрибутов, где для каждого указаны `attribute_code`, `normalized_value` (каноническое значение) и `confidence` (уверенность).

Путь пайплайна:

```
карточка
  → Этап 0. Чистка и препроцессинг
  → Этап 1. Резолв схемы категории
  → Этап 2. (удалён: seller-атрибуты не являются входом пайплайна)
  → Этап 3. Ядро правил (title/description)
  → Этап 4. NER (характеристика + свойство)
  → Этап 5. Резолв поля (векторный матч + блоклист)
  → Этап 6. Нормализация значений
  → Этап 7. Rules-fallback (незакрытые обязательные поля)
  → Этап 8. Мёржа и дедупликация
  → Этап 9. Grounding
  → Этап 10. Уверенность, пороги, статус
  → Этап 11. Формирование результата
```

## 3. Интерфейсы и контракты

### 3.1 Интерфейс экстрактора

```python
from abc import ABC, abstractmethod

from specflow_contracts import AttributeCandidate, CategorySchema, ProductCard


class BaseExtractor(ABC):
    name: str
    priority: int  # lower = run earlier

    @abstractmethod
    def extract(
        self, card: ProductCard, schema: CategorySchema
    ) -> list[AttributeCandidate]:
        """Извлечь кандидатов атрибутов для карточки в рамках схемы категории."""
        raise NotImplementedError
```

**Требования:** каждый экстрактор возвращает список `AttributeCandidate`. Кандидаты из NER несут `ner_score`; кандидаты с незакреплённым кодом поля (NER-характеристика) разрешаются на Этапе 5.

### 3.2 Правила и NER

- **RuleExtractor (priority 0)** — регулярные выражения и близость ключевых слов для целевых полей (`brand`, `model`, `diagonal`, `storage`, `ram`, `battery_capacity`, `drive`, `processor`, `color`). Возвращает код поля напрямую. `extraction_method='rule'`.
- **NERExtractor (priority 10)** — multilingual encoder, token-classification с двумя метками `CHARACTERISTIC` и `PROPERTY`; спаны пейрятся в пределах окна. `extraction_method='ner'`, `ner_score` — entity-level вероятность.

### 3.3 Резолв поля

```python
class VectorIndex(Protocol):
    def embed(self, text: str) -> list[float]: ...
    def add(self, key: str, vector: list[float]) -> None: ...
    def search(self, vector: list[float], k: int) -> list[tuple[str, float]]: ...
```

- **FieldCatalog** — каталог канонических полей (код, `name_ru`, синонимы, `value_type`, `unit`, флаг `is_new_field`), индексируется в `VectorIndex`.
- **FieldBlocklist** — множество стоп-слов/шаблонов служебных «атрибутов» (выведено из EDA: «Подборки», «Продавец», BI-поля, «Гарантия предоставляется», «Потратить бонусы» и т.п.).
- **FieldResolver** — сопоставляет характеристику с каталогом: `match_score` = близость к ближайшему полю; `>= MATCH_THRESHOLD` → существующий код; иначе проверка по блоклисту и (при отсутствии шума) авто-добавление нового поля.

### 3.4 DTO

Используются доменные сущности (domain-model.md): `ProductCard`, `AttributeCandidate`, `ExtractionResult`, `CategorySchema`, `Span`, `FieldCatalog`, `VectorIndex`, `FieldBlocklist`, `CharacteristicMatch`, `NewField`.

## 4. Этапы пайплайна (детально)

### Этап 0. Чистка и препроцессинг

- **Сбор текста:** `raw_text` из `title`, `description` с метками секций («Заголовок:»/«Описание:», метки задаются константами контракта) — бренд и модель почти всегда живут в заголовке, поэтому заголовок отличим от описания в едином тексте.
- **Очистка (обязательно):** снятие HTML-тегов, удаление служебных вставок и водяных знаков, мусорных/невидимых символов, унификация кавычек, тире и переносов, сжатие пробелов. Обоснование: 49,3% описаний с HTML и служебный шум (EDA).
- **Язык:** автоопределение (ru/en/mixed) — для словарей и нормализаторов; при наличии `card.language` используется он.
- **Токенизация:** whitespace — для правил, токенизатор модели — для NER.
- **Правило:** очистка не изменяет содержательные значения; она улучшает вход для правил и NER.

### Этап 1. Резолв схемы категории

- Загрузка `CategorySchema` по `category_id`/`category_name`; fallback — generic-схема. Обязательные атрибуты схемы управляют rules-fallback (Этап 7).

### Этап 2. Удалён (seller-атрибуты не являются входом)

Этап убран решением команды: характеристики извлекаются только из заголовка и описания; seller-атрибуты остаются в контракте `ProductCard` для обратной совместимости, но пайплайном не используются. Нумерация этапов сохранена ради стабильности ссылок (Этапы 3–11).

### Этап 3. Ядро правил (title/description)

- Регулярные выражения для числовых значений с единицами: диагональ (`(\d+[.,]?\d*)\s*(дюйм|inch|"|″)`), память (`(\d+)\s*(ГБ|GB|ТБ|TB)`), ОЗУ, батарея (`(\d+)\s*(мА·ч|мАч|mAh)`), накопитель.
- Шаблоны ключевых фраз («цвет: чёрный») и близость ключевого слова к значению.
- Бренд/модель — по словарю брендов со границами слов.
- Код поля известен сразу. `extraction_method='rule'`.

### Этап 4. NER (характеристика + свойство)

- Многоязычный encoder (token-classification), метки `CHARACTERISTIC` (имя поля) и `PROPERTY` (значение).
- Пейринг `PROPERTY` ↔ ближайшая `CHARACTERISTIC` в пределах окна (предложение/контекст).
- `ner_score` — entity-level вероятность для извлечённой сущности.
- Характеристика разрешается в код поля на Этапе 5; `extraction_method='ner'`.
- NER применяется к свободному тексту (title/description); правила и NER не дублируют друг друга без явной причины.

### Этап 5. Резолв поля (векторный матч + блоклист)

- Для кандидатов без кода поля (NER-характеристики): `match_score` = близость характеристики к ближайшему полю `FieldCatalog` через `VectorIndex`.
- `match_score >= MATCH_THRESHOLD` → существующий `attribute_code`; `match_score` сохраняется в кандидате для трассировки.
- `match_score < MATCH_THRESHOLD`:
  - характеристика в `FieldBlocklist` → кандидат отбрасывается (шум);
  - иначе → **авто-добавление нового поля** в `FieldCatalog` (код генерируется слагификацией нормализованной характеристики), `is_new_field=true`.
- `match_score` **не входит** в `confidence` (см. Этап 10): это маршрутизация, а не оценка достоверности значения.

### Этап 6. Нормализация значений

- Базовая: trim, сжатие пробелов, нормализация кавычек/дефисов.
- Синонимы: `synonyms_map` alias→canonical (`алый` → `красный`, `red` → `красный`).
- Единицы измерения: унификация сокращений (`ГБ/Гб/GB`, `ТБ/TB`, `дюйм/"/″/inch`, `мАч/mAh`), приведение к канонической единице схемы, единообразный формат чисел (`8GB`/`8128 МБ` → `8 ГБ`).
- Регистр: бренды — канонический из словаря, enum — канонический из `vocab`, остальное — по правилам.
- Enum-валидация: `value_type == 'enum'` → значение должно быть в `vocab`; иначе попытка маппинга, при неуспехе — `low_confidence`.
- `unit_value`: парсинг числа+единицы, нормализация, форматирование (`256 ГБ`, `6,7 дюйма`, `5000 мА·ч`).

### Этап 7. Rules-fallback (незакрытые обязательные поля)

- Детерминированные правила выполняются как fallback: заполняют **только** те обязательные поля схемы, которые не закрыли NER-путь.
- `extraction_method='rule'`, `confidence=DETERMINISTIC_CONFIDENCE`.

### Этап 8. Мёржа и дедупликация

- Группировка кандидатов по `attribute_code`.
- При одинаковом `normalized_value` — объединение (оставляем лучший по confidence, сохраняем спаны).
- При разных `normalized_value` для одного кода — оставляем кандидата с максимальным confidence, `needs_review=true`.
- `allow_multiple == false` → оставить лучшее значение.

### Этап 9. Grounding (обязательный фильтр)

- **Hard constraint:** для всех финальных кандидатов `is_confirmed_in_text == true`.
- Проверка: `evidence_text`/ключевые токены присутствуют в `title`/`description` очищенной карточки (case-insensitive, нормализация пробелов, числовое/единичное совпадение `6,7` vs `6.7`, `ГБ` vs `GB`, `128GB` vs `128 ГБ`) и синонимия цветов (`Black` подтверждает канон «черный»). Кандидаты, существующие только в seller-атрибутах и отсутствующие в тексте, не подтверждаются.
- Кандидаты без подтверждения **отбрасываются**. Сохраняется минимум один `source_spans`.

### Этап 10. Уверенность, пороги, статус

- **Уверенность:**
  - `rule` → `DETERMINISTIC_CONFIDENCE` (константа, по умолчанию 0.9);
  - `ner` → `ner_score`;
  - `match_score` — только трассировка, в `confidence` не входит.
- **Пороги:** `AUTO_THRESHOLD = 0.80`, `REVIEW_THRESHOLD = 0.60`.
- **Логика статуса:**
  - `confidence >= AUTO_THRESHOLD` → `needs_review=false`, `status='ok'`;
  - `REVIEW_THRESHOLD <= confidence < AUTO_THRESHOLD` → `needs_review=true`, `status='low_confidence'`;
  - `confidence < REVIEW_THRESHOLD` → `needs_review=true`, `status='low_confidence'`;
  - обязательный атрибут отсутствует → `status='partial'`, `needs_review=true`;
  - ошибка → `status='error'`; без схемы/пропущено → `status='skipped'`.
- **Coverage:** доля обязательных атрибутов категории, извлечённых с `confidence >= REVIEW_THRESHOLD`.

### Этап 11. Формирование результата

- `ExtractionResult.attributes` = финальный список (отсортирован по `attribute_code`).
- Заполнить `pipeline_version`, `processing_time_ms`, `low_confidence_count`, `needs_review`, `status`.
- Обязательные поля каждого атрибута: `extraction_method`, `is_confirmed_in_text=true`, `normalized_value`, `confidence`, `source_spans` (>=1).

## 6. Обработка граничных случаев

| Случай | Поведение | Статус |
| --- | --- | --- |
| Текст пустой/недостаточный | Нет возможности подтвердить значения. Пустой список, `needs_review=true`. | `skipped` |
| Текст содержит HTML/служебные вставки | Очистка на Этапе 0, значения ищутся в очищенном тексте. | `ok` |
| Категория не определена | Generic-схема; `category_id/category_name` из входа при наличии. | `ok`/`partial` |
| Схема категории отсутствует | Минимальная схема по умолчанию, обработка не блокируется. | `partial` |
| Характеристика не сопоставлена (`match_score < MATCH_THRESHOLD`), не шум | Авто-добавление нового поля (`is_new_field=true`), кандидат возвращается. | `ok` |
| Характеристика в блоклисте (служебный «атрибут») | Кандидат отбрасывается как шум. | фильтруется |
| Атрибут встречается несколько раз с разными значениями | Оставляем max confidence, `needs_review=true`. | `low_confidence` |
| Значение в тексте, но не в vocab (enum) | Попытка маппинга через `synonyms_map`; при неуспехе — `low_confidence`. | `low_confidence` |
| Числовой диапазон («128–256 ГБ») | Парсинг по правилам; при неоднозначности — извлечённое явно либо `low_confidence`. | `low_confidence` при неоднозначности |
| Смешанные единицы (дюймы/мм, ГБ/ТБ) | Unit-rules приводят к канонической единице. | `ok`/`low_confidence` |
| Короткое упоминание («6.7» без «дюйм») | Требуется контекст; если правило/NER однозначно определяет поле — допустимо с пониженной уверенностью, иначе не включать. | `low_confidence` или отбрасывается |
| Синонимы/аббревиатуры («ОЗУ 8ГБ», «RAM 8GB») | Нормализация через синонимы и unit-rules. | `ok` |
| Англо-русский микс | Регистронезависимый поиск, двусторонние маппинги, словари брендов/enum. | `ok` |
| NER-модель не загружена | Fallback на правила; предупреждение, продолжение работы. | `ok`/`partial` |
| Векторный индекс недоступен | NER-характеристики без матча: при недоступности — fallback на правила и точное совпадение по имени поля. | `partial` |
| Множественные кандидаты от разных путей | Мёржа по `attribute_code`, выбор max confidence. | `ok` |

## 7. Тестирование модуля

### 7.1 Unit-тесты

- Cleaner: снятие HTML, удаление служебных вставок/водяных знаков, мусорных символов, нормализация кавычек/тире/пробелов.
- RuleExtractor: парсинг единиц, шаблоны, boundary-aware, форматы чисел.
- NERExtractor: две метки, пейринг `PROPERTY`↔`CHARACTERISTIC`, `ner_score`, маппинг в код.
- FieldResolver/VectorIndex: матч по порогу, ниже порога → новое поле, блоклист отбрасывает шум.
- Normalizer: unit-rules, синонимы, enum-mapping, форматирование чисел+единиц.
- GroundingValidator: exact/normalized, числовое (`6,7` vs `6.7`), единичное совпадение.
- Merger: группировка по коду, выбор max confidence, конфликт → `needs_review`.
- Confidence: `DETERMINISTIC_CONFIDENCE`, `ner_score`, пороги, `needs_review`, `status`.

### 7.2 Integration-тесты

- Полный путь: clean → rules → NER → field resolution → normalize → fallback → merge → grounding → confidence.
- Rules-fallback закрывает только оставшиеся обязательные поля.
- Авто-добавление поля ниже порога и отбрасывание мусора по блоклисту.
- Graceful degradation: NER-модель/векторный индекс недоступны → fallback без падения.
- Батч: частично успешный батч не прерывает остальные.
- Grounding hard-filter: кандидат без подтверждения отбрасывается.

### 7.3 Contract-тесты

- Соответствие `AttributePrediction`/`ExtractionResponseItem` (api_contract.md).
- Обязательные поля: `attribute_code`, `normalized_value`, `confidence`, `extraction_method`, `is_confirmed_in_text`.
- `confidence` ∈ [0.0,1.0]; `is_confirmed_in_text == true` во всех финальных атрибутах.
- `extraction_method ∈ {rule, ner}` в финальных атрибутах (значений `structured` не возникает).

### 7.4 Приёмочные тест-кейсы

- Смартфон: бренд, модель, объём памяти, диагональ экрана, ёмкость батареи, цвет.
- Ноутбук: бренд, процессор, объём ОЗУ, накопитель, диагональ экрана, цвет.
- Редкая категория: проверка без массовых правил, NER и векторный матч закрывают хвост.
- Длинный хвост: редкие значения, синонимы, аббревиатуры.
- Микс RU/EN: корректная нормализация.
- Грязный ввод: HTML и служебные вставки не портят извлечение.

## 8. Метрики качества модуля

| Метрика | Описание | Способ расчёта |
| --- | --- | --- |
| Precision | Доля корректно извлечённых среди извлечённых | TP/(TP+FP) по (product_id, attribute_code) на эталоне |
| Recall | Доля корректно извлечённых среди истинных | TP/(TP+FN) по (product_id, attribute_code) на эталоне |
| F1 | Гармоническое среднее P/R | 2*P*R/(P+R) |
| Accuracy (per-attribute) | Корректность по конкретному атрибуту | Отдельно по каждому атрибуту |
| Coverage | Доля карточек, в которых атрибут заполнен | (карточки с атрибутом) / (всего карточек) |
| ExactMatch | Строгое совпадение `normalized_value` с эталонным | 1/0 |
| SoftMatch | Мягкое совпадение (синонимы, эквивалентные единицы) | 1/0 по правилам |
| % ниже порога (needs_review) | Доля предсказаний с `confidence < AUTO_THRESHOLD` | Нагрузка на ручную проверку |
| % отфильтровано grounding | Доля кандидатов, отброшенных GroundingValidator | Контроль жёсткости фильтра |
| Доля новых полей | Доля кандидатов с `is_new_field=true` | Контроль дрейфа каталога |
| Coverage по required-атрибутам | Покрытие обязательных атрибутов категории | Среднее/по категории на gold-сете |
| Качество по категориям (stratified) | Оценка отдельно по каждой категории | Stratified по `category_name/id` |
| Weighted by traffic | Метрики, взвешенные по трафику фильтрации атрибута | При наличии статистики трафика |

**Правила валидации:** сравнение по `normalized_value`; учитывать `allow_multiple` (матч по пересечению); grounding-фильтр не должен искусственно завышать Precision без учёта Recall; метрики — отдельно по каждому атрибуту; настройка порогов и оценка — только на gold-наборе (см. design.md, «Данные и ML-методология»).

## 9. Мониторинг, логирование, трассировка

### 9.1 Логирование

- Уровни: INFO (этапы), DEBUG (детали кандидатов), WARNING (fallbacks/degraded), ERROR (failures).
- Структурные логи (JSON): `product_id`, `category`, `pipeline_version`, `stages`, `methods_used`, `candidates_before_grounding`, `candidates_after_grounding`, `new_fields`, `blocked_fields`, `processing_time_ms`, `needs_review`.
- Без PII: не логировать полный сырой текст; допустимы `text_hash`, длина, первые N символов title.

### 9.2 Метрики (runtime)

- `extract_requests_total{method="single|batch"}`
- `extract_duration_ms{stage="clean|rules|ner|resolve|normalize|fallback|merge|grounding|total"}`
- `candidates_total{method,attribute_code}`
- `vector_match_total{outcome="existing|new|blocked"}`
- `new_fields_total{attribute_code}`
- `grounding_filtered_total{reason}`
- `low_confidence_total{attribute_code,threshold}`
- `needs_review_ratio`
- `coverage_by_attribute{attribute_code,category}`
- `degraded_mode{component="ner|vector_index"}`

### 9.3 Трассировка

- `pipeline_version` в каждом ответе API.
- `extraction_method`, `ner_score`, `match_score`, `is_new_field`, `source_spans`, `evidence_text` для каждого финального кандидата.
- Тайминги по этапам.
- Версии компонентов: `ner_model_version`, `field_catalog_version`, `vocab_version`, `rules_version`.

### 9.4 Алерты (рекомендуемые)

- Резкий рост `needs_review` (>X%) за окно.
- Рост доли новых полей (дрейф каталога).
- Рост `degraded_mode` (недоступность NER/векторного индекса).
- Падение coverage по required-атрибутам ключевых категорий.
- Долгая инициализация моделей/индекса при старте.

## 10. Принципы реализации

- **Чистка — первый этап:** любой входящий текст очищается до извлечения.
- **Целевой гибрид:** правила (ядро) → NER (хвост) → векторный матч (канон полей) → нормализация → rules-fallback.
- **Grounding как инвариант:** никогда не выпускать кандидата с `is_confirmed_in_text == false`.
- **Determinism:** rules детерминированы; для NER фиксируются версия модели и параметры.
- **Простая уверенность:** `rule` → константа, `ner` → `ner_score`; никаких весов методов, штрафов и взвешенной агрегации.
- **Fail-safe:** graceful degradation, partial results в батче, ошибки элемента не валят батч.
- **Traceable:** каждый финальный атрибут несёт `extraction_method`, `confidence`, `source_spans`, `evidence_text`.
- **Тестируемо:** чистые интерфейсы, DI, конфиг через `Pydantic Settings`.
- **Обратная совместимость:** `pipeline_version` растёт при изменении логики нормализации/порогов/резолва полей.
- **Не выдумывать:** NER + grounding — главный защитный барьер; LLM не используется.
- **Единообразие:** `attribute_code` в snake_case, `normalized_value` в каноническом формате.
