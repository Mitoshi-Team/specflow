# Attribute Extractor

Сервис извлечения атрибутов товаров из спецификаций на FastAPI.

## Устройство

- `src/attribute_extractor/main.py` — фабрика приложения `create_app()` и объект `app`.
- `src/attribute_extractor/config.py` — настройки (`EXTRACTOR_*`).
- `src/attribute_extractor/constants.py` — константы маршрутов.
- `tests/` — unit-тесты.

## Запуск

Из корня репозитория:

```bash
uv run uvicorn attribute_extractor.main:app --port 8001 --reload
```

## Эндпоинты

| Метод | Путь | Описание |
| --- | --- | --- |
| GET | `/api/health` | Проверка работоспособности |

В docker-сети сервис доступен API Gateway по адресу
`http://attribute_extractor:8001`.
