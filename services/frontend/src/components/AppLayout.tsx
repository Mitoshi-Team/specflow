import { Outlet } from "react-router-dom";

import Header from "./Header";

/**
 * Общий каркас приложения: Header и область контента для страниц
 * (frontend.md, раздел 6.1). Страницы рендерятся через вложенные маршруты.
 */
export default function AppLayout() {
  return (
    <div className="layout">
      <Header />
      <main className="layout__content">
        <Outlet />
      </main>
    </div>
  );
}
