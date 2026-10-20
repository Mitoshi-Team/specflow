## 1. Данные и обучение

- [x] 1.1 Собрать weak-датасет для NER через distant supervision: join `sku_desc.parquet` и `skus.pkl` по `sku_id` (пересечение ~241 355 карточек)
- [x] 1.2 Для каждой пары key→value найти значение в `title`/`description` и разметить спан как `PROPERTY`, контекст — как `CHARACTERISTIC`
- [x] 1.3 Очистить размеченные примеры от служебного шума (HTML, служебные «атрибуты» из EDA)
- [ ] 1.4 Создать малый ручной gold-набор (несколько сотен карточек) для метрик и подбора порогов

## 2. Каталог полей и векторный индекс

- [x] 2.1 Забустрапить `FieldCatalog` из 9 целевых кодов + 10 708 наблюдаемых имён атрибутов (после нормализации)
- [x] 2.2 Составить `FieldBlocklist` из стоп-слов EDA («Подборки», «Продавец», BI-поля, «Гарантия предоставляется», «Потратить бонусы» и т.п.)
- [x] 2.3 Реализовать абстрактный `VectorIndex` (`embed`, `add`, `search`) и выбрать конкретную реализацию для MVP
- [ ] 2.4 Подобрать `MATCH_THRESHOLD` на gold-наборе

## 3. Контракты (`services/contracts`)

- [x] 3.1 Заменить `ExtractionMethod` на `{structured, rule, ner}`; обновить `test_domain.py`, `test_api.py`
- [x] 3.2 Дополнить `AttributeCandidate` полями `ner_score`, `match_score`, `is_new_field`
- [x] 3.3 Обновить схемы API (`HealthResponse.models_loaded`, `/info`, `/config`) под новый контракт
- [x] 3.4 Обновить TS-типы `services/frontend/src/schemas/api.ts` (`ExtractionMethod`, `ConfigResponse`)

## 4. Сервис извлечения (`services/attribute_extractor`)

- [x] 4.1 `constants.py`: удалить `DEFAULT_METHOD_WEIGHTS`, три штрафа, `MERGED_METHOD`, блок LLM; добавить `MATCH_THRESHOLD`, `DETERMINISTIC_CONFIDENCE`, версию NER-модели/каталога
- [x] 4.2 `config.py`: удалить `method_weights`, `enable_llm`, `llm_*`, `hybrid_strategy`; добавить векторные параметры; обновить `test_config.py`
- [x] 4.3 Этап чистки: расширить препроцессинг снятием HTML-тегов и служебных вставок
- [ ] 4.4 Реализовать structured-экстрактор (`seller_attributes` key→вектор-матч, значение→нормализация)
- [ ] 4.5 Реализовать NER-экстрактор (2 метки, пейринг, `ner_score`), подключить обученную модель
- [x] 4.6 Реализовать rules-fallback (единицы + близость ключевых слов) только для незакрытых required
- [x] 4.7 Переработать `merging.py`: группировка по `attribute_code`, выбор max confidence, конфликт → `needs_review`
- [x] 4.8 Упростить confidence: `structured`/`rule` → `DETERMINISTIC_CONFIDENCE`, `ner` → `ner_score`; убрать веса и штрафы
- [x] 4.9 Удалить экстракторы `classifier.py`, `transformer.py`, `llm.py`, `dictionary.py`; переписать `extractors/__init__.py` и `registry.py`
- [x] 4.10 Реализовать авто-добавление новых полей с проверкой блоклиста и персистентностью каталога

## 5. Тестирование и синхронизация

- [x] 5.1 Обновить `test_attribute_extractor_extractors.py`, `test_attribute_extractor_merging.py`
- [x] 5.2 Добавить тесты на чистку текста, field resolution, блоклист, авто-добавление, rules-fallback
- [ ] 5.3 Проверить grounding-фильтр и пороги на gold-наборе
- [x] 5.4 Синхронизировать `README.md` с новой архитектурой
- [x] 5.5 Прогнать `uv run pytest` и `uv run ruff check`
