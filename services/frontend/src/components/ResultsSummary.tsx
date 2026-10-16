import { useTranslation } from "react-i18next";

import type { BatchExtractResponse } from "../schemas/api";

export type ResultsSummaryProps = {
  /** Ответ батча — источник сводки и метаданных (api_contract.md, 3.5). */
  response: BatchExtractResponse;
};

/**
 * Сводка батча (frontend.md, 6.2 `ResultsSummary`, сценарий 3; design.md, §7).
 *
 * Показываются только значения, доступные из API-контракта BatchExtractResponse
 * (`total`, `ok`, `low_confidence`, `errors`), плюс вычисленное по результатам
 * число записей с `needs_review` и метаданные батча (`batch_id`,
 * `pipeline_version` записей, `processing_time_ms_total`). Отсутствующие
 * опциональные поля не отображаются (design.md, §7).
 */
export default function ResultsSummary({ response }: ResultsSummaryProps) {
  const { t } = useTranslation();

  const needsReviewCount = response.results.filter(
    (result) => result.needs_review,
  ).length;

  // Версия пайплайна задана на уровне записи (api_contract.md, 3.3); сводка
  // показывает уникальные значения, чтобы не дублировать одну и ту же метку.
  const pipelineVersions = Array.from(
    new Set(response.results.map((result) => result.pipeline_version)),
  );

  const metrics: { key: string; value: number }[] = [
    { key: "total", value: response.total },
    { key: "ok", value: response.ok },
    { key: "lowConfidence", value: response.low_confidence },
    { key: "errors", value: response.errors },
    { key: "needsReview", value: needsReviewCount },
  ];

  return (
    <div className="results-summary">
      <dl className="results-summary__metrics">
        {metrics.map((metric) => (
          <div className="results-summary__metric" key={metric.key}>
            <dt className="results-summary__label">
              {t(`results.summary.${metric.key}`)}
            </dt>
            <dd className="results-summary__value">{metric.value}</dd>
          </div>
        ))}
      </dl>

      {response.batch_id !== undefined ||
      pipelineVersions.length > 0 ||
      response.processing_time_ms_total !== undefined ? (
        <dl className="results-summary__meta">
          {response.batch_id !== undefined ? (
            <div className="results-summary__meta-item">
              <dt>{t("results.summary.batchId")}</dt>
              <dd className="results-summary__meta-value results-summary__meta-value--mono">
                {response.batch_id}
              </dd>
            </div>
          ) : null}

          {pipelineVersions.length > 0 ? (
            <div className="results-summary__meta-item">
              <dt>{t("results.summary.pipelineVersion")}</dt>
              <dd className="results-summary__meta-value results-summary__meta-value--mono">
                {pipelineVersions.join(", ")}
              </dd>
            </div>
          ) : null}

          {response.processing_time_ms_total !== undefined ? (
            <div className="results-summary__meta-item">
              <dt>{t("results.summary.processingTime")}</dt>
              <dd className="results-summary__meta-value results-summary__meta-value--mono">
                {response.processing_time_ms_total}
              </dd>
            </div>
          ) : null}
        </dl>
      ) : null}
    </div>
  );
}
