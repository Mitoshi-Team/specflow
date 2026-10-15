import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { getHealth } from "./api";

type ApiStatus = "loading" | "ok" | "error";

export default function App() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<ApiStatus>("loading");

  useEffect(() => {
    let cancelled = false;

    getHealth()
      .then((): ApiStatus => "ok")
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
