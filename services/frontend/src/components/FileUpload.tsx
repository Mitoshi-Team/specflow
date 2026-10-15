import { useId, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";
import { useTranslation } from "react-i18next";

import { ACCEPTED_FILE_EXTENSIONS } from "../constants";
import type { FileParseError } from "../lib/fileParser";

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
 * Выбор файла карточек: drag&Drop и file input для CSV/JSON/TSV
 * (frontend.md, раздел 6.2). Компонент не разбирает файл — он принимает
 * состояние и ошибки снаружи (парсинг в `useFileParser`/`lib/fileParser`).
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
  const [isDragging, setIsDragging] = useState(false);

  const isBusy = status === "parsing";
  const isInteractive = !disabled && !isBusy;

  const selectFile = (files: FileList | null): void => {
    const file = files?.[0];
    if (file) {
      onFileSelect(file);
    }
  };

  const handleInputChange = (event: ChangeEvent<HTMLInputElement>): void => {
    selectFile(event.target.files);
    // Сброс значения позволяет повторно выбрать тот же файл.
    event.target.value = "";
  };

  const handleDragOver = (event: DragEvent<HTMLLabelElement>): void => {
    event.preventDefault();
    if (isInteractive) {
      setIsDragging(true);
    }
  };

  const handleDragLeave = (event: DragEvent<HTMLLabelElement>): void => {
    if (event.currentTarget.contains(event.relatedTarget as Node | null)) {
      return;
    }
    setIsDragging(false);
  };

  const handleDrop = (event: DragEvent<HTMLLabelElement>): void => {
    event.preventDefault();
    setIsDragging(false);
    if (!isInteractive) {
      return;
    }
    selectFile(event.dataTransfer.files);
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
    statusText = isDragging ? t("fileUpload.dragging") : t("fileUpload.idle");
  }

  const showClear =
    onClear !== undefined && (status === "success" || status === "error");

  return (
    <div
      className={`file-upload file-upload--${status}${
        isDragging ? " file-upload--dragging" : ""
      }`}
      aria-busy={isBusy}
    >
      <label
        className="file-upload__dropzone"
        htmlFor={inputId}
        onDragEnter={handleDragOver}
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
        <span className="file-upload__status" role="status">
          <span className="file-upload__title">{statusText}</span>
          {status === "success" && cardCount !== undefined ? (
            <span className="file-upload__count">
              {t("fileUpload.cardCount", { total: cardCount })}
            </span>
          ) : null}
        </span>
        <span className="file-upload__hint">{t("fileUpload.hint")}</span>
      </label>

      {showClear ? (
        <button
          type="button"
          className="file-upload__clear"
          onClick={onClear}
        >
          {t("fileUpload.clear")}
        </button>
      ) : null}
    </div>
  );
}
