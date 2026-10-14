# Спецификация: Frontend (веб-интерфейс)

## 1. Назначение
Веб-интерфейс (SPA) для демонстрации и ручной проверки пайплайна извлечения атрибутов. Позволяет загрузить карточки товаров (CSV/JSON), запустить пакетную обработку через REST API, просмотреть результаты с оценкой уверенности, индикаторами ручной проверки, источниками подтверждения и экспортировать предсказания в формате CSV (PredictionRow).

Стек: **React + TypeScript + Vite**, минимальный UI, fetch API, сборка статикой через nginx.

## 2. Целевая аудитория
- Команда разработки/исследователей (демонстрация экспериментов, сравнение подходов)
- Контент/каталог (проверка качества извлечения, отбор кейсов на ручную разметку)
- Защита решения (наглядный показ работы пайплайна)

## 3. Архитектура фронтенда

### 3.1 Технологический стек
| Технология | Версия (рекомендуемая) | Назначение |
|---|---|---|
| [Vite](https://vitejs.dev/) | ^6.x | Сборка, dev-сервер, HMR |
| [React](https://react.dev/) | ^19.x | UI-компоненты |
| [TypeScript](https://www.typescriptlang.org/) | ^5.x | Типизация |
| [React Router](https://reactrouter.com/) | ^7.x (опц.) | Роутинг (минимум — одна страница) |
| [fetch API](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API) | нативный | Взаимодействие с REST API |
| [Papa Parse](https://www.papaparse.com/) | ^5.x | Парсинг CSV (загрузка) |
| [xlsx](https://docs.sheetjs.com/) | опц. | Альтернативный импорт (необязательно) |
| [clsx](https://github.com/lukeed/clsx) | опц. | Условные классы |

**Принцип**: минимализм. Без избыточных UI-библиотек, достаточно CSS-модулей/просто CSS.

### 3.2 Структура проекта
```
services/frontend/
├── src/
│   ├── api/                # Клиент API (fetch)
│   ├── components/         # Переиспользуемые UI-компоненты
│   ├── features/            # Фичи (upload, results, preview)
│   ├── hooks/              # Кастомные хуки
│   ├── lib/                # Утилиты (csv, formatters, validators)
│   ├── pages/              # Страницы
│   ├── schemas/            # TS-типы (совпадают с API-контрактом)
│   ├── styles/             # Глобальные стили
│   ├── App.tsx
│   └── main.tsx
├── public/
├── index.html
├── vite.config.ts
├── tsconfig.json
├── package.json
└── Dockerfile (multi-stage)
```

### 3.3 Интеграция с API
Фронт взаимодействует с бэкендом через nginx-прокси: все `/api/*` проксируются на `backend:8000`.

**Эндпоинты, используемые UI:**
| Метод | URL | Назначение |
|---|---|---|
| `POST` | `/api/v1/extract/batch` | Пакетная обработка загруженных карточек |
| `GET` | `/api/v1/health` | Проверка доступности сервиса (статус-панель) |
| `GET` | `/api/v1/info` | Отображение версии пайплайна/сервиса (опц.) |
| `GET` | `/api/v1/categories` | Выбор категории/просмотр схемы (опц.) |

## 4. Типизация (TypeScript)
Типы синхронизированы с доменом/API-контрактом (api_contract.md).

```ts
// schemas/api.ts (фрагмент)
export type ProductCardRequest = {
  product_id?: string
  title?: string
  description?: string
  seller_attributes?: Record<string, unknown>
  category_id?: string
  category_name?: string
  language?: string
}

export type Span = {
  field: 'title' | 'description' | 'seller_attributes'
  text: string
  start?: number
  end?: number
}

export type AttributePrediction = {
  attribute_code: string
  raw_value: string
  normalized_value: string
  confidence: number
  evidence_text?: string
  source_spans?: Span[]
  extraction_method: 'rule'|'dict'|'ner'|'classifier'|'ml_transformer'|'llm'|'hybrid'
  is_confirmed_in_text: boolean
}

export type ExtractionResponseItem = {
  product_id?: string
  category_id?: string
  category_name?: string
  attributes: AttributePrediction[]
  status: 'ok'|'low_confidence'|'partial'|'error'|'skipped'
  needs_review: boolean
  low_confidence_count?: number
  processing_time_ms?: number
  pipeline_version: string
}

export type BatchExtractRequest = {
  items: ProductCardRequest[]
  batch_id?: string
  batch_size?: number
  return_sources?: boolean
  return_raw_values?: boolean
  threshold_override?: number
}

export type BatchExtractResponse = {
  batch_id?: string
  total: number
  ok: number
  low_confidence: number
  errors: number
  results: ExtractionResponseItem[]
  processing_time_ms_total?: number
}
```

## 5. Пользовательские сценарии

### Сценарий 1. Загрузка файла
1. Пользователь выбирает CSV или JSON-файл с карточками.
2. Фронт парсит файл (валидация минимального набора полей).
3. Отображает предпросмотр (первые 10–20 строк).
4. Проверяет наличие хотя бы одного из: `title`, `description`, `seller_attributes`.

### Сценарий 2. Пакетная обработка
1. Нажатие «Обработать».
2. Блокировка UI + индикатор загрузки, прогресс «обработано/всего».
3. POST `/api/v1/extract/batch` с `items`, `batch_size` (по умолчанию 10–20, макс. 50).
4. При успехе — переход к результатам.
5. При ошибке — сообщение с детализацией.

### Сценарий 3. Просмотр результатов
1. Таблица по карточкам: `product_id`, `category`, `status`, `needs_review`, `low_confidence_count`, `processing_time_ms`.
2. Раскрывающийся блок атрибутов: `attribute_code`, `normalized_value`, `confidence`, `extraction_method`, `evidence_text`, `source_spans`.
3. Визуальная индикация: `needs_review=true` — акцент, `confidence < threshold` — выделение, `error` — красный.
4. Показ `pipeline_version`, `batch_id`, сводки (`total/ok/low_confidence/errors`).

### Сценарий 4. Экспорт CSV (PredictionRow)
1. Кнопка «Скачать CSV» формирует файл по формату `PredictionRow` (domain-model.md).
2. Колонки: `product_id`, `title`, `category`, `needs_review`, `status`. Для каждого атрибута — `[attribute_code]` = `normalized_value`, `[attribute_code]_confidence` = `confidence`.
3. Экспорт только финальных атрибутов (grounded). Пустые ячейки для не извлечённых.
4. Кодировка UTF-8, разделитель `,`.

## 6. Компоненты UI

### 6.1 Структурные
| Компонент | Назначение |
|---|---|
| `AppLayout` | Общий лэйаут (шапка, контейнер, футер с версией) |
| `Header` | Заголовок + индикатор здоровья API (`/health`) |
| `PageHome` | Главная (загрузка + предпросмотр + запуск батча) |
| `PageResults` | Страница результатов батча |

### 6.2 Функциональные
| Компонент | Описание |
|---|---|
| `FileUpload` | Drag&Drop + file input (CSV/JSON), валидация |
| `DataPreview` | Предпросмотр загруженных карточек |
| `BatchControls` | Настройки батча + кнопки «Обработать»/«Сброс» |
| `ResultsSummary` | Сводка батча |
| `ResultsTable` | Список карточек с раскрытием атрибутов |
| `AttributesTable` | Таблица атрибутов по карточке |
| `AttributeRow` | Строка атрибута с подсветкой low_confidence/needs_review |
| `ConfidenceBadge` | Бейдж уверенности с цветовой индикацией |
| `MethodBadge` | Бейдж метода извлечения |
| `ExportCsvButton` | Генерация и скачивание CSV по PredictionRow |
| `StatusBadge` | Статус карточки |
| `ErrorBanner` | Ошибки API/валидации |
| `Loader` | Спиннер + прогресс |
| `EmptyState` | Пустое состояние |

### 6.3 Валидация загружаемого файла
**CSV (рекомендуемые колонки):** `product_id`, `title`, `description`, `seller_attributes`, `category_id`, `category_name`.

**JSON:** массив объектов `ProductCardRequest`.

**Валидация:** минимум одно непустое из `title|description|seller_attributes`; корректный JSON в `seller_attributes` (если строка); не пустой файл; разумный размер; расширение `.csv`, `.json`, `.tsv` (опц.).

## 7. Состояние и хуки
| Хук | Назначение |
|---|---|
| `useApiHealth()` | Периодическая проверка `/api/v1/health` |
| `useBatchExtract()` | Отправка батча с состоянием loading/error/progress |
| `useFileParser()` | Парсинг CSV/JSON, нормализация, валидация |
| `useCsvExport()` | Генерация PredictionRow CSV |
| `useLocalStorage()` | Сохранение последнего батча (опц.) |

## 8. Визуализация и UX

### 8.1 Цветовая индикация
| Элемент | Цвет | Пояснение |
|---|---|---|
| `confidence >= 0.9` | Зелёный | Высокая уверенность |
| `0.8 <= confidence < 0.9` | Жёлтый | Близко к порогу |
| `confidence < 0.8` | Оранжевый | Ниже типичного auto-порога |
| `needs_review = true` | Жёлто-оранжевая рамка/акцент | Ручная проверка |
| `status = error` | Красный | Ошибка обработки |
| `status = partial` | Фиолетовый/синий | Частично извлечены required-атрибуты |
| `status = low_confidence` | Оранжевый | Много низкоуверенных |

### 8.2 UX-правила
- Прогресс «Обработано X из Y».
- Блокировка дублирующих кликов при `loading=true`.
- Понятные ошибки из API (detail + validation).
- Явное пустое состояние.
- Базовая адаптивность (desktop-first), горизонтальный скролл таблиц.
- Осмысленные aria-label (минимум).
- Кнопка «Новый батч» сбрасывает state и возвращает на главную.
- Всегда показывать `pipeline_version`.

### 8.3 Показ источников (explainability)
В `AttributesTable` показывать: `evidence_text`, `source_spans[]` (field/text/start/end), `extraction_method`, `is_confirmed_in_text`.

## 9. Конфигурация и сборка

### 9.1 Vite конфиг
```ts
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } }
  },
  build: { outDir: 'dist', sourcemap: false, chunkSizeWarningLimit: 1000 }
})
```
В Docker-контейнере проксирование идёт через nginx (`/api` → `backend:8000`).

### 9.2 Переменные окружения
Только `VITE_*` для статического SPA:
```env
VITE_API_BASE_URL=/api/v1
VITE_DEFAULT_BATCH_SIZE=10
VITE_MAX_PREVIEW=20
VITE_SHOW_SOURCES=true
VITE_DEFAULT_THRESHOLD=0.80
```

### 9.3 Dockerfile (multi-stage)
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

**nginx.conf:** `location / { try_files $uri /index.html; }`, `location /api/ { proxy_pass http://backend:8000/api/; ... }`, gzip, `client_max_body_size`.

## 10. Сценарий развёртывания (локально)
```bash
# dev: backend (uvicorn) + frontend (npm run dev)
docker compose up --build  # единый стек: http://localhost/
```

## 11. Acceptance-критерии фронтенда
- [ ] Загрузка CSV/JSON, предпросмотр работает.
- [ ] Валидация минимального набора полей с понятным сообщением.
- [ ] Батч-обработка через `/api/v1/extract/batch`, прогресс.
- [ ] Результаты с `attribute_code`, `normalized_value`, `confidence`, `extraction_method`, `needs_review`.
- [ ] Подсветка low_confidence/needs_review.
- [ ] Экспорт CSV в формате `PredictionRow`.
- [ ] Показ `pipeline_version`, сводки батча.
- [ ] Отображение `evidence_text`/`source_spans` при наличии.
- [ ] Graceful-обработка ошибок API (422/500).
- [ ] Сброс «Новый батч» возвращает на главную.
- [ ] Работает через nginx-прокси в docker-compose.
- [ ] Базовый режим не ломается при `degraded`.

## 12. Нефункциональные требования фронтенда
- Производительность: батч N<=50 без заметных лагов (виртуализация не требуется для MVP).
- Надёжность: валидация + обработка сетевых ошибок.
- Типобезопасность: строгий TypeScript, общие типы с API.
- Малый бандл: избегать тяжёлых зависимостей.
- Кроссбраузерность: современный Chromium/Firefox/Edge.
- Zero-runtime secrets: только `VITE_*`.
- Простота: фокус на демонстрации пайплайна и выгрузке артефакта «предсказания по каждой карточке».
