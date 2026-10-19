import { useState } from "react";
import { useTranslation } from "react-i18next";

import EmptyState from "../components/EmptyState";
import ExportCsvButton from "../components/ExportCsvButton";
import ResultsSummary from "../components/ResultsSummary";
import ResultsTable from "../components/ResultsTable";
import StatusLegend from "../components/StatusLegend";
import { readLastBatch } from "../lib/lastBatch";
import type { StoredBatch } from "../lib/lastBatch";

/**
 * Страница результатов пакетной обработки (frontend.md, сценарий 3;
 * design.md, §7). Показывает сводку батча, легенду статусов и таблицу
 * результатов с экспортом CSV; до запуска батча — пустое состояние.
 *
 * Данные берутся из последнего сохранённого батча (`lib/lastBatch`), а не из
 * `location.state`: состояние маршрута теряется при переходе на страницу из
 * навигации и при перезагрузке, из-за чего результаты пропадали.
 */
export default function PageResults() {
  const { t } = useTranslation();
  // Читаем сохранённый батч один раз при монтировании: повторные переходы на
  // этот же маршрут не должны сбрасывать уже показанные результаты.
  const [batch] = useState<StoredBatch | null>(() => readLastBatch());
  const response = batch?.response ?? null;

  return (
    <section className="page">
      <div>
        <h1>{t("pages.results.title")}</h1>
        <p className="page__description">{t("pages.results.description")}</p>
      </div>

      {response === null ? (
        <EmptyState message={t("pages.results.empty")} />
      ) : (
        <>
          <section className="panel">
            <h2 className="panel__title">{t("results.summary.title")}</h2>
            <ResultsSummary response={response} />
          </section>

          <section className="panel">
            <div className="panel__header">
              <h2 className="panel__title">{t("results.table.caption")}</h2>
              <div className="panel__actions">
                <ExportCsvButton results={response.results} cards={batch?.cards} />
              </div>
            </div>

            <StatusLegend threshold={batch?.threshold} />
            <ResultsTable results={response.results} threshold={batch?.threshold} />
          </section>
        </>
      )}
    </section>
  );
}
