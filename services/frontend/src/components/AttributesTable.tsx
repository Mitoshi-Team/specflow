import { useTranslation } from "react-i18next";

import type { AttributePrediction } from "../schemas/api";
import AttributeRow from "./AttributeRow";

export type AttributesTableProps = {
  /** Атрибуты одной карточки (api_contract.md, 3.2). */
  attributes: AttributePrediction[];
  /**
   * Порог уверенности, использованный в батче (design.md, §8). Прокидывается
   * в `AttributeRow` → `ConfidenceBadge`.
   */
  threshold?: number;
};

/**
 * Таблица атрибутов одной карточки (frontend.md, 6.2 `AttributesTable`;
 * design.md, §7–9). Колонки: код атрибута, каноническое значение, уверенность,
 * метод извлечения, подтверждение с explainability (`evidence_text`,
 * `source_spans[]`, `is_confirmed_in_text`).
 *
 * Пустой список атрибутов показывается явным пустым состоянием
 * (design.md, §7).
 */
export default function AttributesTable({
  attributes,
  threshold,
}: AttributesTableProps) {
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
        {attributes.map((attribute, index) => (
          <AttributeRow
            key={`${attribute.attribute_code}-${index}`}
            attribute={attribute}
            threshold={threshold}
          />
        ))}
      </tbody>
    </table>
  );
}
