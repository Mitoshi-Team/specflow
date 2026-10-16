import { useId, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { PREVIEW_MAX_ROWS } from "../constants";
import {
  REQUIRED_INPUT_FIELDS,
  isFieldPresent,
  validateInput,
  type InputValidationResult,
  type RequiredInputField,
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
  field: RequiredInputField,
): string | undefined {
  if (!isFieldPresent(card, field)) {
    return undefined;
  }
  if (field === "seller_attributes") {
    return JSON.stringify(card.seller_attributes);
  }
  return card[field] ?? "";
}

function hasLongValue(card: ProductCardRequest): boolean {
  const values = [
    card.product_id,
    ...REQUIRED_INPUT_FIELDS.map((field) => fieldCellValue(card, field)),
  ];
  return values.some(
    (value) => typeof value === "string" && value.length > EXPAND_MIN_CHARS,
  );
}

/**
 * Ключ текста сводки валидации (i18n): перечень недостающих полей,
 * подтверждение их наличия либо ошибка, когда нет ни одного обязательного
 * поля (frontend.md, 6.3).
 */
function summaryKey(validation: InputValidationResult): string {
  if (!validation.valid) {
    return "preview.validation.noContent";
  }
  if (validation.missingFields.length > 0) {
    return "preview.validation.missingFields";
  }
  return "preview.validation.allPresent";
}

export type DataPreviewProps = {
  /** Полный список разобранных карточек; показываются первые `maxRows`. */
  cards: ProductCardRequest[];
  /**
   * Результат валидации обязательных полей. По умолчанию считается из
   * `cards` через `validateInput`, поэтому вызывающему коду достаточно
   * передать карточки; проп нужен, когда результат уже посчитан снаружи
   * (например, в тестах).
   */
  validation?: InputValidationResult;
  /** Сколько первых строк показывать (по умолчанию `PREVIEW_MAX_ROWS`). */
  maxRows?: number;
};

/**
 * Предпросмотр первых строк загруженного файла (design.md, раздел 7;
 * frontend.md, разделы 5.1, 6.2 `DataPreview`, 6.3).
 *
 * Длинные значения обрезаются по высоте; строку можно раскрыть явным
 * действием. Пустые поля показываются отдельной меткой, а не выглядят
 * как заполненные. Над таблицей — сводка валидации обязательных полей
 * title/description/seller_attributes.
 */
export default function DataPreview({
  cards,
  validation,
  maxRows = PREVIEW_MAX_ROWS,
}: DataPreviewProps) {
  const { t } = useTranslation();
  const tableId = useId();
  const [expandedRows, setExpandedRows] = useState<ReadonlySet<number>>(
    () => new Set(),
  );

  const inputValidation = validation ?? validateInput(cards);
  const missingLabels = inputValidation.missingFields
    .map((field) => t(`preview.columns.${field}`))
    .join(", ");

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
      <p
        className={`preview__validation${
          inputValidation.valid ? "" : " preview__validation--error"
        }`}
        role={inputValidation.valid ? "status" : "alert"}
      >
        {t(summaryKey(inputValidation), { fields: missingLabels })}
      </p>

      <ul className="preview__fields">
        {REQUIRED_INPUT_FIELDS.map((field) => {
          const present = inputValidation.presentFields.includes(field);
          return (
            <li
              key={field}
              className={`preview__field preview__field--${
                present ? "present" : "missing"
              }`}
            >
              <span className="preview__field-name">
                {t(`preview.columns.${field}`)}
              </span>
              <span className="preview__field-state">
                {present
                  ? t("preview.validation.present")
                  : t("preview.validation.missing")}
              </span>
            </li>
          );
        })}
      </ul>

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
                {t("preview.columns.seller_attributes")}
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
                  {cell(
                    fieldCellValue(card, "seller_attributes"),
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
