# Образ сервиса извлечения атрибутов. Контекст сборки — корень репозитория (uv workspace).
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# OMP_NUM_THREADS/MKL_NUM_THREADS ограничивают число потоков torch для
# CPU-инференса: без ограничения torch занимает все ядра хоста, а контейнеру
# достаётся только часть — инференс замедляется и мешает соседним сервисам.
# Переопределяется в docker-compose.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=4 \
    MKL_NUM_THREADS=4 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# --- Шаг 1: внешние зависимости ( invalidated только манифестами) ---------------
# Манифесты всех участников workspace нужны, чтобы uv разрешил общий lock-файл.
COPY pyproject.toml uv.lock ./
COPY services/contracts/pyproject.toml services/contracts/
COPY services/api_gateway/pyproject.toml services/api_gateway/
COPY services/attribute_extractor/pyproject.toml services/attribute_extractor/

# Зависимости ставятся ДО копирования исходников: слой инвалидируется только
# правкой pyproject.toml/uv.lock. Иначе любая правка кода заставляет заново
# скачивать torch+transformers (~250 МБ) — пересборка занимала ~3 минуты.
# --no-install-workspace: сами пакеты workspace ставятся из исходников ниже,
# здесь — только внешние зависимости.
# Кэш uv подключён cache-mount'ом: он переживает пересборки (не нужно качать
# колеса повторно) и НЕ попадает в образ.
RUN uv sync --frozen --no-dev --package attribute-extractor --extra ner --no-install-workspace

# --- Шаг 2: веса NER-модели (инвалидируются только весами) ---------------------
# Веса NER-модели (~713 МБ, Git LFS) копируются в образ: сервис должен
# работать автономно внутри docker-сети, без тома с весами на хосте.
# Шаг идёт ДО копирования исходников, чтобы правка кода не перезаписывала
# 713 МБ весов заново.
COPY services/attribute_extractor/models/ner /app/models/ner

# --- Шаг 3: исходники сервиса (инвалидируются правкой кода) -------------------
COPY services/contracts/src services/contracts/src
COPY services/attribute_extractor/src services/attribute_extractor/src
# Версонируемый бренд-словарь: без него brand/model-правила в образе выключены.
COPY services/attribute_extractor/assets services/attribute_extractor/assets

# Установка пакетов workspace из исходников: локальная сборка колес, без сети
# (нужное уже в кэше uv предыдущего шага).
RUN uv sync --frozen --no-dev --package attribute-extractor --extra ner

# Проверка весов на этапе сборки: образ с нескачанными весами (указатели
# Git LFS) собираться не должен — иначе сервис молча деградирует до правил.
# Проверка идёт ПОСЛЕ установки пакетов: скрипт импортирует модули сервиса.
COPY services/attribute_extractor/scripts/check_ner_model.py /tmp/check_ner_model.py
RUN python3 /tmp/check_ner_model.py /app/models/ner && rm /tmp/check_ner_model.py

EXPOSE 8001

CMD ["uvicorn", "attribute_extractor.main:app", "--host", "0.0.0.0", "--port", "8001"]
