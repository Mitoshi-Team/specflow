import { useCallback, useEffect, useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import BatchControls from "../components/BatchControls";
import CardTextInput from "../components/CardTextInput";
import DataPreview from "../components/DataPreview";
import FileUpload from "../components/FileUpload";
import InputModeSwitch from "../components/InputModeSwitch";
import type { InputMode } from "../components/InputModeSwitch";
import { useBatchExtract } from "../hooks/useBatchExtract";
import type { BatchSettings } from "../hooks/useBatchExtract";
import { useFileParser } from "../hooks/useFileParser";
import { formatFileSize } from "../lib/format";
import { clearLastBatch, writeLastBatch } from "../lib/lastBatch";
import type { ProductCardRequest } from "../schemas/api";

/** Параметры последнего запущенного батча: нужны, чтобы передать на страницу результатов. */
type SubmittedBatch = {
  settings: BatchSettings;
  cards: ProductCardRequest[];
};

/**
 * Главная страница: выбор способа загрузки карточек (файл либо текстовое
 * описание одной карточки), предпросмотр разобранных строк и запуск батча
 * (frontend.md, сценарии 1–2; design.md, раздел 6, области «Загрузка» и
 * «Обработка»).
 *
 * Успешный ввод сам по себе ничего не запускает — запуск батча отдельное
 * явное действие (design.md, раздел 7). При успехе выполняется переход к
 * результатам (frontend.md, сценарий 2, шаг 4).
 */
export default function PageHome() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const sectionIds = useId();
  const [mode, setMode] = useState<InputMode>("file");
  const [file, setFile] = useState<File | null>(null);
  const [description, setDescription] = useState("");
  const [submitted, setSubmitted] = useState<SubmittedBatch | null>(null);
  const parser = useFileParser(file);
  const batch = useBatchExtract();

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
  const batchTitleId = `${sectionIds}-batch`;

  // Кнопка «Новый батч» доступна, когда есть что сбрасывать: выбранный файл,
  // введённый текст карточки или запущенный батч (frontend.md, раздел 8.2).
  const canStartNewBatch =
    file !== null || description.trim() !== "" || batch.status !== "idle";

  const handleNewBatch = (): void => {
    // Сброс текущих данных и состояния батча; во время выполнения кнопка
    // заблокирована, поэтому поздний ответ не перезаписывает сброс.
    batch.reset();
    setSubmitted(null);
    setFile(null);
    setDescription("");
    setMode("file");
    // Заодно убираем сохранённый батч: «Новый батч» начинает всё заново,
    // а страница результатов не должна показывать старые данные
    // (frontend.md, §8.2).
    clearLastBatch();
    navigate("/");
  };

  // Запоминаем отправленные карточки и настройки: ответ батча несёт только
  // результат, а странице результатов нужен ещё и порог уверенности, чтобы
  // пояснить низкоуверенные значения (frontend.md, сценарий 3).
  const handleStart = useCallback(
    (items: ProductCardRequest[], settings: BatchSettings): Promise<void> => {
      setSubmitted({ settings, cards: items });
      return batch.run(items, settings);
    },
    [batch.run],
  );

  // Переход к результатам при успехе (frontend.md, сценарий 2, шаг 4).
  // Ответ сохраняем в localStorage, а не передаём через `location.state`:
  // состояние маршрута теряется при повторном переходе на «Результаты» из
  // навигации и при перезагрузке страницы.
  useEffect(() => {
    if (
      batch.status !== "success" ||
      batch.response === null ||
      submitted === null
    ) {
      return;
    }
    writeLastBatch({
      response: batch.response,
      threshold: submitted.settings.thresholdOverride,
      cards: submitted.cards,
    });
    navigate("/results");
  }, [batch.status, batch.response, submitted, navigate]);

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

      <section className="panel" aria-labelledby={batchTitleId}>
        <div className="panel__header">
          <h2 className="panel__title" id={batchTitleId}>
            {t("batch.title")}
          </h2>
          {canStartNewBatch ? (
            <div className="panel__actions">
              <button
                type="button"
                className="btn btn--secondary"
                disabled={batch.status === "running"}
                onClick={handleNewBatch}
              >
                {t("batch.newBatch")}
              </button>
            </div>
          ) : null}
        </div>

        <BatchControls
          cards={cards}
          status={batch.status}
          progress={batch.progress}
          error={batch.error}
          response={batch.response}
          onStart={handleStart}
          onReset={batch.reset}
        />
      </section>
    </section>
  );
}
