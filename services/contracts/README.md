# SpecFlow Contracts

Общий пакет доменных моделей и Pydantic-схем, разделяемый сервисами
`api_gateway` и `attribute_extractor`.

## Устройство

- `src/specflow_contracts/constants.py` — разделяемые числовые/строковые константы.
- `src/specflow_contracts/enums.py` — перечисления домена и API.
- `src/specflow_contracts/domain.py` — доменные модели (`ProductCard`, `Span`,
  `Attribute`, `AttributeCandidate`, `CategorySchema`, `ExtractionResult`).
- `src/specflow_contracts/api.py` — схемы API (`ProductCardRequest`,
  `BatchExtractRequest`, `BatchExtractResponse`, `HealthResponse`,
  `ErrorResponse`, `ErrorDetail`).
- `tests/` — unit-тесты.

Спецификации: `openspec/specs/domain-model.md`, `openspec/specs/api_contract.md`.

## Использование

```python
from specflow_contracts import ProductCard, ExtractionResult
```
