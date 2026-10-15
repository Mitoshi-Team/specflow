import { useTranslation } from "react-i18next";
import { NavLink } from "react-router-dom";

import { useApiHealth } from "../hooks/useApiHealth";

/**
 * Шапка приложения: бренд, навигация и индикатор здоровья API.
 * Состояние индикатора берётся из `useApiHealth` (frontend.md, раздел 6.1).
 */
export default function Header() {
  const { t } = useTranslation();
  const health = useApiHealth();

  return (
    <header className="header">
      <NavLink to="/" className="header__brand">
        {t("app.title")}
      </NavLink>

      <nav className="header__nav">
        <NavLink to="/" end className="header__nav-link">
          {t("nav.home")}
        </NavLink>
        <NavLink to="/results" className="header__nav-link">
          {t("nav.results")}
        </NavLink>
      </nav>

      <div
        className={`health health--${health}`}
        role="status"
        aria-label={`${t("health.label")}: ${t(`health.${health}`)}`}
      >
        <span className="health__dot" aria-hidden="true" />
        <span className="health__text">{t(`health.${health}`)}</span>
      </div>
    </header>
  );
}
