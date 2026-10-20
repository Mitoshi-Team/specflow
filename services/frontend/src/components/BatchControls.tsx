import { useId, useState } from "react";
import type { ChangeEvent } from "react";
import { useTranslation } from "react-i18next";

import type { ApiError } from "../api";
import {
  CONFIDENCE_THRESHOLD_STEP,
  DEFAULT_CONFIDENCE_THRESHOLD,
  MAX_CONFIDENCE_THRESHOLD,
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
  /**
   * Сброс внешних данных страницы: загруженного файла либо текста одиночной
   * карточки. Сам порог уверенности компонент сбрасывает сам, поэтому
   * снаружи он не передаётся.
   */
  onResetAll: () => void;
};

/**
 * Пустое поле — это не ноль: `Number("")` даёт 0, и невведённый порог
 * выглядел бы валидным (0 входит в диапазон [0; 1]), а батч уходил бы на
 * сервер с нулевым порогом. Браузер сам отдаёт пустую строку и для ввода,
 * который не является числом (например, «1,5» или «abc» в `input[type=number]`).
 */
function isBlank(value: string): boolean {
  return value.trim() === "";
}

/**
 * Настройки порога уверенности, кнопки «Обработать»/«Сброс», прогресс
 * «Обработано X из Y» и ошибки API (frontend.md, раздел 6.2; design.md,
 * раздел 7).
 *
 * Размер батча не настраивается: он определяется числом загруженных
 * карточек (см. `useBatchExtract`). «Сброс» возвращает панель к исходному
 * состоянию: порог — к значению по умолчанию, а загруженный файл или текст
 * одиночной карточки очищает страница через `onResetAll` (компонент не
 * владеет этими данными). Запуск, прогресс и ошибки приходят снаружи через
 * `useBatchExtract` (логика отделена от UI).
 */
export default function BatchControls({
  cards,
  status,
  progress,
  error,
  response,
  onStart,
  onResetAll,
}: BatchControlsProps) {
  const { t } = useTranslation();
  const thresholdId = useId();
  const thresholdHintId = `${thresholdId}-hint`;
  const defaultThresholdValue = String(DEFAULT_CONFIDENCE_THRESHOLD);

  const [thresholdValue, setThresholdValue] = useState(defaultThresholdValue);

  const threshold = Number(thresholdValue);
  const thresholdValid =
    !isBlank(thresholdValue) &&
    Number.isFinite(threshold) &&
    threshold >= MIN_CONFIDENCE_THRESHOLD &&
    threshold <= MAX_CONFIDENCE_THRESHOLD;

  const hasCards = cards.length > 0;
  const isRunning = status === "running";
  const showProgress = status !== "idle";
  const canStart = hasCards && thresholdValid && !isRunning;
  const partialErrors = status === "success" ? (response?.errors ?? 0) : 0;

  const handleStart = (): void => {
    if (!canStart) {
      return;
    }
    void onStart(cards, { thresholdOverride: threshold });
  };

  const handleThresholdChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setThresholdValue(event.target.value);
  };

  const handleReset = (): void => {
    setThresholdValue(defaultThresholdValue);
    onResetAll();
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
          disabled={isRunning || (!hasCards && thresholdValue === defaultThresholdValue)}
          onClick={handleReset}
        >
          {t("batch.reset")}
        </button>
      </div>

      {!hasCards ? (
        <p className="batch__hint">{t("batch.errors.noCards")}</p>
      ) : null}

      <div className="batch__state">
        {/* Статусная строка убрана: во время обработки состояние показывает
            оверлей загрузки на уровне страницы (PageHome, design.md,
            «Прогресс и состояние батча»). Здесь остаётся только прогресс. */}
        {showProgress ? (
          <span className="batch__progress-count">{progressLabel}</span>
        ) : null}

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
