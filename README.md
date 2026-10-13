# specflow

## Описание

Монорепозиторий сервисов SpecFlow — извлечение атрибутов товаров из спецификаций.

## Архитектура

```
specflow/
├── pyproject.toml            # корневой uv-workspace и dev-зависимости
├── docker-compose.yml        # сборка и запуск всего стека
├── nginx/nginx.conf          # reverse-proxy: единая точка входа
└── services/
    ├── frontend/             # React + TypeScript + Vite (i18next)
    ├── api_gateway/          # FastAPI — публичный API
    └── attribute_extractor/  # FastAPI — извлечение атрибутов
```

Запросы снаружи приходят на nginx (порт 80): `/` проксируется на фронтенд,
`/api/` — на API Gateway. Сервис `attribute_extractor` доступен только внутри
docker-сети.

## Требования

- Python 3.13
- [uv](https://docs.astral.sh/uv/)
- Node.js 22+ (для локальной разработки фронтенда)
- Docker и Docker Compose

## Начало работы

### 1. Клонируйте репозиторий

```bash
git clone https://github.com/Mitoshi-Team/specflow
cd specflow
```

### 2. Создайте .env на основе .env.example

```bash
cp .env.example .env
```

При необходимости отредактируйте переменные.

### 3. Установите pre-commit хуки

```bash
uv tool install pre-commit
pre-commit install
```

### 4. Установите зависимости бэкенда

```bash
uv sync
```

Команда создаёт общее виртуальное окружение `.venv` и устанавливает оба сервиса
(`api_gateway`, `attribute_extractor`) вместе с dev-зависимостями (ruff, pytest).

### 5. Запустите docker

```bash
docker compose up --build -d
```

Сайт будет доступен на `http://localhost` (порт задаётся переменной `NGINX_PORT`).

Для остановки используйте

```bash
docker compose down
```

## Структура сервисов

| Сервис | Технологии | Порт в контейнере |
| --- | --- | --- |
| `nginx` | nginx | 80 |
| `frontend` | React, TypeScript, Vite, i18next | 5173 |
| `api_gateway` | FastAPI, uvicorn | 8000 |
| `attribute_extractor` | FastAPI, uvicorn | 8001 |

## Полезные команды

### Бэкенд

```bash
uv run pytest              # все тесты бэкенда
uv run ruff check          # линт
uv run ruff format         # форматирование
uv run uvicorn api_gateway.main:app --reload         # запуск API Gateway
uv run uvicorn attribute_extractor.main:app --port 8001 --reload  # запуск экстрактора
```

### Фронтенд

```bash
cd services/frontend
npm install
npm run dev        # dev-сервер Vite (http://localhost:5173)
npm run build      # проверка типов и production-сборка
```

Если нужно сбросить окружение: удалите `.venv` и выполните `uv sync` заново.
