# Образ сервиса извлечения атрибутов. Контекст сборки — корень репозитория (uv workspace).
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Манифесты всех участников workspace нужны, чтобы uv разрешил общий lock-файл.
COPY pyproject.toml uv.lock ./
COPY services/api_gateway/pyproject.toml services/api_gateway/
COPY services/attribute_extractor/pyproject.toml services/attribute_extractor/
COPY services/attribute_extractor/src services/attribute_extractor/src

RUN uv sync --frozen --no-dev --package attribute-extractor

EXPOSE 8001

CMD ["uvicorn", "attribute_extractor.main:app", "--host", "0.0.0.0", "--port", "8001"]
