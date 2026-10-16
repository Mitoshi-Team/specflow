import { useCallback } from "react";

import { CSV_MIME_TYPE, PREDICTIONS_CSV_FILENAME } from "../constants";
import { serializePredictionsCsv } from "../lib/csvExport";
import type {
  ExtractionResponseItem,
  ProductCardRequest,
} from "../schemas/api";

export type UseCsvExportOptions = {
  /**
   * Исходные карточки батча. Нужны для колонки `title` формата PredictionRow:
   * ответ API её не содержит (domain-model.md, 3.7).
   */
  cards?: ProductCardRequest[];
  /** Имя скачиваемого файла; по умолчанию `predictions.csv`. */
  filename?: string;
};

export type UseCsvExportResult = {
  /** Кнопка экспорта недоступна без результатов (design.md, §7). */
  disabled: boolean;
  /** Формирует CSV формата PredictionRow и инициирует скачивание файла. */
  exportCsv: () => void;
};

/**
 * Создаёт временную ссылку на Blob и инициирует скачивание файла целиком на
 * клиенте — без обращений к API (frontend.md, 5.4).
 */
function downloadCsv(content: string, filename: string): void {
  const blob = new Blob([content], { type: CSV_MIME_TYPE });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

/**
 * Экспорт результатов батча в CSV формата PredictionRow
 * (frontend.md, 5.4 и 7; design.md, §7).
 *
 * Логика сериализации вынесена в `lib/csvExport` и не зависит от UI; хук
 * добавляет только скачивание файла в браузере. При отсутствии результатов
 * `disabled` истинно, а `exportCsv` ничего не делает.
 */
export function useCsvExport(
  results: ExtractionResponseItem[],
  options: UseCsvExportOptions = {},
): UseCsvExportResult {
  const { cards = [], filename = PREDICTIONS_CSV_FILENAME } = options;
  const disabled = results.length === 0;

  const exportCsv = useCallback((): void => {
    if (results.length === 0) {
      return;
    }
    downloadCsv(serializePredictionsCsv(results, cards), filename);
  }, [results, cards, filename]);

  return { disabled, exportCsv };
}
