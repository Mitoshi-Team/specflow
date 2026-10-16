import { Fragment, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import type {
  AttributePrediction,
  ExtractionResponseItem,
  Span,
} from "../schemas/api";

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

/** Текст упоминания в исходном тексте: `field: text [start–end]`. */
function spanLabel(span: Span): string {
  const range =
    span.start !== undefined && span.end !== undefined
      ? ` [${span.start}–${span.end}]`
      : "";
  return `${span.field}: ${span.text}${range}`;
}

type AttributesBlockProps = {
  attributes: AttributePrediction[];
  threshold?: number;
};

/**
 * Таблица атрибутов карточки (frontend.md, 6.2; design.md, §7–9):
 * `attribute_code`, `normalized_value`, `confidence`, `extraction_method`,
 * `evidence_text`, `source_spans`, `is_confirmed_in_text`.
 *
 * Числовое значение уверенности показывается всегда; при заданном пороге
 * значение ниже порога дополнительно выделяется текстовой пометкой, а не
 * только цветом (design.md, §8, §11). Отсутствующее подтверждение явно
 * помечается, а не придумывается (design.md, §7).
 */
function AttributesBlock({ attributes, threshold }: AttributesBlockProps) {
  const { t } = useTranslation();

  if (attributes.length === 0) {
    return (
      <p className="results-table__empty-attributes">
        {t("results.table.emptyAttributes")}
      </p>
    );
  }

  return (
    <table className="results-table__attributes">
      <thead>
        <tr>
          <th scope="col">{t("results.table.attributes.attribute")}</th>
          <th scope="col">{t("results.table.attributes.value")}</th>
          <th scope="col">{t("results.table.attributes.confidence")}</th>
          <th scope="col">{t("results.table.attributes.method")}</th>
          <th scope="col">{t("results.table.attributes.evidence")}</th>
        </tr>
      </thead>
      <tbody>
        {attributes.map((attribute, index) => {
          const isLow =
            threshold !== undefined && attribute.confidence < threshold;
          return (
            <tr key={`${attribute.attribute_code}-${index}`}>
              <td className="results-table__code">
                {attribute.attribute_code}
              </td>
              <td className="results-table__value">
                {attribute.normalized_value}
              </td>
              <td className="results-table__number">
                <span
                  className={`confidence${isLow ? " confidence--low" : ""}`}
                >
                  {attribute.confidence}
                  {isLow ? (
                    <span className="sr-only">
                      {" "}
                      {t("results.table.attributes.confidenceLow")}
                    </span>
                  ) : null}
                </span>
              </td>
              <td className="results-table__method">
                {attribute.extraction_method}
              </td>
              <td className="results-table__evidence">
                {attribute.evidence_text ? (
                  <span className="results-table__quote">
                    {attribute.evidence_text}
                  </span>
                ) : (
                  <span className="results-table__muted">
                    {t("results.table.attributes.noEvidence")}
                  </span>
                )}

                {attribute.source_spans &&
                attribute.source_spans.length > 0 ? (
                  <ul className="results-table__spans">
                    {attribute.source_spans.map((span, spanIndex) => (
                      <li key={spanIndex}>{spanLabel(span)}</li>
                    ))}
                  </ul>
                ) : null}

                <span
                  className={`results-table__confirmed${
                    attribute.is_confirmed_in_text
                      ? ""
                      : " results-table__confirmed--no"
                  }`}
                >
                  {attribute.is_confirmed_in_text
                    ? t("results.table.attributes.confirmed")
                    : t("results.table.attributes.notConfirmed")}
                </span>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

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
                      <AttributesBlock
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
