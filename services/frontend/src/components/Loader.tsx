import { useTranslation } from "react-i18next";

/** Числовой прогресс «обработано/всего» для определённого индикатора. */
export type LoaderProgress = {
  processed: number;
  total: number;
};

export type LoaderProps = {
  /**
   * Локализованная подпись состояния. Если не передана, используется
   * общий ключ `loader.label`.
   */
  label?: string;
  /**
   * Если задан, дополнительно показывается определённый прогресс
   * «Обработано X из Y» с полосой (frontend.md, раздел 6.2: «Спиннер + прогресс»).
   */
  progress?: LoaderProgress;
  /** Компактный вариант для встраивания в строку (например, в загрузчике файла). */
  inline?: boolean;
};

/**
 * Индикатор загрузки: спиннер и, при наличии данных, определённый прогресс
 * (frontend.md, раздел 6.2 `Loader`; design.md, разделы 7, 11, 12).
 *
 * Точный процент не имитируется: полоса показывается только когда вызывающий
 * код передал фактический `progress` (design.md, раздел 7). Регион `status`
 * делает состояние доступным скринридеру (design.md, раздел 11).
 */
export default function Loader({ label, progress, inline }: LoaderProps) {
  const { t } = useTranslation();

  const text = label ?? t("loader.label");
  const progressLabel = progress
    ? t("loader.progress", {
        processed: progress.processed,
        total: progress.total,
      })
    : undefined;
  const barWidth =
    progress && progress.total > 0
      ? (progress.processed / progress.total) * 100
      : 0;

  return (
    <div className={`loader${inline ? " loader--inline" : ""}`} role="status">
      <span className="loader__spinner" aria-hidden="true" />
      <span className="loader__label">{text}</span>
      {progress ? (
        <div
          className="loader__bar"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={progress.total}
          aria-valuenow={progress.processed}
          aria-label={progressLabel}
        >
          <div
            className="loader__bar-fill"
            style={{ width: `${barWidth}%` }}
          />
        </div>
      ) : null}
    </div>
  );
}
