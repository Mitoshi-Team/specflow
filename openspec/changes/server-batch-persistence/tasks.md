## 1. Контракт и модели

- [x] 1.1 Добавить `BatchSummary`, `BatchListResponse`, `StoredBatchResponse` в `services/contracts/src/specflow_contracts/api.py`, поле `persisted` в `BatchExtractResponse`
- [x] 1.2 Экспортировать модели из `specflow_contracts.__init__`, покрыть тестами (`services/contracts/tests/test_api.py`)

## 2. Серверная персистентность (attribute_extractor)

- [x] 2.1 Зависимость `psycopg[binary]`, константы истории (`BATCHES_ENDPOINT`, лимиты, таймаут подключения), `database_url` в настройках
- [x] 2.2 Модуль `batch_store.py`: протокол `BatchStore`, `InMemoryBatchStore`, `PostgresBatchStore` (DDL, insert/update, список, чтение; ошибки → `BatchStoreError`)
- [x] 2.3 Доменные ошибки `BatchNotFoundError` (404) и `BatchHistoryUnavailableError` (503)
- [x] 2.4 `main.py`: выбор хранилища по `EXTRACTOR_DATABASE_URL`, логирование режима и подготовка схемы при старте, запись батча после `POST /extract/batch`, `GET /batches`, `GET /batches/{batch_id}`
- [x] 2.5 Тесты: `test_attribute_extractor_batch_store.py`, `test_attribute_extractor_batches_api.py` (persisted=false + логи, 503/404-конверты, пагинация, OpenAPI)

## 3. Инфраструктура

- [x] 3.1 Сервис `postgres:16-alpine` в `docker-compose.yml` (volume, healthcheck, порт не публикуется), `depends_on: service_healthy` у `attribute_extractor`
- [x] 3.2 `EXTRACTOR_DATABASE_URL` собирается из `POSTGRES_*`; `.env.example` документирует переменные
- [x] 3.3 Интеграционный тест `test_attribute_extractor_batch_store_integration.py` (пропускается без `EXTRACTOR_TEST_DATABASE_URL`)

## 4. Frontend

- [x] 4.1 Типы и методы API: `listBatches`, `getBatch`, `persisted` в `BatchExtractResponse`
- [x] 4.2 Страница результатов: загрузка батча по `?batch_id`, панель «Предыдущие батчи», предупреждения `notPersisted`/`localFallback`, ErrorBanner на сбоях
- [x] 4.3 `PageHome`: навигация с `?batch_id` при успешной серверной записи; `writeLastBatch` возвращает успех и влияет на навигацию
- [x] 4.4 i18n-ключи (ru/en), стили истории
- [x] 4.5 Тесты: `endpoints.test.ts`, `PageResults.test.tsx`, `PageHome.test.tsx`, `lastBatch.test.ts`

## 5. Документация и проверки

- [x] 5.1 `openspec/specs/api_contract.md`: 3.9–3.11, 4.8, 4.9, семантика `persisted`, коды ответов
- [x] 5.2 `openspec/specs/frontend.md`: эндпоинты истории, сценарий просмотра истории, `useLocalStorage` как фолбэк
- [x] 5.3 README (корневой, attribute_extractor, frontend, api_gateway): эндпоинты истории, настройка PostgreSQL
- [x] 5.4 Прогон полного набора тестов (pytest, ruff, vitest, tsc), `docker compose config`
