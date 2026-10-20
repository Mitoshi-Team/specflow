import { useId, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";
import { useTranslation } from "react-i18next";

import { ACCEPTED_FILE_EXTENSIONS, MAX_UPLOAD_SIZE_BYTES } from "../constants";
import type { FileParseError } from "../lib/fileParser";
import { formatFileSize } from "../lib/format";
import Loader from "./Loader";

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
 * Выбор файла карточек обычным системным диалогом по клику либо
 * перетаскиванием файла в область загрузки (frontend.md, раздел 6.2;
 * design.md, раздел 7).
 *
 * Компонент не разбирает файл — он принимает состояние и ошибки снаружи
 * (парсинг в `useFileParser`/`lib/fileParser`).
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
  const [isDragOver, setIsDragOver] = useState(false);

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

  // Браузер по умолчанию открывает перетаскиваемый файл в новой вкладке,
  // поэтому dragover/drop должны предотвращаться. Файл принимается, только
  // когда область активна: во время обработки и при заблокированном
  // состоянии drop игнорируется.
  const handleDragOver = (event: DragEvent<HTMLLabelElement>): void => {
    event.preventDefault();
    if (isInteractive) {
      setIsDragOver(true);
    }
  };

  const handleDragLeave = (event: DragEvent<HTMLLabelElement>): void => {
    event.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (event: DragEvent<HTMLLabelElement>): void => {
    event.preventDefault();
    setIsDragOver(false);
    if (!isInteractive) {
      return;
    }
    const file = event.dataTransfer.files?.[0];
    if (file) {
      onFileSelect(file);
    }
  };

  let statusText: string;
  // Подсказка «что делать» для ошибки разбора; в остальных состояниях нет.
  let errorHint: string | null = null;
  if (status === "success") {
    statusText = t("fileUpload.success", { name: fileName ?? "" });
  } else if (status === "error") {
    // Код ошибки определяет и сообщение, и безопасное следующее действие —
    // пользователь видит не только «что не так», но и «что исправить»
    // (design.md, §7: ошибка объясняет происходящее и предлагает действие).
    const code = error?.code ?? "invalidStructure";
    const message = t(`fileUpload.errors.${code}`);
    statusText = error?.row
      ? `${message} (${t("fileUpload.row", { row: error.row })})`
      : message;
    errorHint = t(`fileUpload.hints.${code}`);
  } else if (status === "parsing") {
    statusText = t("fileUpload.parsing");
  } else {
    statusText = t("fileUpload.idle");
  }

  const showClear =
    onClear !== undefined && (status === "success" || status === "error");

  return (
    <div className={`file-upload file-upload--${status}`} aria-busy={isBusy}>
      <label
        className={`file-upload__zone${isDragOver ? " file-upload__zone--dragover" : ""}`}
        htmlFor={inputId}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <input
          id={inputId}
          className="file-upload__input"
          type="file"
          accept={ACCEPTED_FILE_EXTENSIONS.join(",")}
          aria-label={t("fileUpload.inputLabel")}
          disabled={!isInteractive}
          onChange={handleInputChange}
        />
        {isBusy ? (
          <Loader label={statusText} inline />
        ) : (
          <span className="file-upload__status" role="status">
            <span className="file-upload__title">{statusText}</span>
            {status === "success" && cardCount !== undefined ? (
              <span className="file-upload__count">
                {t("fileUpload.cardCount", { total: cardCount })}
              </span>
            ) : null}
            {errorHint ? (
              <span className="file-upload__error-hint">{errorHint}</span>
            ) : null}
          </span>
        )}
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
