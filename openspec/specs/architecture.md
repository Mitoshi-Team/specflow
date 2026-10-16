# Спецификация: Архитектура

## 1. Назначение

Описать целевую архитектуру решения «ИИ для автоматического заполнения характеристик товаров». Определить компоненты, потоки данных, развёртывание и принципы (целевой гибрид без LLM, grounding, управляемая стоимость, human-in-the-loop).

Стек: **Backend** — Python + FastAPI; **Frontend** — React, TypeScript, Vite; **Reverse proxy** — nginx; **Контейнеризация** — Docker (docker-compose).

**Ядро системы (вход → выход):** на вход подаётся текст карточки товара (название, описание, текстовые атрибуты продавца), на выход отдаётся JSON с выделенными атрибутами, где для каждого атрибута указаны каноническое значение и уверенность. Вся описанная ниже архитектура (чистка текста, structured/rules/NER-пути, векторный матч полей, нормализация, grounding, confidence) обслуживает именно этот контракт.

## 2. Архитектурные принципы

- **Целевой гибрид без LLM:** структурированный путь (`seller_attributes`), детерминированные правила на ядре, NER-трансформер на длинном хвосте и векторное сопоставление характеристик с каталогом полей. Генеративные модели не используются.
- **Clean-first:** любой входящий текст очищается (HTML, служебные вставки, шум) до извлечения.
- **Grounding-first (не выдумывать):** каждое извлечённое значение должно быть подтверждено исходным текстом карточки.
- **Separation of concerns:** чёткое разделение чистки, извлечения, резолва полей, нормализации, валидации, агрегации и экспорта.
- **Модульность и расширяемость:** structured/rules/NER и `FieldCatalog`/`VectorIndex` подключаются через единые интерфейсы.
- **Контролируемая стоимость:** без внешних вызовов; NER и векторный индекс — локальные подключаемые компоненты.
- **Human-in-the-loop:** `confidence < threshold` → `needs_review`; новые поля и ошибки можно выгружать для аудита.
- **Stateless API (с оговоркой):** API stateless, но каталог полей и блоклист персистируются (см. 4.6).
- **Observability-ready:** структурные логи, метрики, тайминги по этапам.
- **Portability:** Docker Compose, конфигурация через .env; пути structured/rules работают без тяжёлых зависимостей.

