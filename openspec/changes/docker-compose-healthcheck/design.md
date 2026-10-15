## Context

См. proposal.md - Why. Текущий стек (docker-compose.yml): nginx, frontend, api_gateway, attribute_extractor. У сервисов уже есть `restart: unless-stopped`, но нет healthcheck'ов и нет строгого условия готовности в `depends_on` (используется только `depends_on: [service]`).

Для реализации зависимостей "только после здорового состояния" в Compose V2 используется `depends_on` с `condition: service_healthy` (требует наличия `healthcheck` у зависимого сервиса). Также nginx настроен как reverse-proxy на frontend/api_gateway; фронтенд в dev-режиме (Vite), бэкенд-сервисы на FastAPI/Uvicorn.

## Goals / Non-Goals

**Goals:**
- Добавить healthcheck для всех сервисов (nginx, frontend, api_gateway, attribute_extractor)
- Настроить `depends_on: condition: service_healthy` там, где есть реальные зависимости (nginx -> frontend, api_gateway; api_gateway -> attribute_extractor)
- Ввести единообразную политику рестарта (уже есть, унифицировать при необходимости)
- Добавить структурное логирование (json-формат, ограничения по размеру/количеству файлов) для всех сервисов

**Non-Goals:**
- Изменение бизнес-логики сервисов (не трогаем код приложений)
- Переход с dev-режима frontend на production-сборку
- Изменение портов/конфигурации nginx, кроме добавления healthcheck
- Настройка внешнего лог-агрегатора (только локальные параметры docker logging driver)

## Decisions

**D1. Стратегия healthcheck по сервисам**
- **nginx**: HTTP-проверка на localhost (например, `curl -f http://localhost/` или `GET /healthz`). Так как в `nginx/nginx.conf` есть проксирование, можно добавить простой location `/healthz` с `return 200 'ok'` и `access_log off`. Альтернатива: `nc -z localhost 80`/`curl` без доп. location — но добавление `/healthz` чище.
- **frontend (Vite dev)**: HTTP-проверка на `http://localhost:5173` (Vite отвечает на запросы). В alpine-образе node есть curl? node:22-alpine обычно содержит curl? Или лучше использовать wget (тоже есть). Проверим: можно использовать `wget --no-verbose --tries=1 --spider http://localhost:5173/ || exit 1`.
- **api_gateway (FastAPI)**: стандартный health endpoint. У сервиса есть `main.py`? Посмотрим код. Если есть `/healthz` или `/health`, используем его. Если нет — добавим минимальный `/healthz`? Но цель — не менять бизнес-логику. Можно проверить базовую доступность Uvicorn (например, `curl -f http://localhost:8000/docs` или добавить в код простой endpoint). Лучше сначала поискать существующие health-endpoints. Если их нет — можно временно использовать проверку TCP (`nc -z localhost 8000`) через `wait-for`-подход, но в Docker healthcheck лучше HTTP.
  Однако **Non-Goal** — не менять код приложений. Поэтому либо использовать TCP-проверку через `nc`/`ss` (если есть), либо добавить endpoint в код. Но код менять нельзя по Non-Goal? "Не трогаем код приложений" — значит избегаем. Альтернатива: для FastAPI можно сделать healthcheck через `python -c "..."` с urllib, но в slim-образе доступен python. Или просто проверка, что порт слушается: `timeout 2 bash -c '</dev/tcp/localhost/8000'`. В node-alpine/nginx-alpine часто нет `nc`. Можно использовать `wget`/`curl`.
- **attribute_extractor**: аналогично api_gateway, порт 8001. HTTP или TCP. Предпочтителен HTTP-контроль готовности приложения.

**D2. depends_on с condition: service_healthy**
В `docker-compose.yml`:
- `nginx`:
  - `depends_on: frontend: condition: service_healthy, api_gateway: condition: service_healthy`
- `api_gateway`:
  - `depends_on: attribute_extractor: condition: service_healthy`
- `frontend`/`attribute_extractor` не имеют health-условий для зависимостей в текущем стеке (frontend зависит только от себя, attribute_extractor — только от себя).

