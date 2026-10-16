import { Fragment, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import type { ExtractionResponseItem } from "../schemas/api";
import AttributesTable from "./AttributesTable";

/**
 * Метка отсутствующего значения (design.md, §7: пустые поля показываются
 * отдельным знаком, а не выглядят заполненными).
 */
const EMPTY_VALUE = "—";

export type ResultsTableProps = {
  /** Результаты обработки по каждой карточке (api_contract.md, 3.3). */
  results: ExtractionResponseItem[];
  /**
   * Порог уверенности, использованный в батче. Нужен только для подсветки
   * атрибутов с `confidence < threshold` (frontend.md, сценарий 3). Значение
   * задаёт вызывающий код; компонент не вводит собственных порогов
   * (design.md, §8: пороги определяет backend/продуктовая логика).
   */
  threshold?: number;
};

/** Число колонок основной таблицы — нужно для `colSpan` блока атрибутов. */
const COLUMN_COUNT = 7;

/**
 * Таблица результатов по карточкам с раскрытием атрибутов (frontend.md, 6.2
 * `ResultsTable`, сценарий 3; design.md, §7).
 *
 * Колонки карточек: `product_id`, категория, `status`, `needs_review`,
 * `low_confidence_count`, `processing_time_ms`. Раскрывающийся блок атрибутов
 * показывает `AttributesBlock`. Сортировка, фильтрация и пагинация в
 * спецификациях не заданы и здесь не реализуются.
 */
export default function ResultsTable({
  results,
  threshold,
}: ResultsTableProps) {
  const { t } = useTranslation();
  const tableId = useId();
  const [expandedRows, setExpandedRows] = useState<ReadonlySet<number>>(
    () => new Set(),
  );

  const toggleRow = (index: number): void => {
    setExpandedRows((previous) => {
      const next = new Set(previous);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  if (results.length === 0) {
    return (
      <p className="empty-state" role="status">
        {t("results.table.empty")}
      </p>
    );
  }

  return (
    <div className="results-table__scroll">
      <table className="results-table" aria-label={t("results.table.caption")}>
        <thead>
          <tr>
            <th scope="col">{t("results.table.columns.product")}</th>
            <th scope="col">{t("results.table.columns.category")}</th>
            <th scope="col">{t("results.table.columns.status")}</th>
            <th scope="col">{t("results.table.columns.needsReview")}</th>
            <th scope="col">
              {t("results.table.columns.lowConfidenceCount")}
            </th>
            <th scope="col">{t("results.table.columns.processingTime")}</th>
            <th scope="col" className="results-table__action">
              <span className="sr-only">{t("results.table.columns.action")}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {results.map((result, index) => {
            const expanded = expandedRows.has(index);
            const rowId = `${tableId}-row-${index}`;
            const detailsId = `${tableId}-details-${index}`;
            return (
              <Fragment key={rowId}>
                <tr id={rowId}>
                  <td className="results-table__code">
                    {result.product_id ?? EMPTY_VALUE}
                  </td>
                  <td>{result.category_name ?? result.category_id ?? EMPTY_VALUE}</td>
                  <td>
                    <span className={`status status--${result.status}`}>
                      {t(`results.status.${result.status}`)}
                    </span>
                  </td>
                  <td>
                    {result.needs_review ? (
                      <span className="flag flag--review">
                        {t("results.needsReview.yes")}
                      </span>
                    ) : (
                      <span className="results-table__muted">{EMPTY_VALUE}</span>
                    )}
                  </td>
                  <td className="results-table__number">
                    {result.low_confidence_count ?? EMPTY_VALUE}
                  </td>
                  <td className="results-table__number">
                    {result.processing_time_ms ?? EMPTY_VALUE}
                  </td>
                  <td className="results-table__action">
                    <button
                      type="button"
                      className="link"
                      aria-expanded={expanded}
                      aria-controls={detailsId}
                      onClick={() => toggleRow(index)}
                    >
                      {expanded
                        ? t("results.table.collapse")
                        : t("results.table.expand")}
                    </button>
                  </td>
                </tr>

                {expanded ? (
                  <tr>
                    <td
                      className="results-table__details"
                      id={detailsId}
                      colSpan={COLUMN_COUNT}
                    >
                      <AttributesTable
                        attributes={result.attributes}
                        threshold={threshold}
                      />
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
