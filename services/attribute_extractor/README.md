# Attribute Extractor

Сервис извлечения атрибутов товаров из спецификаций на FastAPI.

## Устройство

- `src/attribute_extractor/main.py` — фабрика приложения `create_app()` и объект `app`.
- `src/attribute_extractor/config.py` — настройки Pydantic (`EXTRACTOR_*`): пороги
  уверенности, веса методов, лимиты батча, таймауты и версии с валидацией.
- `src/attribute_extractor/constants.py` — значения по умолчанию и доменные
  константы пайплайна (пороги, штрафы, веса методов, версии, таймауты).
- `src/attribute_extractor/preprocessing.py` — препроцессинг карточки (Этап 0):
  сбор `raw_text`, нормализация текста, определение языка, токенизация и резолв
  `CategorySchema` с fallback на generic-схему.
- `src/attribute_extractor/extractors/` — базовый класс `BaseExtractor`, реестр
  `ExtractorRegistry` и скелеты экстракторов каскада.
- `tests/` — unit-тесты.

## Запуск

Из корня репозитория:

```bash
uv run uvicorn attribute_extractor.main:app --port 8001 --reload
```

## Эндпоинты

| Метод | Путь | Описание |
| --- | --- | --- |
| GET | `/api/v1/health` | Проверка работоспособности |

В docker-сети сервис доступен API Gateway по адресу
`http://attribute_extractor:8001`.
