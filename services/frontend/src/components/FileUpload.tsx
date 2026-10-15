import { useId } from "react";
import type { ChangeEvent } from "react";
import { useTranslation } from "react-i18next";

import { ACCEPTED_FILE_EXTENSIONS, MAX_UPLOAD_SIZE_BYTES } from "../constants";
import type { FileParseError } from "../lib/fileParser";
import { formatFileSize } from "../lib/format";

/** Статус загрузчика, соответствующий состояниям парсера. */
export type FileUploadStatus = "idle" | "parsing" | "success" | "error";

export type FileUploadProps = {
  status: FileUploadStatus;
  /** Имя выбранного файла (для отображения успеха). */
  fileName?: string;
  /** Число разобранных карточек (для отображения успеха). */
  cardCount?: number;
  /** Типизированная ошибка разбора (для состояния `error`). */
  error?: FileParseError | null;
  /** Блокирует взаимодействие (например, во время батч-обработки). */
  disabled?: boolean;
  onFileSelect: (file: File) => void;
  /** Показывается, когда есть что сбросить. */
  onClear?: () => void;
};

/**
 * Выбор файла карточек обычным системным диалогом по клику
 * (frontend.md, раздел 6.2; design.md, раздел 7).
 *
 * Перетаскивание файлов не поддерживается: у области нет drag-and-drop
 * поведения. Компонент не разбирает файл — он принимает состояние и
 * ошибки снаружи (парсинг в `useFileParser`/`lib/fileParser`).
 */
export default function FileUpload({
  status,
  fileName,
  cardCount,
  error,
  disabled = false,
  onFileSelect,
  onClear,
}: FileUploadProps) {
  const { t } = useTranslation();
  const inputId = useId();

  const isBusy = status === "parsing";
  const isInteractive = !disabled && !isBusy;

  const handleInputChange = (event: ChangeEvent<HTMLInputElement>): void => {
    const file = event.target.files?.[0];
    if (file) {
      onFileSelect(file);
    }
    // Сброс значения позволяет повторно выбрать тот же файл.
    event.target.value = "";
  };

  let statusText: string;
  if (status === "success") {
    statusText = t("fileUpload.success", { name: fileName ?? "" });
  } else if (status === "error") {
    const message = error
      ? t(`fileUpload.errors.${error.code}`)
      : t("fileUpload.errors.invalidStructure");
    statusText = error?.row
      ? `${message} (${t("fileUpload.row", { row: error.row })})`
      : message;
  } else if (status === "parsing") {
    statusText = t("fileUpload.parsing");
  } else {
    statusText = t("fileUpload.idle");
  }

  const showClear =
    onClear !== undefined && (status === "success" || status === "error");

  return (
    <div className={`file-upload file-upload--${status}`} aria-busy={isBusy}>
      <label className="file-upload__zone" htmlFor={inputId}>
        <input
          id={inputId}
          className="file-upload__input"
          type="file"
          accept={ACCEPTED_FILE_EXTENSIONS.join(",")}
          aria-label={t("fileUpload.inputLabel")}
          disabled={!isInteractive}
          onChange={handleInputChange}
        />
        <span className="file-upload__status" role="status">
          <span className="file-upload__title">{statusText}</span>
          {status === "success" && cardCount !== undefined ? (
            <span className="file-upload__count">
              {t("fileUpload.cardCount", { total: cardCount })}
            </span>
          ) : null}
        </span>
        <span className="file-upload__hint">
          {t("fileUpload.hint", {
            size: formatFileSize(MAX_UPLOAD_SIZE_BYTES),
          })}
        </span>
      </label>

      {showClear ? (
        <button
          type="button"
          className="btn btn--secondary file-upload__clear"
          onClick={onClear}
        >
          {t("fileUpload.clear")}
        </button>
      ) : null}
    </div>
  );
}
