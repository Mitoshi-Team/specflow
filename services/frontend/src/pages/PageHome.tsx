import { useTranslation } from "react-i18next";

/** Главная страница (заглушка до реализации загрузки и запуска батча). */
export default function PageHome() {
  const { t } = useTranslation();

  return (
    <section className="page">
      <h1>{t("pages.home.title")}</h1>
      <p>{t("pages.home.description")}</p>
    </section>
  );
}
