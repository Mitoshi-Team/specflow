import { useTranslation } from "react-i18next";

import { useCsvExport } from "../hooks/useCsvExport";
import type {
  ExtractionResponseItem,
  ProductCardRequest,
} from "../schemas/api";

export type ExportCsvButtonProps = {
  /** Результаты батча для экспорта (api_contract.md, 3.5). */
  results: ExtractionResponseItem[];
  /**
   * Исходные карточки батча — источник колонки `title`
   * (domain-model.md, 3.7), которой нет в ответе API.
   */
  cards?: ProductCardRequest[];
};

/**
 * Кнопка «Скачать CSV» (frontend.md, 6.2 `ExportCsvButton`, сценарий 4;
 * design.md, §7). Формирует и скачивает файл в формате PredictionRow на
 * клиенте; доступна только при наличии результатов.
 *
 * Текст кнопки обозначает формат явно (design.md, §7), а состояние
 * `disabled` берётся из `useCsvExport`.
 */
export default function ExportCsvButton({
  results,
  cards,
}: ExportCsvButtonProps) {
  const { t } = useTranslation();
  const { disabled, exportCsv } = useCsvExport(results, { cards });

  return (
    <button
      type="button"
      className="btn btn--secondary"
      disabled={disabled}
      aria-label={t("results.export.ariaLabel")}
      onClick={exportCsv}
    >
      {t("results.export.label")}
    </button>
  );
}