## 3. Высокоуровневая архитектура

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ Клиенты (Frontend / External)                                            │
└───────────────────────────────┬─────────────────────┬─────────────────┘
                                │ REST (JSON)        │
                                ▼                   │
                        ┌─────────────────────────┐  │
                        │  nginx (Reverse Proxy)  │  │
                        │  маршрутизация + статика│  │
                        └────────────┬────────────┘  │
                                     ▼                   ▼
                          ┌─────────────────────────────────────┐
                          │        API Gateway / Backend        │
                          │        FastAPI (api/v1)             │
                          │  - Validation (Pydantic)             │
                          │  - Orchestration, Health, Info      │
                          └──────────────┬──────────────┬──────┘
                                         ▼              ▼
                            ┌─────────────────────────────────┐
                            │        Pipeline Orchestrator     │
                            │  (AttributeExtractionPipeline)   │
                            │  - Clean + Grounding + Confidence│
                            │  - Normalization + Aggregation   │
                            └─────────────┬─────────┬─────────┘
                                          ▼           ▼
                    ┌─────────────────────────────────────────┐
                    │           Extraction Paths               │
                    │  Structured | Rules | NER                │
                    └─────────────┬─────────┬─────────┬────────┘
                                  ▼           ▼           ▼
                        ┌─────────────┐ ┌─────────┐ ┌───────────┐
                        │  Vocabularies│ │  NER    │ │ Vector    │
                        │  (Brands,    │ │  Model  │ │ Index +   │
                        │   Mappings,  │ │ (HF/ONNX│ │ Field     │
                        │   Units)     │ │         │ │ Catalog   │
                        └─────────────┘ └─────────┘ └───────────┘
                                  ▲
                        ┌─────────┴───────┐
                        │ FieldBlocklist  │
                        └─────────────────┘

                        ┌─────────────────────────────────┐
                        │           Frontend (SPA)        │
                        │     React + TS + Vite           │
                        │  - Upload CSV/JSON, Preview     │
                        │  - Batch, Results, Export CSV   │
                        └─────────────┬─────────────────┘
                                      │ Static (nginx)
                                      ▼
```

## 4. Компоненты и зоны ответственности

### 4.1 API Layer (FastAPI)

- Routers: `extract`, `categories`, `health`, `info`, `config`
- Pydantic-схемы валидации (api_contract.md)
- Middlewares: CORS, логирование, обработка ошибок, (опц.) rate-limiting
- Dependencies: DI пайплайна, конфигурации, индекса

### 4.2 Pipeline Orchestrator

Отвечает за: чистку текста, резолв схемы категории, structured/rules/NER-пути, резолв полей, нормализацию, rules-fallback, мёржа кандидатов, grounding validation, расчёт уверенности, пост-фильтрацию и формирование результата.

**Стратегия:** Этап A (structured + rules, дешёвые и детерминированные) → Этап B (NER, хвост) → Этап C (векторный матч полей) → нормализация → rules-fallback для незакрытых обязательных полей.

### 4.3 Extraction Paths

| Путь | Назначение | Стоимость | Особенности |
| --- | --- | --- | --- |
| `StructuredExtractor` | Разбор `seller_attributes` (key→value) | Очень низкая | Точный, структура задана продавцом |
| `RuleExtractor` | Регулярки, шаблоны, единицы | Очень низкая | Детерминирован, explainable, ядро |
| `NERExtractor` | Token-level извлечение `CHARACTERISTIC`/`PROPERTY` | Низкая/средняя | Трансформер, длинный хвост, локальный |

### 4.4 Поля, нормализаторы, валидаторы

- **FieldCatalog**: канонические поля (код, name_ru, синонимы, value_type, unit, is_new_field).
- **VectorIndex**: эмбеддинги названий полей, поиск ближайшего поля (`match_score`).
- **FieldBlocklist**: стоп-слова/шаблоны служебных «атрибутов» (шум из EDA).
- **BrandVocab/AttributeVocab**: канонические значения + синонимы.
- **UnitRules**: приведение единиц измерения.
- **Normalizers**: синонимы, регистр, единицы, форматирование.
- **GroundingValidator**: проверка подтверждения в исходном тексте (hard filter).

### 4.5 Confidence & Aggregation

Упрощённая модель: `structured`/`rule` → `deterministic_confidence`; `ner` → `ner_score`. Мёржа по `attribute_code` с выбором максимального confidence; конфликт значений → `needs_review`. Взвешенная агрегация методов и штрафы не применяются.

### 4.6 Data & Storage

- Конфиги/правила/словари/схемы категорий — в репозитории (версионируются).
- **FieldCatalog и FieldBlocklist персистируются** (файл/БД): авто-добавление новых полей меняет состояние между запросами.
- Локальные модели — в `models/` (volume), не коммитить тяжёлые веса.
- Артефакты (EDA, предсказания CSV, презентация) — в `artifacts/`.

### 4.7 Frontend

SPA на React + TS + Vite, собирается в `dist/`, раздаётся nginx. Взаимодействие через REST API по `/api`.

### 4.8 Infrastructure & Deployment (Docker + nginx)

**Dockerfile (backend):** `python:3.11-slim`, установка зависимостей, запуск `uvicorn app.main:app --host 0.0.0.0 --port 8000`.

**Dockerfile (frontend):** multi-stage (node build → nginx). Копия `dist/`, кастомный `nginx.conf`.

**docker-compose.yml:** сервисы `backend`, `frontend`. Volumes: `models_data`, `catalog_data`. Внутренняя сеть `app-net`.

**nginx.conf:** статика `location / { try_files $uri /index.html; }`, API-прокси `location /api/ { proxy_pass http://backend:8000/api/; ... }`, gzip, `client_max_body_size` для батчей.

**Конфигурация (.env):**

```env
APP_ENV=dev
LOG_LEVEL=INFO
API_PREFIX=/api/v1
DEFAULT_CONFIDENCE_THRESHOLD=0.80
REVIEW_CONFIDENCE_THRESHOLD=0.60
MATCH_THRESHOLD=0.75
DETERMINISTIC_CONFIDENCE=0.90
NER_MODEL_PATH=models/ner
FIELD_CATALOG_PATH=data/field_catalog.json
FIELD_BLOCKLIST_PATH=data/field_blocklist.txt
GROUNDING_REQUIRED=true
NORMALIZATION_ENABLED=true
UNIT_CONVERSION_ENABLED=true
MAX_BATCH_SIZE=50
CORS_ORIGINS=*
```

Пути structured/rules работают без NER-модели и векторного индекса (graceful degradation).

## 5. Потоки данных

**Сценарий 1. Одиночное извлечение (`POST /api/v1/extract`):** вход → чистка + схема → structured/rules/NER → резолв полей (векторный матч + блоклист) → нормализация → rules-fallback → merge → grounding validation → confidence → формирование ответа.

**Сценарий 2. Батч + экспорт CSV:** батчевый запрос → параллельная обработка → `BatchExtractResponse` → фронт экспортирует в формате PredictionRow.

**Сценарий 3. Graceful degradation:** NER-модель не загружена → fallback на structured/rules; векторный индекс недоступен → точное совпадение по имени поля и правила; ошибка элемента батча → индивидуальный `status=error`, батч не прерывается.

## 6. Нефункциональные требования (архитектура)

- **Масштабируемость:** stateless API, горизонтальное масштабирование (каталог/блоклист — общее персистентное хранилище).
- **Производительность:** дешёвые пути (structured/rules) первыми, (опц.) кэширование по хэшу текста.
- **Надёжность:** graceful degradation при недоступности NER/индекса, partial results в батче.
- **Репродуктивность:** `pipeline_version`, версии NER-модели/каталога/словарей, детерминизм rule-веток.
- **Безопасность:** валидация входов, grounding-защита от выдумывания, отсутствие PII в логах.
- **Совместимость:** Windows (win32), кроссплатформенный Docker Compose.
- **Расширяемость:** добавление пути/компонента через интерфейсы и конфиг.

## 7. Риски и меры снижения

| Риск | Меры снижения |
| --- | --- |
| Отсутствие разметки для NER | Distant supervision от `seller_attributes` + малый ручной gold (см. design.md) |
| Ошибки NER/пейринга | Grounding hard-filter, порог по `ner_score`, `source_spans`/`evidence_text` |
| Дрейф каталога от авто-добавления полей | FieldBlocklist, периодический аудит новых полей, лимит авто-полей |
| Потолок покрытия по полям вне текста (`color` 16,8%) | Ограничение данных; фиксируется честно, архитектурой не решается |
| Стоимость на масштабе | Локальные компоненты, отсутствие внешних вызовов, дешёвые пути первыми |
| Недоступность NER/индекса | Graceful degradation до structured/rules + точного совпадения |
| Конфликты кандидатов | Мёржа по `attribute_code`, выбор max confidence, `needs_review` |
| Качество нормализации (enum) | Enum-validation против vocab: синонимы либо `low_confidence` |
| Тяжёлые зависимости (encoder + embeddings) | Структурные/правила-пути без моделей; модели — подключаемый volume |

## 8. Требования к развёртыванию (MVP)

- `docker compose up --build` поднимает backend+frontend+nginx без ручных шагов (README).
- Базовый режим (structured + rules, без NER/индекса) работает offline-friendly.
- Frontend: `http://localhost` (80), API через `/api/v1`.
- `GET /api/v1/health` возвращает `status: ok` после старта.
