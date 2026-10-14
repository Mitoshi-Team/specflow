# Спецификация: Модуль извлечения атрибутов (Attribute Extractor)

## 1. Назначение
Специфицировать ядро пайплайна извлечения характеристик товаров из текста карточки (title, description, seller_attributes). Модуль отвечает за извлечение, нормализацию, валидацию grounding, расчёт уверенности и формирование структурированного результата. Реализуется по принципу гибридного каскада (rules-first, cheap-first) с жёстким требованием «не выдумывать характеристики».

## 2. Область применения
Пайплайн проходит путь: входная карточка → препроцессинг → извлечение кандидатами (экстракторы) → мёржинг → валидация (grounding) → нормализация → агрегация уверенности → фильтрация по порогам → выходной результат. Модуль является основным вычислительным компонентом бэкенда (Python + FastAPI).

## 3. Интерфейсы и контракты

### 3.1 Интерфейс BaseExtractor
```python
from abc import ABC, abstractmethod
from typing import List

class BaseExtractor(ABC):
    name: str
    priority: int  # lower = run earlier (rules first)

    @abstractmethod
    def extract(self, card: ProductCard, schema: CategorySchema) -> List[AttributeCandidate]:
        """Извлечь кандидатов атрибутов для карточки в рамках схемы категории."""
        raise NotImplementedError

    @abstractmethod
    def supports(self, attribute_code: str, category: str | None) -> bool:
        """Поддерживает ли экстрактор данный атрибут/категорию."""
        return True
```
**Требования**: каждый экстрактор возвращает список `AttributeCandidate` с заполненными `extraction_method`, `confidence`, `is_confirmed_in_text`, `source_spans`/`evidence_text` (где возможно).

### 3.2 Ключевые DTO (структуры)
Используются доменные сущности (domain-model.md): `ProductCard`, `AttributeCandidate`, `ExtractionResult`, `CategorySchema`, `Span`.

### 3.3 Регистрация экстракторов
`ExtractorRegistry` хранит список экстракторов, сортирует по `priority` (ascending). Порядок запуска по умолчанию: Rule(priority 0), Dict(1), NER(10), Classifier(20), Transformer(30), LLM(50) — конфигурируемо.

## 4. Этапы пайплайна (детально)

### Этап 0. Препроцессинг
- **Сбор текста**: `raw_text = " ".join(filter(None, [card.title, card.description, str(card.seller_attributes)]))`
- **Нормализация**: сжатие множественных пробелов, унификация переносов, удаление мусорных символов (опц.), нормализация кавычек.
- **Язык**: автоопределение (ru/en/mixed) — опц., влияет на словари/нормализаторы.
- **Токенизация**: базовая (whitespace) для rules/dicts, токенизация модели — для NER/Transformer.
- **Резолв схемы**: загрузка `CategorySchema` по `category_id/name` (fallback: generic schema).

### Этап 1. Rules + Dicts (ядро, детерминированное)
**RuleExtractor (priority 0)**:
- Регулярные выражения для числовых значений с единицами: диагональ (`(\d+[.,]?\d*)\s*(дюйм|inch|"|″)`), объём памяти (`(\d+)\s*(ГБ|Гб|GB|ТБ|Тб|TB)`), ОЗУ (`(\d+)\s*(ГБ|GB|RAM)`), ёмкость батареи (`(\d+)\s*(мА·ч|мАч|mAh|mA·h)`), накопитель и др.
- Шаблоны ключевых фраз («цвет: чёрный», «диагональ экрана — 6,7 дюйма»).
- Экстракция бренда/модели по маркерам (словари + контекст).
- Возвращает кандидатов с `extraction_method='rule'`, `confidence` 0.90–0.99 (высокая для точных шаблонов), `source_spans` по совпадению.

**DictExtractor (priority 1)**:
- Точный/частичный поиск по `synonyms_map` (alias→canonical) и `vocab` (enum). Приоритет точному совпадению (boundary-aware), затем словарному.
- BrandVocab: поиск бренда с boundary (слова), исключение стоп-слов, уменьшение ложных срабатываний.
- Цвет, материал, форм-факторы — enum-словари.
- `confidence` 0.92–0.98 (словари надёжны), `is_confirmed_in_text=true` при совпадении.

**Требования**: boundary-aware (не захватывать часть другого слова), регистронезависимый с учётом рус/англ, нормализация пробелов.

