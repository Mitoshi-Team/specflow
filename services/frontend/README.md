# Frontend

Веб-приложение SpecFlow на React, TypeScript и Vite. Тексты интерфейса
локализованы через i18next.

## Устройство

- `src/main.tsx` — точка входа.
- `src/App.tsx` — корневой компонент.
- `src/i18n.ts` — конфигурация i18next.
- `src/locales/` — переводы (`ru`, `en`).
- `vite.config.ts` — конфигурация Vite и dev-сервера.

## Запуск

```bash
npm install
npm run dev        # dev-сервер Vite (http://localhost:5173)
npm run build      # проверка типов и production-сборка
npm run preview    # предпросмотр собранного приложения
```

Базовый URL API задаётся переменной `VITE_API_BASE_URL`. Если она пустая,
запросы идут на текущий origin (`/api/...`) — так работает в docker через
reverse-proxy nginx.
