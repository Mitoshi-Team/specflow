import { useId, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { PREVIEW_MAX_ROWS } from "../constants";
import type { ProductCardRequest } from "../schemas/api";

/**
 * Минимальная длина значения, начиная которой для строки показывается
 * действие раскрытия длинных ячеек (design.md, раздел 7: длинные
 * значения ограничиваются по высоте с возможностью раскрытия).
 */
const EXPAND_MIN_CHARS = 60;

const EMPTY_VALUE = "—";

function hasLongValue(card: ProductCardRequest): boolean {
  const values = [
    card.product_id,
    card.title,
    card.description,
    card.seller_attributes === undefined
      ? undefined
      : JSON.stringify(card.seller_attributes),
  ];
  return values.some(
    (value) => typeof value === "string" && value.length > EXPAND_MIN_CHARS,
  );
}

export type DataPreviewProps = {
  /** Полный список разобранных карточек; показываются первые N (PREVIEW_MAX_ROWS). */
  cards: ProductCardRequest[];
};

/**
 * Предпросмотр первых строк загруженного файла (design.md, раздел 7;
 * frontend.md, раздел 6.2 `DataPreview`).
 *
 * Длинные значения обрезаются по высоте; строку можно раскрыть явным
 * действием. Пустые поля показываются отдельной меткой, а не выглядят
 * как заполненные.
 */
export default function DataPreview({ cards }: DataPreviewProps) {
  const { t } = useTranslation();
  const tableId = useId();
  const [expandedRows, setExpandedRows] = useState<ReadonlySet<number>>(
    () => new Set(),
  );

  const shown = Math.min(cards.length, PREVIEW_MAX_ROWS);
  const visibleCards = cards.slice(0, shown);

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

  const cell = (
    value: string | undefined,
    index: number,
    className: string,
  ): ReactNode => {
    if (value === undefined || value === "") {
      return (
        <td className={className}>
          <span className="preview__empty" title={t("preview.emptyField")}>
            {EMPTY_VALUE}
          </span>
        </td>
      );
    }
    const expanded = expandedRows.has(index);
    return (
      <td
        className={`${className}${expanded ? " preview__cell--expanded" : ""}`}
      >
        <span className="preview__clamp">{value}</span>
      </td>
    );
  };

  return (
    <div className="preview">
      <div className="preview__scroll">
        <table className="preview__table" aria-label={t("preview.title")}>
          <thead>
            <tr>
              <th scope="col" className="preview__number">
                {t("preview.columns.number")}
              </th>
              <th scope="col">{t("preview.columns.productId")}</th>
              <th scope="col" className="preview__cell--wide">
                {t("preview.columns.title")}
              </th>
              <th scope="col" className="preview__cell--wide">
                {t("preview.columns.description")}
              </th>
              <th scope="col" className="preview__cell--wide">
                {t("preview.columns.attributes")}
              </th>
              <th scope="col" className="preview__action">
                <span className="sr-only">{t("preview.columns.action")}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {visibleCards.map((card, index) => {
              const expanded = expandedRows.has(index);
              return (
                <tr
                  key={`${tableId}-${index}`}
                  id={`${tableId}-row-${index}`}
                >
                  <td className="preview__number">{index + 1}</td>
                  {cell(card.product_id, index, "preview__mono")}
                  {cell(card.title, index, "preview__cell")}
                  {cell(card.description, index, "preview__cell--wide")}
                  {cell(
                    card.seller_attributes === undefined
                      ? undefined
                      : JSON.stringify(card.seller_attributes),
                    index,
                    "preview__cell--wide preview__mono",
                  )}
                  <td className="preview__action">
                    {hasLongValue(card) ? (
                      <button
                        type="button"
                        className="link"
                        aria-expanded={expanded}
                        aria-controls={`${tableId}-row-${index}`}
                        onClick={() => toggleRow(index)}
                      >
                        {expanded
                          ? t("preview.collapse")
                          : t("preview.expand")}
                      </button>
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {cards.length > shown ? (
        <p className="panel__hint">
          {t("preview.shown", { shown, total: cards.length })}
        </p>
      ) : null}
    </div>
  );
}
