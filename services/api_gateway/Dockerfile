# Образ API Gateway. Контекст сборки — корень репозитория (uv workspace).
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Манифесты всех участников workspace нужны, чтобы uv разрешил общий lock-файл.
COPY pyproject.toml uv.lock ./
COPY services/contracts/pyproject.toml services/contracts/
COPY services/api_gateway/pyproject.toml services/api_gateway/
COPY services/attribute_extractor/pyproject.toml services/attribute_extractor/
COPY services/contracts/src services/contracts/src
COPY services/api_gateway/src services/api_gateway/src

RUN uv sync --frozen --no-dev --package api-gateway

EXPOSE 8000

CMD ["uvicorn", "api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
