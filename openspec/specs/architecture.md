# Спецификация: Архитектура

## 1. Назначение

Описать целевую архитектуру решения «ИИ для автоматического заполнения характеристик товаров». Определить компоненты, потоки данных, развёртывание и принципы (гибридный пайплайн, grounding, управляемая стоимость, human-in-the-loop).

Стек: **Backend** — Python + FastAPI; **Frontend** — React, TypeScript, Vite; **Reverse proxy** — nginx; **Контейнеризация** — Docker (docker-compose).

**Ядро системы (вход → выход):** на вход подаётся текст карточки товара (название, описание, текстовые атрибуты продавца), на выход отдаётся JSON с выделенными атрибутами, где для каждого атрибута указаны каноническое значение и уверенность. Вся описанная ниже архитектура (каскад экстракторов, нормализация, grounding, confidence) обслуживает именно этот контракт.

## 2. Архитектурные принципы

- **Гибридный пайплайн (Hybrid-first):** rules/словари, NER/классификатор, трансформеры, LLM — совместно, каскад (cheap-first). Дорогие методы — только при необходимости.
- **Grounding-first (не выдумывать):** каждое извлечённое значение должно быть подтверждено исходным текстом карточки. Галлюцинации блокируются фильтрацией по подтверждению.
- **Separation of concerns:** чёткое разделение входа, препроцессинга, извлечения, нормализации, валидации, агрегации, экспорта.
- **Модульность и расширяемость:** новые экстракторы подключаются через единый интерфейс Registry.
- **Контролируемая стоимость:** трассировка `extraction_method` + `confidence`, флаги для отключения тяжёлых компонентов.
- **Human-in-the-loop:** `confidence < threshold` → `needs_review`, результаты можно выгружать для ручной разметки и обратной связи.
- **Stateless backend:** API stateless, масштабируем по горизонтали. ML-модели грузятся при старте.
- **Observability-ready:** структурные логи, метрики, тайминги по этапам.
- **Portability:** Docker Compose, конфигурация через .env, базовый режим (rules) работает без внешних тяжёлых зависимостей.

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
                            │  - Cascade (cheap-first)         │
                            │  - Grounding + Confidence        │
                            │  - Normalization + Aggregation   │
                            └─────────────┬─────────┬─────────┘
                                          ▼           ▼
                    ┌─────────────────────────────────────────┐
                    │           Extractors Registry           │
                    │  Rule/Dict | NER | Classifier | Transf.| LLM │
                    └─────────────┬─────────┬─────────┬─────────┘
                                  ▼           ▼           ▼
                        ┌─────────────┐ ┌─────────┐ ┌───────────┐
                        │  Vocabularies│ │  Models │ │ LLM Client│
                        │  (Brands,    │ │  ONNX/HF │ │ (OpenRouter│
                        │   Mappings,  │ │         │ │  /External)│
                        │   Units)     │ │         │ │            │
                        └─────────────┘ └─────────┘ └───────────┘

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
- Dependencies: DI пайплайна, конфигурации, клиентов

### 4.2 Pipeline Orchestrator

Отвечает за: препроцессинг, резолв схемы категории, каскад экстракторов (cheap-first), мёржинг кандидатов, grounding validation, нормализация, confidence calibration, пост-фильтрация, формирование результата.

**Стратегия каскада:** Этап 1 (rules+dicts) → Этап 2 (NER/classifier/transformer, локальные) → Этап 3 (LLM, резервный, только при необходимости, с жёстким grounding).

### 4.3 Extractors Registry

| Экстрактор | Назначение | Стоимость | Особенности |
| --- | --- | --- | --- |
| `RuleExtractor` | Регулярки, шаблоны, парсинг единиц | Очень низкая | Детерминирован, explainable |
| `DictExtractor` | Поиск по словарям/синонимам, BrandVocab | Очень низкая | Быстрый, точный для enum |
| `NERExtractor` | Извлечение сущностей (token-level) | Низкая | Работает с текстом |
| `ClassifierExtractor` | Классификация enum по контексту | Низкая | Помогает при неоднозначности |
| `TransformerExtractor` | Encoder-based tagging/QA | Средняя | Сильный на хвосте, локальный |
| `LLMExtractor` | Zero/few-shot с JSON-схемой + grounding | Высокая | Резервный, строго контролируемый |

### 4.4 Vocabularies, Normalizers, Validators

- **BrandVocab/AttributeVocab**: канонические значения + синонимы
- **UnitRules**: приведение единиц, (опц.) конверсия
- **Normalizers**: очистка, регистр, синонимы, форматирование
- **GroundingValidator**: проверка подтверждения в исходном тексте (hard filter)

### 4.5 Confidence & Aggregation

Взвешенное агрегирование по `method_weights`, штрафы при конфликтах/enum-out-of-vocab/слабом подтверждении, калибровка порогов per-attribute/default.

### 4.6 Data & Storage

