import { useId, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { PREVIEW_MAX_ROWS } from "../constants";
import {
  hasMissingDescription,
  isFieldPresent,
  type PreviewField,
} from "../lib/inputValidation";
import type { ProductCardRequest } from "../schemas/api";
import EmptyState from "./EmptyState";

/**
 * Минимальная длина значения, начиная которой для строки показывается
 * действие раскрытия длинных ячеек (design.md, раздел 7: длинные
 * значения ограничиваются по высоте с возможностью раскрытия).
 */
const EXPAND_MIN_CHARS = 60;

const EMPTY_VALUE = "—";

/**
 * Значение поля карточки для ячейки предпросмотра. Поле без содержимого
 * (`isFieldPresent`) возвращает `undefined`, чтобы ячейка показала метку
 * пустого значения, а не выглядела заполненной (design.md, раздел 7).
 */
function fieldCellValue(
  card: ProductCardRequest,
  field: PreviewField,
): string | undefined {
  if (!isFieldPresent(card, field)) {
    return undefined;
  }
  return card[field] ?? "";
}

function hasLongValue(card: ProductCardRequest): boolean {
  const values = [
    card.product_id ?? "",
    card.title ?? "",
    card.description ?? "",
  ];
  return values.some((value) => value.length > EXPAND_MIN_CHARS);
}

export type DataPreviewProps = {
  /** Полный список разобранных карточек; показываются первые `maxRows`. */
  cards: ProductCardRequest[];
  /** Сколько первых строк показывать (по умолчанию `PREVIEW_MAX_ROWS`). */
  maxRows?: number;
};

/**
 * Предпросмотр первых строк загруженного файла (design.md, раздел 7;
 * frontend.md, разделы 5.1, 6.2 `DataPreview`).
 *
 * Длинные значения обрезаются по высоте; строку можно раскрыть явным
 * действием. Пустые поля показываются отдельной меткой, а не выглядят
 * как заполненные. Над таблицей — предупреждение, если хотя бы в одной
 * карточке нет описания: пайплайн использует только `title` и
 * `description` (api_contract.md, 3.1), поэтому других проверок состава
 * полей предпросмотр не делает.
 */
export default function DataPreview({
  cards,
  maxRows = PREVIEW_MAX_ROWS,
}: DataPreviewProps) {
  const { t } = useTranslation();
  const tableId = useId();
  const [expandedRows, setExpandedRows] = useState<ReadonlySet<number>>(
    () => new Set(),
  );

  const shown = Math.min(cards.length, maxRows);
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

  if (cards.length === 0) {
    return (
      <div className="preview">
        <EmptyState message={t("preview.empty")} />
      </div>
    );
  }

  return (
    <div className="preview">
      {hasMissingDescription(cards) ? (
        <p className="preview__validation" role="status">
          {t("preview.validation.missingDescription")}
        </p>
      ) : null}

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
                  {cell(
                    fieldCellValue(card, "title"),
                    index,
                    "preview__cell",
                  )}
                  {cell(
                    fieldCellValue(card, "description"),
                    index,
                    "preview__cell--wide",
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
