import { useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import CardTextInput from "../components/CardTextInput";
import DataPreview from "../components/DataPreview";
import FileUpload from "../components/FileUpload";
import InputModeSwitch from "../components/InputModeSwitch";
import type { InputMode } from "../components/InputModeSwitch";
import { useFileParser } from "../hooks/useFileParser";
import { formatFileSize } from "../lib/format";

/**
 * Главная страница: выбор способа загрузки (файл карточек либо текстовое
 * описание одной карточки) и предпросмотр разобранных строк (frontend.md,
 * сценарий 1; design.md, раздел 6, область «Загрузка»).
 *
 * Успешный ввод сам по себе ничего не запускает — запуск батча будет
 * отдельным явным действием (design.md, раздел 7).
 */
export default function PageHome() {
  const { t } = useTranslation();
  const sectionIds = useId();
  const [mode, setMode] = useState<InputMode>("file");
  const [file, setFile] = useState<File | null>(null);
  const [description, setDescription] = useState("");
  const parser = useFileParser(file);

  // Текстовый режим: обрезанный текст — готовая карточка с полем
  // description, пустой текст — карточек нет и предпросмотр не показывается.
  const textCards = useMemo(
    () =>
      description.trim() === "" ? [] : [{ description: description.trim() }],
    [description],
  );

  const isFileMode = mode === "file";
  const cards = isFileMode ? parser.cards : textCards;
  const showPreview = cards.length > 0;
  const cardCountText = t("fileUpload.cardCount", {
    total: cards.length,
  });

  const uploadTitleId = `${sectionIds}-upload`;
  const previewTitleId = `${sectionIds}-preview`;

  return (
    <section className="page">
      <div>
        <h1>{t("pages.home.title")}</h1>
        <p className="page__description">{t("pages.home.description")}</p>
      </div>

      <section className="panel" aria-labelledby={uploadTitleId}>
        <div className="panel__header">
          <h2 className="panel__title" id={uploadTitleId}>
            {t("upload.title")}
          </h2>
          <InputModeSwitch value={mode} onChange={setMode} />
        </div>

        {isFileMode ? (
          <FileUpload
            status={parser.status}
            fileName={file?.name}
            cardCount={parser.cards.length}
            error={parser.error}
            onFileSelect={setFile}
            onClear={() => setFile(null)}
          />
        ) : (
          <CardTextInput
            value={description}
            onChange={setDescription}
            onClear={() => setDescription("")}
          />
        )}
      </section>

      {showPreview ? (
        <section className="panel" aria-labelledby={previewTitleId}>
          <div className="panel__header">
            <h2 className="panel__title" id={previewTitleId}>
              {t("preview.title")}
            </h2>
            <p className="panel__meta">
              {isFileMode && file ? (
                <>
                  <span>{file.name}</span>
                  <span aria-hidden="true">·</span>
                  <span>{parser.format?.toUpperCase()}</span>
                  <span aria-hidden="true">·</span>
                  <span>{formatFileSize(file.size)}</span>
                  <span aria-hidden="true">·</span>
                </>
              ) : (
                <>
                  <span>{t("upload.mode.text")}</span>
                  <span aria-hidden="true">·</span>
                </>
              )}
              <span>{cardCountText}</span>
            </p>
          </div>

          <DataPreview cards={cards} />
        </section>
      ) : null}
    </section>
  );
}