### Этап 2. ML-экстракторы (локальные)
**NERExtractor (priority 10)**:
- Token-level NER (BIO/BILOU) для сущностей: `BRAND`, `MODEL`, `STORAGE_GB`, `DIAGONAL_INCH`, `BATTERY_MAH`, `RAM_GB`, `DRIVE_GB`, `PROCESSOR`, `COLOR`.
- Предобработка под модель (сплиттер/токенизатор). Постобработка: склейка сущностей, валидация чисел+единиц, нормализация.
- `confidence` по softmax токенов (entity-level), типично 0.80–0.95.
- Обязателен маппинг в `attribute_code`.

**ClassifierExtractor (priority 20)**:
- Малый классификатор (logreg/mini-transformer) для неоднозначных enum-атрибутов (цвет при наличии нескольких кандидатов, тип корпуса) по контекстному окну вокруг упоминания.
- `confidence` = вероятность класса.

**TransformerExtractor (priority 30)**:
- Encoder (BERT/RoBERTa/ModernBERT) — sequence tagging (token classification) или extractive QA («какой объём памяти?») под схему категории.
- Сильнее на длинном хвосте, возвращает спаны + уверенность span-level.
- Локальный инференс, управляемая стоимость.

### Этап 3. LLM-экстрактор (резервный)
**LLMExtractor (priority 50)**:
- **Режим**: zero-shot/few-shot. Включается только если `ENABLE_LLM=true` и имеются незакрытые обязательные атрибуты схемы И/ИЛИ кандидаты с `confidence < threshold` после этапов 1–2.
- **Строгая схема вывода (JSON Schema)** — принудительная типизация. Обязательные поля: `attribute_code`, `raw_value`, `normalized_value`, `confidence` [0,1], `evidence_text` (обязателен), `source_field` (`title|description|seller_attributes`), `is_confirmed_in_text` (bool).
- **Hard constraints (промпт)**:
  - «Не выдумывай характеристики, которых нет в тексте карточки. Если атрибута нет — не указывай его».
  - «Для каждого значения ОБЯЗАТЕЛЬНО укажи точную цитату (`evidence_text`) — фрагмент исходного текста, который подтверждает это значение (grounding)».
  - «`is_confirmed_in_text` = true только если `evidence_text` дословно/по смыслу присутствует во входном тексте. Никогда не ставь true без подтверждения».
  - «Возвращай только значения, подтверждённые текстом. Не додумывай публично известные характеристики, не указанные продавцом, без прямого упоминания в тексте».
  - «Используй только коды атрибутов из переданной схемы категории».
  - «Приводи значения к каноническому виду (normalized_value), сохраняя единицы измерения по умолчанию схемы».
- **Параметры**: `temperature=0.0`, `top_p` ≤ 0.9 (фикс.), `max_tokens` достаточный для схемы, `response_format: json_schema` (strict).
- **Пост-валидация LLM-ответа**: проверка JSON Schema, валидация `is_confirmed_in_text==true` и что `evidence_text` содержится в соответствующем `source_field` входного текста (exact/normalized substring). Кандидаты, не прошедшие grounding — отбрасываются. Также проверка соответствия vocab (enum) — при выходе → confidence penalty/low_confidence.
- `extraction_method='llm'`, confidence калибруется.
- **Правило активации LLM (gate)**: не вызывать для каждой карточки по умолчанию. Активация по условию: есть незакрытые `required_attributes` категории ИЛИ кандидаты с `confidence < default_threshold` после этапов 1–2. Глобальный флаг `ENABLE_LLM`.

### Этап 4. Candidate Merging (объединение кандидатов)
- Группировка по `(attribute_code, normalized_value)`. При равных — сливаем.
- При разных `normalized_value` для одного `attribute_code` (конфликт): приоритет grounded + вес метода (rule/dict > NER/Trans > LLM), при обоих grounded — не объединяем, понижаем confidence, возможен `needs_review=true`.
- **Взвешенная агрегация confidence** при слиянии: `conf_agg = (∑ w_m * conf_m * g_m) / (∑ w_m * g_m)`, где `g_m=1.0` если `is_confirmed_in_text` true.
- **Метод-веса (рекомендуемые)**: `rule=1.00`, `dict=0.98`, `ner=0.90`, `classifier=0.90`, `ml_transformer=0.92`, `llm=0.85` (конфигурируемы).

