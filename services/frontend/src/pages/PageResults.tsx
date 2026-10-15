import { useTranslation } from "react-i18next";

/**
 * Страница результатов пакетной обработки (frontend.md, сценарий 3).
 * Таблица результатов появится после запуска батча — до тех пор
 * показывается пустое состояние (design.md, раздел 7).
 */
export default function PageResults() {
  const { t } = useTranslation();

  return (
    <section className="page">
      <div>
        <h1>{t("pages.results.title")}</h1>
        <p className="page__description">{t("pages.results.description")}</p>
      </div>

      <div className="empty-state" role="status">
        {t("pages.results.empty")}
      </div>
    </section>
  );
}
