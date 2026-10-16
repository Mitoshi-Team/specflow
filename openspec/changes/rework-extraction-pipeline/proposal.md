## Why

Текущее описание пайплайна (`openspec/specs/attribute_extractor.md`) построено вокруг гибридного cheap-first каскада из шести экстракторов (rule/dict/NER/classifier/transformer/LLM) со взвешенной агрегацией уверенности, штрафами и LLM как резервным звеном. Эта модель переусложнена, плохо понимается и не соответствует данным.

Разведочный анализ (EDA) показал, что качество определяется двумя факторами: **чистотой входного текста** (49,3% описаний содержат HTML, 41,1% заголовков дублируются, много служебного шума) и **нормализацией имён полей** (10 708 имён атрибутов сводятся к 9 целевым кодам). Сложность каскада и внешняя LLM на это не влияют, а внешние LLM в задаче не обязательны.

Нужно упростить спецификацию и привести её к проверяемому целевому гибриду без LLM: чистая текстовая основа, структурированный быстрый путь, правила на ядре, NER на длинном хвосте и векторное сопоставление характеристик с каталогом полей.

## What Changes

- **Новый пайплайн:** clean → schema resolve → structured (`seller_attributes`) → core rules → NER tail → vector field matching (+ blocklist) → normalize → rules fallback → merge → grounding → confidence → assemble.
- **NER** — multilingual encoder (token-classification) с двумя метками: `CHARACTERISTIC` (имя поля, «корпус») и `PROPERTY` (значение, «красный»); пейринг в пределах окна/предложения.
- **Field resolution** — векторный матч характеристики к каталогу полей `FieldCatalog` через абстрактный `VectorIndex`; при `match_score >= MATCH_THRESHOLD` — существующее поле, ниже — авто-добавление нового поля с обязательным блоклистом.
- **Confidence упрощена:** deterministic-кандидаты (`structured`/`rule`) получают фиксированную `DETERMINISTIC_CONFIDENCE`; `ner`-кандидаты — `ner_score`; `match_score` хранится только для трассировки. Удаляются `method_weights`, три штрафа, формула взвешенной агрегации, `hybrid_strategy` и метод `hybrid`.
- **LLM полностью удаляется** из спецификаций (экстрактор, конфиг, диаграмма, API, продуктовые принципы).
- **Обучение NER** фиксируется как distant supervision от `seller_attributes` (join по `sku_id`, поиск значения в тексте) плюс малый ручной gold-набор для метрик и подбора порогов.
- **Новые требования к архитектуре:** персистентность каталога полей и блоклиста (следствие авто-добавления полей).

## Capabilities

### Modified Capabilities
- `attribute-extractor` — этапы и интерфейсы пайплайна извлечения
- `architecture` — компоненты, поток данных, конфигурация, развёртывание
- `domain-model` — сущности пайплайна, перечисление `ExtractionMethod`
- `api-contract` — перечисления `extraction_method`, `/health`, `/info`, `/config`
- `product` — принципы гибридности и бизнес-метрики

## Impact

- **Спецификации:** `openspec/specs/attribute_extractor.md`, `architecture.md`, `domain-model.md`, `api_contract.md`, `product.md`.
- **Код (breaking, вне скоупа этой правки):**
  - `services/contracts` — перечисление `ExtractionMethod` (7 → 3 значений), поля `AttributeCandidate`, схемы API;
  - `services/attribute_extractor` — `constants.py`, `config.py`, `merging.py`, `extractors/` (удаление classifier/transformer/llm/dict, новый registry), соответствующие тесты;
  - `services/frontend` — TS-типы `ExtractionMethod` и `ConfigResponse`;
  - `api_gateway` — без изменений (тонкий прокси, логики извлечения нет).
- **Документация:** `README.md` описывает старый LLM-каскад и потребует синхронизации (отдельной задачей).
- **Данные:** для NER требуется weak-разметка из `seller_attributes` и малый gold-набор; риск их отсутствия зафиксирован в `design.md`.
