# Спецификация: API-контракт

## 1. Назначение

Описать REST API сервиса извлечения атрибутов (Attribute Extractor Service). API предназначен для пакетной и одиночной обработки карточек товаров, получения схем атрибутов по категориям, проверки здоровья сервиса и получения информации о конфигурации.

Стек: Python + FastAPI. Формат — JSON. Все эндпоинты валидируются через Pydantic.

**Основной контракт (вход → выход):** на вход подаётся текст карточки товара (название, описание, атрибуты продавца), на выход возвращается JSON с выделенными атрибутами — для каждого атрибута `attribute_code`, `normalized_value` (каноническое значение) и `confidence` (уверенность). Основной эндпоинт: `POST /api/v1/extract`.

## 2. Общие принципы

- **Base URL**: `/api/v1`
- **Формат**: `application/json`
- **Коды ответов**: 200, 400, 422, 429, 500
- **Валидация**: ошибки в формате `{"detail": "...", "errors": [...]}` (стандарт FastAPI)
- **Только текст**: изображения не принимаются
- **Idempotency**: не требуется для одиночных предсказаний. Для батча опц. `batch_id`
- **Ограничения батча**: `batch_size` ∈ [1, 50]. Превышение → 422
- **Версионирование**: префикс `v1`
- **Частичный успех**: батч возвращает результаты по каждой карточке с индивидуальным `status`

## 3. Модели запросов/ответов (Pydantic)

### 3.1 ProductCardRequest

```json
{
  "product_id": "string (optional)",
  "title": "string (optional)",
  "description": "string (optional)",
  "seller_attributes": { "...": "any (optional)" },
  "category_id": "string (optional)",
  "category_name": "string (optional)",
  "language": "string (optional, e.g. 'ru'|'en'|'mixed')"
}
```

**Правило валидации:** хотя бы одно из полей (`title`, `description`, `seller_attributes`) должно быть непустым.

### 3.2 AttributePrediction

```json
{
  "attribute_code": "string",
  "raw_value": "string",
  "normalized_value": "string",
  "confidence": 0.0,
  "evidence_text": "string (optional)",
  "source_spans": [
    {"field": "title|description|seller_attributes", "text": "string", "start": 0, "end": 10}
  ],
  "extraction_method": "rule|ner",
  "is_confirmed_in_text": true,
  "ner_score": 0.0,
  "match_score": 0.0,
  "is_new_field": false
}
```

**Ограничения:** `confidence` ∈ [0.0,1.0], `is_confirmed_in_text == true` в финальном ответе. `ner_score` присутствует для `extraction_method="ner"`; `match_score` и `is_new_field` — опциональная трассировка резолва поля.

### 3.3 ExtractionResponseItem

```json
{
  "product_id": "string (optional)",
  "category_id": "string (optional)",
  "category_name": "string (optional)",
  "attributes": [AttributePrediction],
  "status": "ok|low_confidence|partial|error|skipped",
  "needs_review": true,
  "low_confidence_count": 0,
  "processing_time_ms": 123,
  "pipeline_version": "string"
}
```

### 3.4 BatchExtractRequest

```json
{
  "items": [ProductCardRequest],
  "batch_id": "string (optional)",
  "batch_size": 10,
  "return_sources": true,
  "return_raw_values": true,
  "threshold_override": 0.8
}
```

**Ограничения:** `batch_size` ∈ [1,50].

### 3.5 BatchExtractResponse

```json
{
  "batch_id": "string (optional)",
  "total": 2,
  "ok": 1,
  "low_confidence": 1,
  "errors": 0,
  "results": [ExtractionResponseItem],
  "processing_time_ms_total": 456
}
```

### 3.6 CategorySchema

```json
{
  "category": "string",
  "category_id": "string (optional)",
  "required_attributes": [{"code": "brand", "value_type": "string", "is_required": true}],
  "optional_attributes": [{"code": "color", "value_type": "enum", "vocab": ["чёрный","белый"]}],
  "schema_version": "string"
}
```

### 3.7 HealthResponse

```json
{
  "status": "ok|degraded|down",
  "version": "string",
  "pipeline_version": "string",
  "uptime_seconds": 123,
  "models_loaded": ["rules", "ner", "vector_index"],
  "cache_enabled": true
}
```

### 3.8 ErrorResponse

```json
{
  "detail": "string",
  "code": "string (optional)",
  "errors": [{"loc": ["string"], "msg": "string", "type": "string"}]
}
```

## 4. Эндпоинты

### 4.1 POST `/api/v1/extract` — одиночное извлечение

**Request:** `ProductCardRequest` → **Response:** `ExtractionResponseItem` (200). Ошибки: 422, 500.

### 4.2 POST `/api/v1/extract/batch` — пакетное извлечение

**Request:** `BatchExtractRequest` → **Response:** `BatchExtractResponse` (200). Ошибки: 400, 422, 500.
Особенности: `return_sources` (по умолчанию true), `threshold_override` (временное переопределение порога).

### 4.3 GET `/api/v1/categories` — список категорий со схемами

**Query:** `category` (опц.), `limit` (int, default=50, max=200), `offset` (int, default=0)
**Response:** `{"items": [CategorySchema], "total": 100}` (200)

### 4.4 GET `/api/v1/categories/{category}` — схема конкретной категории

**Response:** `CategorySchema` (200), 404 если не найдена.

### 4.5 GET `/api/v1/health` — проверка работоспособности

**Response:** `HealthResponse` (200). `degraded` — часть компонентов не загружена, но базовый пайплайн (rules) доступен. `down` — критическая ошибка инициализации.

### 4.6 GET `/api/v1/info` — информация о сервисе

**Response (200):**

```json
{
  "service_name": "attribute-extractor",
  "version": "1.0.0",
  "pipeline_version": "1.0.0",
  "extraction_methods": ["rule","ner"],
  "default_threshold": 0.80,
  "supports_batch": true,
  "max_batch_size": 50,
  "text_only": true,
  "features": {
    "grounding_required": true,
    "normalization": true,
    "unit_conversion": true,
    "traffic_weighted_metrics": true
  }
}
```

### 4.7 GET `/api/v1/config` — конфигурация (read-only)

**Response (200):** `confidence_thresholds` (auto/review), `match_threshold`, `deterministic_confidence`.

## 5. Нефункциональные требования API

- **Производительность:** stateless, горизонтально масштабируемый. Приоритет дешёвых путей (rules/NER).
- **Надёжность:** graceful degradation — при недоступности тяжёлых компонентов использовать fallback с корректным `status`.
- **Безопасность:** валидация входа, отсутствие логирования PII в сыром виде, read-only конфиги без секретов.
- **Документация:** автоматическая OpenAPI/Swagger (`/docs`, `/redoc`).
- **Кэширование:** опционально (in-memory) для идентичных карточек по хэшу текста.
- **Ограничения:** защита от слишком больших описаний (soft-limit) с понятной 422-ошибкой.

## 6. Допущения и особенности

- **Grounding обязателен:** API никогда не возвращает `is_confirmed_in_text=false` в успешном финальном ответе. Неподтверждённые кандидаты отфильтровываются.
- **Low confidence handling:** значения с `confidence < threshold` остаются в `attributes` с полями; `needs_review=true`, `status = low_confidence/partial`.
- **Частичные результаты:** `partial` — часть обязательных атрибутов категории не извлечена.
- **Единый выходной формат:** `attribute_code` (snake_case), `normalized_value` в каноническом виде.
