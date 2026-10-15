# Frontend

Веб-приложение SpecFlow на React, TypeScript и Vite. Тексты интерфейса
локализованы через i18next.

## Устройство

- `src/main.tsx` — точка входа (включая `BrowserRouter`).
- `src/App.tsx` — корневой компонент с маршрутами.
- `src/components/` — переиспользуемые компоненты (`AppLayout`, `Header`).
- `src/pages/` — страницы (`PageHome`, `PageResults`).
- `src/hooks/` — кастомные хуки (`useApiHealth`).
- `src/constants.ts` — константы уровня приложения.
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
