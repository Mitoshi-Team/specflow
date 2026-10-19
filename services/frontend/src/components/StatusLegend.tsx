import { useId, useState } from "react";
import { useTranslation } from "react-i18next";

import type { ExtractionStatus } from "../schemas/api";

export type StatusLegendProps = {
  /**
   * Порог уверенности, использованный в батче. Если неизвестен, показывается
   * общее пояснение без конкретного числа (design.md, §8: пороги определяет
   * backend и передаёт вызывающий код).
   */
  threshold?: number;
};

/**
 * Порядок статусов в легенде: от полностью успешного к пропущенному.
 * Полный набор статусов задан контрактом (api_contract.md, 3.3).
 */
const STATUSES: ExtractionStatus[] = [
  "ok",
  "low_confidence",
  "partial",
  "error",
  "skipped",
];

/**
 * Легенда результатов (frontend.md, 8.1; design.md, §8).
 *
 * Расшифровывает словами статусы карточек, смысл порога уверенности и
 * значение служебных колонок таблицы. Без этого низкая уверенность читалась
 * бы только по подсветке, а цвет не должен быть единственным носителем
 * смысла (design.md, §8, §11).
 *
 * Раздел свёрнут по умолчанию: это справочный материал, а раскрытая легенда
 * заслоняет таблицу результатов. Раскрывает панель вся строка заголовка —
 * кнопка занимает ширину шапки и содержит и текст, и галочку; состояние
 * дублируется для скринридеров через aria-expanded/aria-controls.
 */
export default function StatusLegend({ threshold }: StatusLegendProps) {
  const { t } = useTranslation();
  const contentId = useId();
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="status-legend">
      <h3 className="status-legend__title">
        <button
          type="button"
          className="status-legend__toggle"
          aria-expanded={expanded}
          aria-controls={contentId}
          onClick={() => setExpanded((value) => !value)}
        >
          {t("results.hints.title")}
          <span className="status-legend__chevron" aria-hidden="true" />
        </button>
      </h3>

      {expanded ? (
        <div className="status-legend__content" id={contentId}>
          <p className="status-legend__threshold">
            {threshold !== undefined
              ? t("results.hints.threshold", { threshold })
              : t("results.hints.thresholdUnknown")}
          </p>

          <dl className="status-legend__list">
            {STATUSES.map((status) => (
              <div className="status-legend__item" key={status}>
                <dt className="status-legend__term">
                  <span className={`status status--${status}`}>
                    {t(`results.status.${status}`)}
                  </span>
                </dt>
                <dd className="status-legend__description">
                  {t(`results.hints.status.${status}`)}
                </dd>
              </div>
            ))}
          </dl>

          <ul className="status-legend__notes">
            <li>{t("results.hints.columnLowConfidence")}</li>
            <li>{t("results.hints.columnNeedsReview")}</li>
          </ul>
        </div>
      ) : null}
    </div>
  );
}
