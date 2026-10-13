import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

type ApiStatus = "loading" | "ok" | "error";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export default function App() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<ApiStatus>("loading");

  useEffect(() => {
    let cancelled = false;

    fetch(`${API_BASE_URL}/api/health`)
      .then((response): ApiStatus => (response.ok ? "ok" : "error"))
      .catch((): ApiStatus => "error")
      .then((next) => {
        if (!cancelled) {
          setStatus(next);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="app">
      <h1>{t("app.title")}</h1>
      <p>{t("app.subtitle")}</p>
      <p>
        {t("app.apiStatus")}: <strong>{t(`app.status.${status}`)}</strong>
      </p>
    </main>
  );
}
