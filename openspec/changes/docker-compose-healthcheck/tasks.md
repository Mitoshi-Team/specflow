## 1. Инфраструктурная подготовка

- [x] 1.1 Проверить наличие health-endpoints в коде `services/api_gateway/src/api_gateway/main.py` и `services/attribute_extractor/src/attribute_extractor/main.py`
- [x] 1.2 Принять решение о методе healthcheck для API-сервисов (HTTP к существующему `/healthz` или TCP) исходя из результатов проверки
- [x] 1.3 Добавить минимальный `/healthz` endpoint в оба API-сервиса (только если его нет). Альтернатива — использовать TCP-проверку без правки кода

## 2. Конфигурация nginx

- [x] 2.1 Добавить location `/healthz` в `nginx/nginx.conf` для healthcheck nginx-контейнера

## 3. Обновление docker-compose.yml

- [x] 3.1 Добавить healthcheck для `nginx` (HTTP на `/healthz` или проверка порта)
- [x] 3.2 Добавить healthcheck для `frontend` (HTTP на http://localhost:5173)
- [x] 3.3 Добавить healthcheck для `api_gateway` (HTTP на http://localhost:8000/healthz или TCP)
- [x] 3.4 Добавить healthcheck для `attribute_extractor` (HTTP на http://localhost:8001/healthz или TCP)
- [x] 3.5 Настроить `depends_on` с `condition: service_healthy` для nginx (depends on frontend и api_gateway)
- [x] 3.6 Настроить `depends_on` с `condition: service_healthy` для api_gateway (depends on attribute_extractor)
- [x] 3.7 Добавить блок `logging` (json-file, max-size: 10m, max-file: 3) для всех сервисов
- [x] 3.8 Убедиться, что `restart: unless-stopped` задан для всех сервисов (унифицировать при необходимости)

## 4. Тестирование и валидация

- [ ] 4.1 Локально собрать образы: `docker compose build`
- [ ] 4.2 Запустить стек: `docker compose up -d` и проверить порядок старта и успешность healthcheck'ов (`docker compose ps`, `docker inspect`)
- [ ] 4.3 Убедиться, что nginx доступен и проксирует запросы после того, как зависимости стали healthy
- [ ] 4.4 Проверить, что существующий CI (docker-build.yml) по-прежнему собирает образы без ошибок
