import { useId, useState } from "react";
import { useTranslation } from "react-i18next";

import BatchControls from "../components/BatchControls";
import DataPreview from "../components/DataPreview";
import FileUpload from "../components/FileUpload";
import { useBatchExtract } from "../hooks/useBatchExtract";
import { useFileParser } from "../hooks/useFileParser";
import { formatFileSize } from "../lib/format";

/**
 * Главная страница: выбор файла карточек, предпросмотр разобранных строк и
 * запуск батча (frontend.md, сценарии 1–2; design.md, раздел 6, области
 * «Загрузка» и «Обработка»).
 *
 * Успешный выбор файла сам по себе ничего не запускает — запуск батча
 * отдельное явное действие (design.md, раздел 7).
 */
export default function PageHome() {
  const { t } = useTranslation();
  const sectionIds = useId();
  const [file, setFile] = useState<File | null>(null);
  const parser = useFileParser(file);
  const batch = useBatchExtract();

  const uploadTitleId = `${sectionIds}-upload`;
  const previewTitleId = `${sectionIds}-preview`;
  const batchTitleId = `${sectionIds}-batch`;
  const showPreview = parser.status === "success" && parser.cards.length > 0;
  const cardCountText = t("fileUpload.cardCount", {
    total: parser.cards.length,
  });

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
        </div>

        <FileUpload
          status={parser.status}
          fileName={file?.name}
          cardCount={parser.cards.length}
          error={parser.error}
          onFileSelect={setFile}
          onClear={() => setFile(null)}
        />
      </section>

      {showPreview && file ? (
        <section className="panel" aria-labelledby={previewTitleId}>
          <div className="panel__header">
            <h2 className="panel__title" id={previewTitleId}>
              {t("preview.title")}
            </h2>
            <p className="panel__meta">
              <span>{file.name}</span>
              <span aria-hidden="true">·</span>
              <span>{parser.format?.toUpperCase()}</span>
              <span aria-hidden="true">·</span>
              <span>{formatFileSize(file.size)}</span>
              <span aria-hidden="true">·</span>
              <span>{cardCountText}</span>
            </p>
          </div>

          <DataPreview cards={parser.cards} />
        </section>
      ) : null}

      <section className="panel" aria-labelledby={batchTitleId}>
        <div className="panel__header">
          <h2 className="panel__title" id={batchTitleId}>
            {t("batch.title")}
          </h2>
        </div>

        <BatchControls
          cards={parser.cards}
          status={batch.status}
          progress={batch.progress}
          error={batch.error}
          response={batch.response}
          onStart={batch.run}
          onReset={batch.reset}
        />
      </section>
    </section>
  );
}
