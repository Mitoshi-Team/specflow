import { useTranslation } from "react-i18next";

/** Страница результатов батча (заглушка до реализации отображения). */
export default function PageResults() {
  const { t } = useTranslation();

  return (
    <section className="page">
      <h1>{t("pages.results.title")}</h1>
      <p>{t("pages.results.description")}</p>
    </section>
  );
}
