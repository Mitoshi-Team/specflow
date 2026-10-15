# Frontend

Веб-приложение SpecFlow на React, TypeScript и Vite. Тексты интерфейса
локализованы через i18next.

## Устройство

- `src/main.tsx` — точка входа (включая `BrowserRouter`).
- `src/App.tsx` — корневой компонент с маршрутами.
- `src/components/` — переиспользуемые компоненты (`AppLayout`, `Header`,
  `FileUpload`).
- `src/pages/` — страницы (`PageHome`, `PageResults`).
- `src/hooks/` — кастомные хуки (`useApiHealth`, `useFileParser`).
- `src/lib/` — утилиты (`fileParser` — разбор CSV/JSON/TSV).
- `src/constants.ts` — константы уровня приложения (в т.ч. параметры
  загрузки файлов).
- `src/i18n.ts` — конфигурация i18next.
- `src/locales/` — переводы (`ru`, `en`).
- `src/schemas/api.ts` — TS-типы, синхронизированные с API-контрактом
  (`openspec/specs/api_contract.md`).
- `src/api/` — клиент API на fetch: единая точка отправки запросов
  (`client.ts`), типизированные методы по эндпоинтам (`index.ts`).
- `vite.config.ts` — конфигурация Vite и dev-сервера.

## Маршруты

- `/` — `PageHome` (главная).
- `/results` — `PageResults` (результаты батча).

Страницы рендерятся внутри `AppLayout` (Header + область контента).
`Header` показывает индикатор здоровья API: хук `useApiHealth` периодически
опрашивает `GET /api/v1/health` (интервал — `API_HEALTH_POLL_INTERVAL_MS`).

## Загрузка карточек

- `FileUpload` — drag&Drop и выбор файла (CSV/JSON/TSV), отображает состояния
  ожидания, перетаскивания, обработки, ошибки и успеха. Компонент не разбирает
  файл: он принимает статус и ошибки снаружи.
- `useFileParser` — разбор выбранного файла: определение формата по расширению,
  чтение, парсинг и валидация минимального набора полей. Возвращает карточки
  (`ProductCardRequest[]`) либо типизированную ошибку (`FileParseError`).
- `lib/fileParser.ts` — чистые функции разбора (без React), покрытые тестами.

Формат определяется по расширению; CSV/TSV разбираются через `papaparse`.
Валидация строки: минимум одно непустое из `title`, `description`,
`seller_attributes`; `seller_attributes` в CSV/TSV должен быть корректным JSON.
Разобранные карточки совпадают с типом `ProductCardRequest`
(`src/schemas/api.ts`).

## Запуск

```bash
npm install
npm run dev        # dev-сервер Vite (http://localhost:5173)
npm run build      # проверка типов и production-сборка
npm run preview    # предпросмотр собранного приложения
npm run typecheck  # только проверка типов
npm test           # unit-тесты (vitest)
```

Базовый URL API задаётся переменной `VITE_API_BASE_URL`. Если она пустая,
запросы идут на текущий origin (`/api/v1/...`) — так работает в docker через
reverse-proxy nginx.
