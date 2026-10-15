import { useTranslation } from "react-i18next";
import { NavLink, useLocation } from "react-router-dom";

/**
 * Ключ перевода с названием раздела для каждого маршрута оболочки
 * (design.md, раздел 6: в шапке рядом с логотипом показывается название
 * текущего раздела). Маршруты без записи скрыты, чтобы не показывать
 * неверное название.
 */
const ROUTE_TITLE_KEYS: Record<string, string> = {
  "/": "pages.home.title",
  "/results": "pages.results.title",
};

/**
 * Верхняя панель: логотип SPECflow, название раздела и навигация.
 *
 * Служебные индикаторы (версия пайплайна, статус API) в шапке не
 * показываются (design.md, раздел 6).
 */
export default function Header() {
  const { t } = useTranslation();
  const location = useLocation();

  const sectionTitleKey = ROUTE_TITLE_KEYS[location.pathname];

  return (
    <header className="header">
      <NavLink to="/" className="header__brand">
        <img
          className="header__logo"
          src="/specflow_logo.svg"
          alt={t("app.title")}
        />
      </NavLink>

      {sectionTitleKey ? (
        <span className="header__section">{t(sectionTitleKey)}</span>
      ) : null}

      <nav className="header__nav">
        <NavLink to="/" end className="header__nav-link">
          {t("nav.home")}
        </NavLink>
        <NavLink to="/results" className="header__nav-link">
          {t("nav.results")}
        </NavLink>
      </nav>
    </header>
  );
}
