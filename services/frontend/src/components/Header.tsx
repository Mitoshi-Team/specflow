import { useCallback } from "react";
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
  const { t, i18n } = useTranslation();
  const location = useLocation();

  const sectionTitleKey = ROUTE_TITLE_KEYS[location.pathname];

  const currentLang = i18n.language === "en" ? "en" : "ru";
  const isRu = currentLang === "ru";
  const isEn = currentLang === "en";

  const changeLanguage = useCallback(
    (lang: "ru" | "en") => {
      if (lang === currentLang) {
        return;
      }
      void i18n.changeLanguage(lang);
    },
    [currentLang, i18n],
  );

  const handleSwitchRu = useCallback(() => changeLanguage("ru"), [changeLanguage]);
  const handleSwitchEn = useCallback(() => changeLanguage("en"), [changeLanguage]);

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
        <NavLink to="/" end className="header__tab">
          {t("nav.home")}
        </NavLink>
        <NavLink to="/results" className="header__tab">
          {t("nav.results")}
        </NavLink>
      </nav>

      <div
        className="lang-switch"
        role="group"
        aria-label={t("lang.ariaLabel") ?? "Переключить язык"}
      >
        <button
          type="button"
          className={isRu ? "header__tab header__tab--active" : "header__tab"}
          onClick={handleSwitchRu}
          aria-pressed={isRu}
        >
          {t("lang.ru")}
        </button>
        <button
          type="button"
          className={isEn ? "header__tab header__tab--active" : "header__tab"}
          onClick={handleSwitchEn}
          aria-pressed={isEn}
        >
          {t("lang.en")}
        </button>
      </div>
    </header>
  );
}
