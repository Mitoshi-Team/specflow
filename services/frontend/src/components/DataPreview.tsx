import { useTranslation } from "react-i18next";

import { DEFAULT_MAX_PREVIEW } from "../constants";
import {
  REQUIRED_INPUT_FIELDS,
  isFieldPresent,
  type InputValidationResult,
  type RequiredInputField,
} from "../lib/inputValidation";
import type { ProductCardRequest } from "../schemas/api";

export type DataPreviewProps = {
  /** Разобранные карточки (например, из `useFileParser`). */
  cards: ProductCardRequest[];
  /** Результат валидации обязательных полей (`validateInput`). */
  validation: InputValidationResult;
  /** Максимум отображаемых строк (frontend.md, 5.1, 9.2). */
  maxRows?: number;
};

/** Строковое представление непустого поля карточки. */
function stringifyField(
  card: ProductCardRequest,
  field: RequiredInputField,
): string {
  switch (field) {
    case "title":
      return card.title ?? "";
    case "description":
      return card.description ?? "";
    case "seller_attributes":
      return JSON.stringify(card.seller_attributes ?? {});
  }
}

/**
 * Предпросмотр загруженных карточек: первые `maxRows` строк и результат
 * валидации обязательных полей title/description/seller_attributes
 * (frontend.md, 5.1; разделы 6.2 и 6.3). Отсутствующие поля явно помечаются
 * как в сводке, так и в ячейках таблицы.
 */
export default function DataPreview({
  cards,
  validation,
  maxRows = DEFAULT_MAX_PREVIEW,
}: DataPreviewProps) {
  const { t } = useTranslation();
  const visibleCards = cards.slice(0, maxRows);
  const missingLabels = validation.missingFields
    .map((field) => t(`dataPreview.columns.${field}`))
    .join(", ");

  return (
    <section
      className={`data-preview${
        validation.valid ? "" : " data-preview--invalid"
      }`}
    >
      <h2 className="data-preview__title">{t("dataPreview.title")}</h2>

      {validation.valid ? (
        <p className="data-preview__validation" role="status">
          {validation.missingFields.length === 0
            ? t("dataPreview.validation.allPresent")
            : t("dataPreview.validation.missingFields", { fields: missingLabels })}
        </p>
      ) : (
        <p
          className="data-preview__validation data-preview__validation--error"
          role="alert"
        >
          {t("dataPreview.validation.noContent")}
        </p>
      )}

      <ul className="data-preview__fields">
        {REQUIRED_INPUT_FIELDS.map((field) => {
          const present = validation.presentFields.includes(field);
          return (
            <li
              key={field}
              className={`data-preview__field data-preview__field--${
                present ? "present" : "missing"
              }`}
            >
              <span className="data-preview__field-name">
                {t(`dataPreview.columns.${field}`)}
              </span>
              <span className="data-preview__field-state">
                {present
                  ? t("dataPreview.validation.present")
                  : t("dataPreview.validation.missing")}
              </span>
            </li>
          );
        })}
      </ul>

      {visibleCards.length === 0 ? (
        <p className="data-preview__empty">{t("dataPreview.empty")}</p>
      ) : (
        <>
          <table className="data-preview__table">
            <thead>
              <tr>
                <th scope="col">{t("dataPreview.columns.product_id")}</th>
                {REQUIRED_INPUT_FIELDS.map((field) => (
                  <th key={field} scope="col">
                    {t(`dataPreview.columns.${field}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visibleCards.map((card, index) => (
                <tr key={card.product_id ?? index}>
                  <td>{card.product_id ?? t("dataPreview.emptyValue")}</td>
                  {REQUIRED_INPUT_FIELDS.map((field) => {
                    const present = isFieldPresent(card, field);
                    return (
                      <td
                        key={field}
                        className={
                          present ? undefined : "data-preview__cell--missing"
                        }
                      >
                        {present
                          ? stringifyField(card, field)
                          : t("dataPreview.emptyValue")}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="data-preview__count">
            {t("dataPreview.rowCount", {
              shown: visibleCards.length,
              total: cards.length,
            })}
          </p>
        </>
      )}
    </section>
  );
}
