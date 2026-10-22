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

# Зависимости ставятся ДО копирования исходников: слой инвалидируется только
# правкой манифестов, поэтому пересборка после правки кода не качает колеса
# заново. --no-install-workspace: пакеты workspace ставятся из исходников ниже.
# Кэш uv — cache-mount: переживает пересборки и не попадает в образ.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package api-gateway --no-install-workspace

COPY services/contracts/src services/contracts/src
COPY services/api_gateway/src services/api_gateway/src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package api-gateway

EXPOSE 8000

CMD ["uvicorn", "api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
