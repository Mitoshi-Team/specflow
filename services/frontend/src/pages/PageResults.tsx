import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";

import EmptyState from "../components/EmptyState";
import ExportCsvButton from "../components/ExportCsvButton";
import ResultsSummary from "../components/ResultsSummary";
import ResultsTable from "../components/ResultsTable";
import StatusLegend from "../components/StatusLegend";
import type { BatchExtractResponse, ProductCardRequest } from "../schemas/api";

/**
 * Данные, передаваемые на страницу результатов после успешного батча
 * (frontend.md, сценарий 2, шаг 4; design.md, §7).
 *
 * Страница получает их через состояние маршрута (`location.state`), а не через
 * повторный запрос: API не хранит выполненные батчи (api_contract.md).
 * При отсутствии данных (прямой переход по ссылке, перезагрузка) показывается
 * пустое состояние.
 */
export type ResultsLocationState = {
  /** Успешный ответ батча — источник сводки и строк таблицы. */
  response: BatchExtractResponse;
  /**
   * Порог уверенности батча. Нужен для подсветки и пояснения низкоуверенных
   * атрибутов (design.md, §8: пороги определяет backend и передаёт вызывающий
   * код); может отсутствовать, если батч запускался без переопределения.
   */
  threshold?: number;
  /** Исходные карточки батча — источник колонки `title` в CSV-экспорте. */
  cards?: ProductCardRequest[];
};

/**
 * Страница результатов пакетной обработки (frontend.md, сценарий 3;
 * design.md, §7). Показывает сводку батча, легенду статусов и таблицу
 * результатов с экспортом CSV; до запуска батча — пустое состояние.
 */
export default function PageResults() {
  const { t } = useTranslation();
  const location = useLocation();
  const state = location.state as ResultsLocationState | null;
  const response = state?.response ?? null;

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
                <ExportCsvButton
                  results={response.results}
                  cards={state?.cards}
                />
              </div>
            </div>

            <StatusLegend threshold={state?.threshold} />
            <ResultsTable
              results={response.results}
              threshold={state?.threshold}
            />
          </section>
        </>
      )}
    </section>
  );
}
