## Why

Настроить healthcheck'и для сервисов в docker-compose и строго определить порядок запуска через `depends_on: condition: service_healthy`. Это повысит надёжность старта стека: nginx/api_gateway не будут пытаться подключиться к зависимым сервисам, пока те реально не готовы принимать соединения. Также добавить базовое структурное логирование и политику рестарта для всех сервисов.

## What Changes

- **Healthcheck'и**: для `nginx`, `frontend`, `api_gateway`, `attribute_extractor` добавлены проверки готовности (curl/wget для HTTP, tcp-проверка или проверка прослушивания порта)
- **depends_on с condition: service_healthy**: `nginx` зависит от `frontend` и `api_gateway` только после их healthcheck; `api_gateway` зависит от `attribute_extractor` после его healthcheck
- **Структурное логирование**: настроены драйвер/формат логов (json) и лимиты ротации (`max-size`, `max-file`) для всех сервисов
- **Политика рестарта**: для всех сервисов задан `restart: unless-stopped` (уже есть частично — унифицировано)
- **Улучшения надёжности**: при необходимости добавлены `init`/`healthcheck` таймауты, `start_period`, `interval`, `retries`, `timeout`

## Capabilities

### New Capabilities
- None

### Modified Capabilities
- None

## Impact

- `docker-compose.yml` — добавление healthcheck, depends_on с condition, logging-конфига, унификация restart
- `nginx/` — при необходимости добавление healthcheck-запроса (например, `/healthz` или проверка порта)
- `services/*/Dockerfile` — могут потребоваться curl/wget/netcat для healthcheck (если их нет в образе)
- Конфигурация запуска dev-стека
- Наблюдаемость при локальном запуске
