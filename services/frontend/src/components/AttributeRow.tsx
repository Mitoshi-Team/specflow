import { useTranslation } from "react-i18next";

import type { AttributePrediction, Span } from "../schemas/api";
import ConfidenceBadge from "./ConfidenceBadge";
import MethodBadge from "./MethodBadge";

export type AttributeRowProps = {
  /** Атрибут карточки (api_contract.md, 3.2). */
  attribute: AttributePrediction;
  /**
   * Порог уверенности, использованный в батче; передаётся в `ConfidenceBadge`
   * (design.md, §8).
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

/**
 * Строка атрибута (frontend.md, 6.2 `AttributeRow`; design.md, §7–9).
 *
 * Показывает каноническое значение, уверенность (`ConfidenceBadge`), метод
 * извлечения (`MethodBadge`) и explainability: `evidence_text` и `source_spans`.
 * Отсутствующий подтверждающий фрагмент явно помечается, а не придумывается
 * (design.md, §7); флаг `is_confirmed_in_text=false` выделяется как критичное
 * противоречие grounding (design.md, §8).
 */
export default function AttributeRow({
  attribute,
  threshold,
}: AttributeRowProps) {
  const { t } = useTranslation();

  return (
    <tr>
      <td className="results-table__code">{attribute.attribute_code}</td>
      <td className="results-table__value">{attribute.normalized_value}</td>
      <td className="results-table__number">
        <ConfidenceBadge
          confidence={attribute.confidence}
          threshold={threshold}
        />
      </td>
      <td className="results-table__method">
        <MethodBadge method={attribute.extraction_method} />
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

        {attribute.source_spans && attribute.source_spans.length > 0 ? (
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
}