- Конфиги/правила/словари/схемы категорий — в репозитории (версионируются)
- Локальные модели — в `models/` (volume), не коммитить тяжёлые веса
- Артефакты (EDA, предсказания CSV, презентация) — в `artifacts/`
- Постоянная БД не требуется (stateless MVP)

### 4.7 Frontend

SPA на React + TS + Vite, собирается в `dist/`, раздаётся nginx. Взаимодействие через REST API по `/api`.

### 4.8 Infrastructure & Deployment (Docker + nginx)

**Dockerfile (backend):** `python:3.11-slim`, установка зависимостей, запуск `uvicorn app.main:app --host 0.0.0.0 --port 8000`.

**Dockerfile (frontend):** multi-stage (node build → nginx). Копия `dist/`, кастомный `nginx.conf`.

**docker-compose.yml:** сервисы `backend`, `frontend`. Volumes: `models_data`. Внутренняя сеть `app-net`.

**nginx.conf:** статика `location / { try_files $uri /index.html; }`, API-прокси `location /api/ { proxy_pass http://backend:8000/api/; ... }`, gzip, `client_max_body_size` для батчей.

**Конфигурация (.env):**

```env
APP_ENV=dev
LOG_LEVEL=INFO
API_PREFIX=/api/v1
DEFAULT_CONFIDENCE_THRESHOLD=0.80
ENABLE_LLM=false
LLM_PROVIDER=openrouter
LLM_MODEL=qwen/qwen3-8b:free
LLM_API_KEY=
LLM_TEMPERATURE=0.0
LLM_MAX_TOKENS=1000
HYBRID_STRATEGY=cascade_cheap_first
GROUNDING_REQUIRED=true
NORMALIZATION_ENABLED=true
UNIT_CONVERSION_ENABLED=true
MAX_BATCH_SIZE=50
CORS_ORIGINS=*
```

Базовый режим `ENABLE_LLM=false` работает без внешних вызовов.

## 5. Потоки данных

**Сценарий 1. Одиночное извлечение (`POST /api/v1/extract`):** вход → препроцессинг + схема → каскад (rules/dict → NER/classifier/transformer → LLM при необходимости) → merge → grounding validation → normalization → confidence → формирование ответа.

**Сценарий 2. Батч + экспорт CSV:** батчевый запрос → параллельная обработка → `BatchExtractResponse` → фронт экспортирует в формате PredictionRow.

**Сценарий 3. Graceful degradation:** LLM недоступен/таймаут → пропускаем этап LLM, возвращаем partial/low_confidence; ML-модели не загружены → fallback на rules/dicts; ошибка элемента батча → индивидуальный `status=error`, батч не прерывается.

## 6. Нефункциональные требования (архитектура)

- **Масштабируемость:** stateless backend, горизонтальное масштабирование.
- **Производительность:** cheap-first, (опц.) кэширование по хэшу текста.
- **Надёжность:** таймауты на внешние вызовы, ограниченные retry с backoff, graceful degradation.
- **Репродуктивность:** `pipeline_version`, версии моделей/промптов, детерминизм rule-веток, LLM-параметры (`temperature=0.0`).
- **Безопасность:** секреты только в .env, CORS настраиваемый, валидация входов, grounding-защита от галлюцинаций.
- **Совместимость:** Windows (win32), кроссплатформенный Docker Compose.
- **Расширяемость:** добавление экстрактора через BaseExtractor + Registry + конфиг.

## 7. Риски и меры снижения

| Риск | Меры снижения |
| --- | --- |
| Галлюцинации LLM | Grounding REQUIRED (hard filter), запрет выдумывать в промпте, требование `evidence_text`+`source_spans`, strict JSON Schema, `is_confirmed_in_text`-валидация, `temperature=0.0`, LLM только резерв |
| Стоимость на масштабе | Cascade cheap-first, `ENABLE_LLM` флаг, per-attribute thresholds, метод-трассировка |
| Длинный хвост/редкие категории | Гибрид (Transformer локально), LLM для новых категорий (few-shot), метрики по категориям, пополняемые словари |
| Падение на новых категориях | Schema-first (CategorySchema), zero/few-shot LLM, валидация по редким категориям |
| Нестабильность внешних LLM | Таймауты, ограниченные retry, graceful degradation, версионирование модели/промпта |
| Конфликты кандидатов | Мёржинг с весами методов, при конфликте — понижение confidence, `needs_review` |
| Качество нормализации (enum) | Enum-validation против vocab: при выходе — synonyms mapping либо penalty/low_confidence либо отбрасывание при strict |

## 8. Требования к развёртыванию (MVP)

- `docker compose up --build` поднимает backend+frontend+nginx без ручных шагов (README).
- Базовый режим (`ENABLE_LLM=false`) работает offline-friendly.
- Frontend: `http://localhost` (80), API через `/api/v1`.
- `GET /api/v1/health` возвращает `status: ok` после старта.