**D3. Структурное логирование**
Использовать `logging`-блок для всех сервисов:
```yaml
logging:
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"
```
Это предотвратит разрастание логов в dev-окружении, унифицировано для всех контейнеров. Альтернатива `local` драйверу — тоже ок, но `json-file` совместим шире.

**D4. Политика рестарта**
`restart: unless-stopped` оставить как есть (все уже имеют). Унифицировать стиль (везде одинаково).

**D5. Наличие утилит в образах для healthcheck**
- `frontend` (node:22-alpine): `wget` есть (busybox), `curl` может отсутствовать. Проще `wget`.
- `api_gateway`/`attribute_extractor` (uv/python slim-bookworm): `curl` часто есть, либо `wget`. Также можно использовать `python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"`.
- `nginx` (nginx:1.27-alpine): `wget`/`curl` есть? nginx:alpine базовый образ минимальный — curl может быть не установлен. Можно либо добавить `RUN apk add --no-cache curl` в nginx-образ (но nginx — готовый образ, можно сделать healthcheck через `wget` из busybox: `wget -O /dev/null http://localhost/healthz || exit 1`). Также можно использовать `nc` через busybox (`nc -z localhost 80`).

## Risks / Trade-offs

- [Risk] **Изменение docker-compose.yml влияет только на локальный запуск.** В CI сейчас собираем образы, но не поднимаем compose-стек. Поэтому healthcheck/depends_on не сломают существующий CI build (он только собирает образы). Mitigation: проверить, что workflow не использует `docker compose up` с `depends_on: condition: service_healthy`.
- [Risk] **Нужно проверить наличие health-endpoints в API-сервисах.** Если в коде нет `/healthz`, HTTP-healthcheck через curl/wget к несуществующему маршруту вернёт 404 → контейнер будет считаться unhealthy. Mitigation: сначала осмотреть код `api_gateway.main` и `attribute_extractor.main`. Если endpoint отсутствует — либо добавить минимальный health-endpoint (меньше всего риска: добавляет тривиальную ручку), либо использовать TCP-проверку. Но Non-Goal — не трогать код. TCP-проверка надёжнее в рамках Non-Goal, но менее информативна.
- [Risk] **В образах могут отсутствовать curl/wget**. Для healthcheck нужны инструменты. Mitigation: использовать то, что есть в образе. Для python-образов можно python-вариант. Для nginx-alpine — busybox wget. Для node-alpine — busybox wget.
- [Risk] **start_period для медленного старта**. FastAPI/Uvicorn стартуют быстро, Vite dev тоже. Можно выставить консервативные значения: `interval: 10s, timeout: 5s, retries: 5, start_period: 20s`.
- [Risk] **nginx healthcheck через /healthz требует добавления location**. Нужно модифицировать `nginx/nginx.conf`. Это минимальное изменение конфигурации, не меняет проксирование.

## Migration Plan

1. Осмотреть код сервисов на предмет наличия health-endpoints (`api_gateway/main.py`, `attribute_extractor/main.py`).
2. При необходимости добавить минимальный `/healthz` в оба FastAPI-сервиса (trivial: `@app.get("/healthz") def healthz(): return {"status": "ok"}`) — это минимальное изменение кода, совместимо с Non-Goal? Non-Goal говорит "Не трогаем код приложений". Добавление простого health-endpoint — это инфраструктурное улучшение, не меняет бизнес-логику. Но формально — правка кода. Обсудим? Но лучше предложить оба варианта: либо TCP-healthcheck (без правки кода), либо HTTP к `/healthz` (с минимальной правкой).
3. Добавить location `/healthz` в `nginx/nginx.conf` (возврат 200).
4. Обновить `docker-compose.yml`: добавить healthcheck для всех сервисов, `depends_on` с `condition: service_healthy`, `logging` для всех, унифицировать `restart`.
5. Проверить локальный запуск: `docker compose up --build` — стек должен стартовать по порядку, healthcheck'и проходить.
6. Убедиться, что CI (только сборка образов) не ломается.
7. Коммит изменений.
