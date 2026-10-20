import { useCallback, useRef, useState } from "react";

import { ApiError, extractBatch } from "../api";
import {
  MAX_BATCH_SIZE,
  MAX_CONFIDENCE_THRESHOLD,
  MIN_CONFIDENCE_THRESHOLD,
} from "../constants";
import type {
  BatchExtractRequest,
  BatchExtractResponse,
  ProductCardRequest,
} from "../schemas/api";

/** Состояние запуска батча (frontend.md, разделы 7–8; design.md, раздел 7). */
export type BatchStatus = "idle" | "running" | "success" | "error";

/** Настройки запуска батча. */
export type BatchSettings = {
  /** Переопределение порога уверенности — поле `threshold_override`. */
  thresholdOverride: number;
};

/**
 * Прогресс «обработано X из Y» (frontend.md, раздел 8.2).
 *
 * API не сообщает прогресса внутри запроса (api_contract.md), поэтому во время
 * выполнения `processed` равен 0, а числом фактически обработанных карточек
 * становится `total` ответа после успешного завершения (design.md, раздел 7:
 * нельзя имитировать процент, которого нет).
 */
export type BatchProgress = {
  processed: number;
  total: number;
};

export type UseBatchExtractResult = {
  status: BatchStatus;
  progress: BatchProgress;
  /** Ошибка запроса в формате контракта ErrorResponse (ApiError). */
  error: ApiError | null;
  /** Успешный ответ батча; содержит сводку включая число частичных ошибок. */
  response: BatchExtractResponse | null;
  /** Отправляет батч. Повторный вызов во время выполнения игнорируется. */
  run: (items: ProductCardRequest[], settings: BatchSettings) => Promise<void>;
  /** Сбрасывает состояние после завершения; во время выполнения игнорируется. */
  reset: () => void;
};

const IDLE_PROGRESS: BatchProgress = { processed: 0, total: 0 };

/**
 * Запуск батч-извлечения через POST /extract/batch с состоянием
 * loading/error/progress (frontend.md, раздел 7).
 *
 * Логика не зависит от UI: компонент передаёт карточки и настройки и рисует
 * возвращаемое состояние. Валидация содержимого карточек (правило
 * api_contract.md, 3.1) выполняется при разборе файла (`lib/fileParser`),
 * здесь она не дублируется — хук защищается только от пустого набора и
 * нарушения диапазонов контракта.
 */
export function useBatchExtract(): UseBatchExtractResult {
  const [status, setStatus] = useState<BatchStatus>("idle");
  const [progress, setProgress] = useState<BatchProgress>(IDLE_PROGRESS);
  const [error, setError] = useState<ApiError | null>(null);
  const [response, setResponse] = useState<BatchExtractResponse | null>(null);

  // Синхронная защита от повторного запуска: setState асинхронен, и только
  // по состоянию гонка двух быстрых кликов не отлавливается.
  const runningRef = useRef(false);

  const run = useCallback(
    async (
      items: ProductCardRequest[],
      settings: BatchSettings,
    ): Promise<void> => {
      if (runningRef.current) {
        return;
      }
      if (items.length === 0) {
        return;
      }
      if (
        !Number.isFinite(settings.thresholdOverride) ||
        settings.thresholdOverride < MIN_CONFIDENCE_THRESHOLD ||
        settings.thresholdOverride > MAX_CONFIDENCE_THRESHOLD
      ) {
        return;
      }
      if (items.length > MAX_BATCH_SIZE) {
        return;
      }

      runningRef.current = true;
      setStatus("running");
      setProgress({ processed: 0, total: items.length });
      setError(null);
      setResponse(null);

      // Размер батча определяется числом загруженных карточек: все карточки
      // уходят одним запросом (контракт ограничивает батч MAX_BATCH_SIZE).
      const payload: BatchExtractRequest = {
        items,
        batch_size: items.length,
        threshold_override: settings.thresholdOverride,
      };

      try {
        const result = await extractBatch(payload);
        setResponse(result);
        setProgress({ processed: result.total, total: items.length });
        setStatus("success");
      } catch (cause) {
        // request() бросает только ApiError (api/client.ts); прочие исключения —
        // ошибки программирования: возвращаем состояние и пробрасываем дальше.
        if (!(cause instanceof ApiError)) {
          setStatus("idle");
          setProgress(IDLE_PROGRESS);
          throw cause;
        }
        setError(cause);
        setStatus("error");
      } finally {
        runningRef.current = false;
      }
    },
    [],
  );

  const reset = useCallback((): void => {
    // Сброс во время выполнения игнорируется: поздний ответ иначе перезаписал
    // бы сброшенное состояние. UI дополнительно блокирует кнопку «Сброс».
    if (runningRef.current) {
      return;
    }
    setStatus("idle");
    setProgress(IDLE_PROGRESS);
    setError(null);
    setResponse(null);
  }, []);

  return { status, progress, error, response, run, reset };
}
