import { useCallback, useEffect, useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import BatchControls from "../components/BatchControls";
import CardTextInput from "../components/CardTextInput";
import DataPreview from "../components/DataPreview";
import FieldNamesHint from "../components/FieldNamesHint";
import FileUpload from "../components/FileUpload";
import InputModeSwitch from "../components/InputModeSwitch";
import type { InputMode } from "../components/InputModeSwitch";
import { useBatchExtract } from "../hooks/useBatchExtract";
import type { BatchSettings } from "../hooks/useBatchExtract";
import { useFileParser } from "../hooks/useFileParser";
import { formatFileSize } from "../lib/format";
import { clearLastBatch, writeLastBatch } from "../lib/lastBatch";
import type { StoredBatch } from "../lib/lastBatch";
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

  // «Сброс» в панели батча возвращает страницу к исходному вводу: очищает
  // выбранный файл (или текст одиночной карточки) и состояние батча, не
  // покидая страницу. Порог уверенности компонент сбрасывает сам
  // (`BatchControls`).
  const handleReset = (): void => {
    batch.reset();
    setSubmitted(null);
    setFile(null);
    setDescription("");
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
  // Батч сохранён сервером (api_contract.md, 4.8/4.9) — переходим по
  // `?batch_id=`, откуда страница результатов подгружает его из истории.
  // Локальная копия остаётся фолбэком (dev-режим без БД, persisted=false).
  // Если localStorage недоступен И сервер не сохранил батч, передаём его
  // через state как последний шанс показать результаты этой сессии — ошибка
  // записи не подавляется молча, а ведёт к последствию (замечание ревью).
  useEffect(() => {
    if (
      batch.status !== "success" ||
      batch.response === null ||
      submitted === null
    ) {
      return;
    }
    const storedBatch: StoredBatch = {
      response: batch.response,
      threshold: submitted.settings.thresholdOverride,
      cards: submitted.cards,
    };
    const storedLocally = writeLastBatch(storedBatch);
    const batchId = batch.response.batch_id;
    const serverSaved = batch.response.persisted !== false && batchId != null;
    if (serverSaved && batchId != null) {
      navigate(`/results?batch_id=${encodeURIComponent(batchId)}`);
    } else if (storedLocally) {
      navigate("/results");
    } else {
      navigate("/results", { state: { batch: storedBatch } });
    }
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
            {isFileMode ? <FieldNamesHint /> : null}
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
          onResetAll={handleReset}
        />
      </section>

      {/* Пока батч обрабатывается — оверлей поверх всей страницы: крупный
          спиннер строго по центру (без видимой подписи; состояние для
          скринридера объявляет role="status" + aria-label) и замыливание
          фона. Оверлей перехватывает клики, поэтому ввод на время
          обработки заблокирован (design.md, «Прогресс и состояние батча»). */}
      {batch.status === "running" ? (
        <div className="loading-overlay">
          <div
            className="loading-overlay__spinner"
            role="status"
            aria-label={t("loader.label")}
          />
        </div>
      ) : null}
    </section>
  );
}
