import { useId, useState } from "react";
import type { ChangeEvent } from "react";
import { useTranslation } from "react-i18next";

import type { ApiError } from "../api";
import {
  CONFIDENCE_THRESHOLD_STEP,
  DEFAULT_BATCH_SIZE,
  DEFAULT_CONFIDENCE_THRESHOLD,
  MAX_BATCH_SIZE,
  MAX_CONFIDENCE_THRESHOLD,
  MIN_BATCH_SIZE,
  MIN_CONFIDENCE_THRESHOLD,
} from "../constants";
import type {
  BatchProgress,
  BatchSettings,
  BatchStatus,
} from "../hooks/useBatchExtract";
import type { BatchExtractResponse, ProductCardRequest } from "../schemas/api";
import ErrorBanner from "./ErrorBanner";

export type BatchControlsProps = {
  /** Разобранные карточки: кнопка активна только при непустом наборе. */
  cards: ProductCardRequest[];
  status: BatchStatus;
  progress: BatchProgress;
  /** Ошибка запроса (формат ErrorResponse, api_contract.md, раздел 3.8). */
  error: ApiError | null;
  /** Ответ успешного батча — источник сводки и частичных ошибок. */
  response: BatchExtractResponse | null;
  onStart: (
    items: ProductCardRequest[],
    settings: BatchSettings,
  ) => Promise<void>;
  onReset: () => void;
};

/**
 * Настройки батча, кнопки «Обработать»/«Сброс», прогресс «Обработано X из Y»
 * и ошибки API (frontend.md, раздел 6.2; design.md, раздел 7).
 *
 * Компонент владеет только введением настроек; запуск, прогресс и ошибки
 * приходят снаружи через `useBatchExtract` (логика отделена от UI).
 */
export default function BatchControls({
  cards,
  status,
  progress,
  error,
  response,
  onStart,
  onReset,
}: BatchControlsProps) {
  const { t } = useTranslation();
  const sizeId = useId();
  const thresholdId = useId();
  const sizeHintId = `${sizeId}-hint`;
  const thresholdHintId = `${thresholdId}-hint`;

  const [batchSizeValue, setBatchSizeValue] = useState(String(DEFAULT_BATCH_SIZE));
  const [thresholdValue, setThresholdValue] = useState(
    String(DEFAULT_CONFIDENCE_THRESHOLD),
  );

  const batchSize = Number(batchSizeValue);
  const threshold = Number(thresholdValue);
  const batchSizeValid =
    Number.isInteger(batchSize) &&
    batchSize >= MIN_BATCH_SIZE &&
    batchSize <= MAX_BATCH_SIZE;
  const thresholdValid =
    Number.isFinite(threshold) &&
    threshold >= MIN_CONFIDENCE_THRESHOLD &&
    threshold <= MAX_CONFIDENCE_THRESHOLD;

  const hasCards = cards.length > 0;
  const isRunning = status === "running";
  const showProgress = status !== "idle";
  const canStart = hasCards && batchSizeValid && thresholdValid && !isRunning;
  const partialErrors = status === "success" ? (response?.errors ?? 0) : 0;

  let statusText: string;
  if (isRunning) {
    statusText = t("batch.status.running");
  } else if (status === "success") {
    statusText =
      partialErrors > 0
        ? t("batch.status.doneWithErrors")
        : t("batch.status.done");
  } else if (status === "error") {
    statusText = t("batch.status.error");
  } else {
    statusText = t("batch.status.idle");
  }

  const handleStart = (): void => {
    if (!canStart) {
      return;
    }
    void onStart(cards, {
      batchSize,
      thresholdOverride: threshold,
    });
  };

  const handleSizeChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setBatchSizeValue(event.target.value);
  };

  const handleThresholdChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setThresholdValue(event.target.value);
  };

  const barWidth =
    progress.total > 0 ? (progress.processed / progress.total) * 100 : 0;
  const progressLabel = t("batch.progress", {
    processed: progress.processed,
    total: progress.total,
  });

  return (
    <div className="batch">
      <div className="batch__settings">
        <div className="batch__field">
          <label className="batch__label" htmlFor={sizeId}>
            {t("batch.batchSize.label")}
          </label>
          <input
            id={sizeId}
            className="batch__input"
            type="number"
            inputMode="numeric"
            min={MIN_BATCH_SIZE}
            max={MAX_BATCH_SIZE}
            step={1}
            value={batchSizeValue}
            disabled={isRunning}
            aria-invalid={!batchSizeValid}
            aria-describedby={sizeHintId}
            onChange={handleSizeChange}
          />
          <p
            className={`batch__hint${
              batchSizeValid ? "" : " batch__hint--error"
            }`}
            id={sizeHintId}
          >
            {batchSizeValid
              ? t("batch.rangeHint", {
                  min: MIN_BATCH_SIZE,
                  max: MAX_BATCH_SIZE,
                })
              : t("batch.rangeError", {
                  min: MIN_BATCH_SIZE,
                  max: MAX_BATCH_SIZE,
                })}
          </p>
        </div>

        <div className="batch__field">
          <label className="batch__label" htmlFor={thresholdId}>
            {t("batch.threshold.label")}
          </label>
          <input
            id={thresholdId}
            className="batch__input"
            type="number"
            inputMode="decimal"
            min={MIN_CONFIDENCE_THRESHOLD}
            max={MAX_CONFIDENCE_THRESHOLD}
            step={CONFIDENCE_THRESHOLD_STEP}
            value={thresholdValue}
            disabled={isRunning}
            aria-invalid={!thresholdValid}
            aria-describedby={thresholdHintId}
            onChange={handleThresholdChange}
          />
          <p
            className={`batch__hint${
              thresholdValid ? "" : " batch__hint--error"
            }`}
            id={thresholdHintId}
          >
            {thresholdValid
              ? t("batch.rangeHint", {
                  min: MIN_CONFIDENCE_THRESHOLD,
                  max: MAX_CONFIDENCE_THRESHOLD,
                })
              : t("batch.rangeError", {
                  min: MIN_CONFIDENCE_THRESHOLD,
                  max: MAX_CONFIDENCE_THRESHOLD,
                })}
          </p>
        </div>
      </div>

      <div className="batch__actions">
        <button
          type="button"
          className="btn btn--primary"
          disabled={!canStart}
          onClick={handleStart}
        >
          {t("batch.run")}
        </button>
        <button
          type="button"
          className="btn btn--secondary"
          disabled={isRunning || status === "idle"}
          onClick={onReset}
        >
          {t("batch.reset")}
        </button>
      </div>

      {!hasCards ? (
        <p className="batch__hint">{t("batch.errors.noCards")}</p>
      ) : null}

      <div className="batch__state">
        <div className="batch__status-row">
          <span className="batch__status-text" role="status">
            {statusText}
          </span>
          {showProgress ? (
            <span className="batch__progress-count">{progressLabel}</span>
          ) : null}
        </div>

        {showProgress ? (
          <div
            className={`batch__bar${
              isRunning ? " batch__bar--indeterminate" : ""
            }`}
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={progress.total}
            aria-valuenow={isRunning ? undefined : progress.processed}
            aria-label={progressLabel}
          >
            <div
              className="batch__bar-fill"
              style={{ width: `${barWidth}%` }}
            />
          </div>
        ) : null}

        {partialErrors > 0 ? (
          <p className="batch__partial-errors">
            {t("batch.errorsCount", { count: partialErrors })}
          </p>
        ) : null}
      </div>

      {error ? <ErrorBanner error={error} /> : null}
    </div>
  );
}