### Этап 5. Grounding Validation (обязательный фильтр)
- **Hard constraint**: для всех финальных кандидатов `is_confirmed_in_text == true`.
- Проверка: `evidence_text` или ключевые токены присутствуют в `card.title`/`card.description`/`seller_attributes` (case-insensitive, нормализация пробелов, числовое/единичное совпадение `6,7` vs `6.7`, `ГБ` vs `GB`).
- Кандидаты без подтверждения **отбрасываются**.
- Сохраняем `source_spans` (минимум одно упоминание).

### Этап 6. Нормализация значений
- Базовая: trim, collapse spaces, нормализация кавычек, дефисов.
- Регистр: бренды — канонический из BrandVocab, enum — канонический из vocab, остальное — опц. Title Case.
- Синонимы: `synonyms_map` alias→canonical.
- Единицы измерения: унификация сокращений (`Гб/ГБ/GB`, `Тб/ТБ/TB`, `дюйм/дюйма/"/″/inch`, `мАч/мА·ч/mAh`), приведение к канонической единице схемы, опц. конверсия (`unit_conversion_enabled`), единообразный формат чисел.
- Enum-валидация: `value_type == 'enum'` → значение должно быть в `vocab`. Иначе попытка маппинга; при неуспехе — penalty/low_confidence либо отбрасывание при `enum_strict=true`.
- `unit_value`: парсинг числа+единицы, нормализация, форматирование (напр. `256 ГБ`, `6,7 дюйма`, `5000 мА·ч`).

### Этап 7. Confidence, пороги, статус
- Финальный `confidence` = взвешенная агрегация после мёржа + штрафы: `enum_out_of_vocab` (-0.15, если не strict), `conflicting_values` (-0.10), `weak_evidence` (-0.05).
- Пороги: `default_threshold_auto = 0.80`, `default_threshold_review = 0.60`, приоритет per-attribute.
- Логика:
  - `confidence >= T_auto` → `needs_review=false`, `status='ok`
  - `T_review <= confidence < T_auto` → `needs_review=true`, `status='low_confidence`
  - `confidence < T_review` → `needs_review=true`, `status='low_confidence`
  - Обязательный атрибут отсутствует → `status='partial'`, `needs_review=true`
  - Ошибка → `status='error'`
  - Без схемы/пропущено → `status='skipped'`
- Coverage: доля обязательных атрибутов категории, извлечённых с `confidence >= T_review` (или присутствующих).

### Этап 8. Пост-фильтрация и дедупликация
- Удаление дублей по `(attribute_code, normalized_value)`.
- `allow_multiple == false` → оставить лучший по confidence.
- Исключить кандидатов с `is_confirmed_in_text == false`.
- `enum_strict == true` + значение вне vocab (не замаппилось) → отбрасываем.

### Этап 9. Формирование результата
- `ExtractionResult.attributes` = финальный список (отсортирован по `attribute_code`).
- Заполнить `pipeline_version`, `processing_time_ms`, `low_confidence_count`, `needs_review`, `status`.
- Обязательные поля: `extraction_method`, `is_confirmed_in_text=true`, `normalized_value`, `confidence`, `source_spans` (>=1).

