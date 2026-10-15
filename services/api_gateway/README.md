# API Gateway

Публичный HTTP-API SpecFlow на FastAPI.

## Устройство

- `src/api_gateway/main.py` — фабрика приложения `create_app()` и объект `app`.
- `src/api_gateway/config.py` — настройки Pydantic (`API_GATEWAY_*`): версии,
  порог уверенности, лимиты батча и таймауты upstream с валидацией.
- `src/api_gateway/constants.py` — значения по умолчанию (маршруты, CORS,
  версии, пороги, лимиты, таймауты).
- `tests/` — unit-тесты.

## Запуск

Из корня репозитория:

```bash
uv run uvicorn api_gateway.main:app --reload
```

## Эндпоинты

| Метод | Путь | Описание |
| --- | --- | --- |
| GET | `/api/v1/health` | Проверка работоспособности |