## 6. Обработка граничных случаев
| Случай | Поведение | Статус |
|---|---|---|
| Текст пустой/недостаточный | Нет возможности подтвердить значения в тексте. Возвращаем пустой список. `needs_review=true`. | `skipped` |
| Категория не определена | Применяем generic-схему. Сохраняем `category_id/category_name` из входа при наличии. | `ok`/`partial` |
| Схема категории отсутствует | Применяем минимальную схему по умолчанию. Не блокируем обработку. | `partial` |
| Атрибут встречается несколько раз с разными значениями | Grounded-кандидаты мёржатся. При конфликте разных `normalized_value` — понижаем confidence, не объединяем, либо `needs_review=true`. | `ok`/`low_confidence` |
| Значение в тексте, но не в vocab (enum) | Пытаемся замаппить через `synonyms_map`. Если нет: при `enum_strict=true` отбрасываем; при `enum_strict=false` — penalty + `needs_review=true`. | `low_confidence` |
| Числовой диапазон («128–256 ГБ») | Парсим по правилам. При неоднозначности — извлекаем явно упомянутое либо помечаем low_confidence. | `low_confidence` при неоднозначности |
| Смешанные единицы (дюймы/мм, ГБ/ТБ) | `UnitRules`. При конверсии приводим к канонической единице схемы. | `ok`/`low_confidence` |
| Короткое упоминание («6.7» без «дюйм») | Требуется контекстное подтверждение. Если rule/NER однозначно определяют атрибут — допустимо с пониженной confidence. Иначе не включать. | `low_confidence` или отбрасывается |
| Синонимы/аббревиатуры («ОЗУ 8ГБ», «RAM 8GB») | Нормализация через synonyms + unit rules. `normalized_value` канонизируем. | `ok` |
| Англо-русский микс | Регистронезависимый поиск, маппинги в обе стороны, словари брендов/enum. | `ok` |
| Множественные кандидаты от разных экстракторов | Мёржинг с весами методов, приоритет grounded. | `ok` |
| LLM вернул кандидата без `evidence_text` | Пост-валидация: отбрасываем (`require_evidence=true`). | фильтруется |
| LLM указал `is_confirmed_in_text=false` | Пост-валидация: отбрасываем (grounding required). | фильтруется |
| `evidence_text` не найден в исходном тексте | Проверка exact/normalized substring по `source_field`. При несовпадении — отбрасываем. | фильтруется |
| Таймаут/ошибка LLM | Graceful degradation: пропускаем LLM-этап, используем этапы 1–2. Обновляем `status`/`needs_review`. | `low_confidence`/`partial` |
| Модель NER/Transformer не загружена | Fallback на Rules/Dict/Classifier. WARNING + продолжение работы. | `ok`/`partial` |

## 7. Тестирование модуля

### 7.1 Unit-тесты
- RuleExtractor: парсинг единиц, шаблоны, boundary-aware, форматы чисел.
- DictExtractor: точное/частичное, синонимы, BrandVocab (стоп-слова), регистронезависимость.
- NERExtractor: BIO, склейка, постнормализация, маппинг в attribute_code.
- Normalizers: unit rules, синонимы, enum-mapping, форматирование чисел+единиц.
- GroundingValidator: exact/normalized, числовое (`6,7` vs `6.7`), единичное совпадение.
- Merging/Aggregation: группировка, взвешивание, конфликты, дедупликация.
- Confidence/Thresholds: пороги, штрафы, `needs_review`, `status`.

### 7.2 Integration-тесты
- Каскад cheap-first: rules закрывают ядро, ML дополняет, LLM не вызывается при достаточном покрытии.
- Grounding hard-filter: LLM-кандидат без подтверждения отбрасывается.
- Батч: частично успешный батч не прерывает остальные.
- Graceful degradation: `ENABLE_LLM=true` но недоступен → fallback на 1–2 этапы.
- Enum strict: поведение `enum_strict=true/false`.
- CategorySchema: required/optional, allow_multiple.

### 7.3 Contract-тесты
- Соответствие `AttributePrediction`/`ExtractionResponseItem` (api_contract.md).
- Обязательные поля: `attribute_code`, `normalized_value`, `confidence`, `extraction_method`, `is_confirmed_in_text`.
- `confidence` ∈ [0.0,1.0].
- `is_confirmed_in_text == true` во всех финальных атрибутах.

### 7.4 Приёмочные тест-кейсы
- Смартфон: бренд, модель, объём памяти, диагональ экрана, ёмкость батареи, цвет.
- Ноутбук: бренд, процессор, объём ОЗУ, накопитель, диагональ экрана, цвет.
- Редкая категория: проверка без массовых правил, активация LLM только при необходимости.
- Длинный хвост: редкие значения, синонимы, аббревиатуры.
- Микс RU/EN: корректная нормализация.

## 8. Метрики качества модуля
| Метрика | Описание | Способ расчёта |
|---|---|---|
| Precision | Доля корректно извлечённых среди извлечённых | TP/(TP+FP) по (product_id, attribute_code) на эталоне |
| Recall | Доля корректно извлечённых среди истинных | TP/(TP+FN) по (product_id, attribute_code) на эталоне |
| F1 | Гармоническое среднее P/R | 2*P*R/(P+R) |
| Accuracy (per-attribute) | Корректность по конкретному атрибуту | Отдельно по каждому атрибуту |
| Coverage | Доля карточек, в которых атрибут заполнен | (карточки с атрибутом) / (всего карточек) |
| ExactMatch | Строгое совпадение `normalized_value` с эталонным | 1/0 |
| SoftMatch | Мягкое совпадение (синонимы, эквивалентные единицы после нормализации) | 1/0 по правилам |
| % ниже порога (needs_review) | Доля предсказаний с `confidence < threshold_auto` | Нагрузка на ручную проверку |
| % отфильтровано grounding | Доля кандидатов, отфильтрованных GroundingValidator | Контроль жёсткости фильтра |
| Coverage по required-атрибутам | Покрытие обязательных атрибутов категории | Среднее/по категории на gold-сете |
| Качество по категориям (stratified) | Оценка отдельно по каждой категории | Stratified по `category_name/id` |
| Weighted by traffic | Метрики взвешенные по трафику/частоте фильтрации атрибута | При наличии статистики трафика |

**Правила валидации**: сравнение по `normalized_value` (каноническому); учитывать `allow_multiple` (матч по пересечению); grounding-фильтр не должен искусственно завышать Precision без учёта Recall; метрики — отдельно по каждому атрибуту.

## 9. Мониторинг, логирование, трассировка

### 9.1 Логирование
- Уровни: INFO (ключевые этапы каскада), DEBUG (детали кандидатов), WARNING (fallbacks/degraded), ERROR (failures).
- Структурные логи (JSON) в prod-подобном режиме: `product_id`, `category`, `pipeline_version`, `stages`, `methods_used`, `llm_called`, `candidates_before_grounding`, `candidates_after_grounding`, `processing_time_ms`, `needs_review`.
- Без PII: не логировать полный сырой текст; допустимы `text_hash`, длина, первые N символов title.
- Секреты: никогда не логировать `LLM_API_KEY`, заголовки авторизации.

### 9.2 Метрики (runtime)
- `extract_requests_total{method="single|batch"}`
- `extract_duration_ms{stage="preprocess|rules|dict|ner|classifier|transformer|llm|merge|normalize|total"}`
- `candidates_total{method,attribute_code}`
- `grounding_filtered_total{reason}`
- `low_confidence_total{attribute_code,threshold}`
- `needs_review_ratio`
- `llm_calls_total{model,status="ok|timeout|error"}`
- `llm_latency_ms`, `llm_tokens_total{type="prompt|completion"}`
- `coverage_by_attribute{attribute_code,category}`
- `degraded_mode{component="ner|transformer|llm"}`

### 9.3 Трассировка
- `pipeline_version` в каждом ответе API.
- `extraction_method`, `source_spans`, `evidence_text` для каждого финального кандидата.
- Тайминги по этапам.
- Версии моделей: `ner_model_version`, `transformer_model_version`, `llm_model`, `vocab_version`, `rules_version`.

### 9.4 Алерты (рекомендуемые)
- Резкий рост `needs_review` (>X%) за окно.
- Увеличение доли отфильтрованных grounding (>Y%) при включённом LLM.
- Рост `llm_errors_total`/таймаутов.
- Падение coverage по required-атрибутам ключевых категорий.
- Долгая инициализация моделей при старте (>Z сек).

## 10. Принципы реализации
- KISS + модульность: каждый экстрактор изолирован.
- Cheap-first каскад: дорогие компоненты только при gate (coverage < 1.0 по required или low_confidence).
- Grounding как инвариант: никогда не выпускать кандидата с `is_confirmed_in_text == false`. Фильтрация после каждого источника (особенно LLM).
- Determinism: Rules/Dict детерминированы. Для LLM — `temperature=0.0`, фиксированные `top_p`, версионирование промпта.
- Fail-safe: graceful degradation, partial results в батче, ошибки элемента не валят батч.
- Traceable: каждый финальный атрибут несёт `extraction_method`, `confidence`, `source_spans`, `evidence_text`.
- Тестируемо: чистые интерфейсы, DI, конфиг через `Pydantic Settings`.
- Обратная совместимость: `pipeline_version` увеличивается при изменении логики нормализации/агрегации/порогов.
- Не выдумывать: явный запрет в LLM-промпте + пост-валидация grounding — главный защитный барьер.
- Единообразие: `attribute_code` в snake_case, `normalized_value` в каноническом формате схемы.
