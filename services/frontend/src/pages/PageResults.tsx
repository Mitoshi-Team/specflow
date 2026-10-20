import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useSearchParams } from "react-router-dom";

import { ApiError, getBatch, listBatches } from "../api";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import ExportCsvButton from "../components/ExportCsvButton";
import Loader from "../components/Loader";
import ResultsSummary from "../components/ResultsSummary";
import ResultsTable from "../components/ResultsTable";
import StatusLegend from "../components/StatusLegend";
import { BATCH_HISTORY_LIMIT } from "../constants";
import { formatDateTime } from "../lib/format";
import { readLastBatch } from "../lib/lastBatch";
import type { StoredBatch } from "../lib/lastBatch";
import type { BatchSummary } from "../schemas/api";

/** Состояние загрузки батча с сервера по `?batch_id=`. */
type RemoteBatchState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; batch: StoredBatch }
  | { status: "error"; error: ApiError };

/** Состояние загрузки списка истории батчей. */
type HistoryState =
  | { status: "loading" }
  | { status: "ready"; items: BatchSummary[]; total: number }
  | { status: "error"; error: ApiError };

/** Локальная копия батча и откуда она взялась. */
type LocalBatch = {
  batch: StoredBatch | null;
  /** true — батч пришёл через state маршрута (localStorage недоступен). */
  fromState: boolean;
};

/**
 * Проверяет форму батча, пришедшего через state маршрута (`{batch: StoredBatch}`
 * от PageHome) — state не доверяем, он приходит извне маршрута.
 */
function toStoredBatch(value: unknown): StoredBatch | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const batch = (value as { batch?: unknown }).batch;
  if (typeof batch !== "object" || batch === null) {
    return null;
  }
  const response = (batch as { response?: unknown }).response;
  return typeof response === "object" && response !== null ? (batch as StoredBatch) : null;
}

/**
 * Страница результатов пакетной обработки (frontend.md, сценарий 3;
 * design.md, §7). Показывает сводку батча, легенду статусов и таблицу
 * результатов с экспортом CSV, а также панель «Предыдущие батчи» из
 * серверной истории (api_contract.md, 4.8/4.9).
 *
 * Источник данных: `?batch_id=` → батч с сервера (история переживает
 * перезагрузку); без параметра — локальная копия (`lib/lastBatch`) как
 * фолбэк. Сбои загрузки видимы (ErrorBanner), а не подавлены; если сервер
 * не сохранил батч (`persisted=false`), показывается предупреждение о риске
 * потери (замечание ревью).
 */
export default function PageResults() {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const batchId = searchParams.get("batch_id");

  // Локальная копия читается один раз при монтировании: повторные переходы на
  // этот же маршрут не должны сбрасывать уже показанные результаты.
  const [local] = useState<LocalBatch>(() => {
    const stored = readLastBatch();
    if (stored !== null) {
      return { batch: stored, fromState: false };
    }
    const viaState = toStoredBatch(location.state);
    return { batch: viaState, fromState: viaState !== null };
  });

  const [remote, setRemote] = useState<RemoteBatchState>({ status: "idle" });

  useEffect(() => {
    if (batchId === null) {
      setRemote({ status: "idle" });
      return;
    }
    const controller = new AbortController();
    setRemote({ status: "loading" });
    void getBatch(batchId, controller.signal).then(
      (stored) => {
        setRemote({
          status: "ready",
          batch: {
            response: stored.response,
            threshold: stored.threshold ?? undefined,
            cards: stored.cards ?? [],
          },
        });
      },
      (error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        if (!(error instanceof ApiError)) {
          // request() бросает только ApiError — прочее ошибка программирования.
          throw error;
        }
        setRemote({ status: "error", error });
      },
    );
    return () => controller.abort();
  }, [batchId]);

  const [history, setHistory] = useState<HistoryState>({ status: "loading" });
  const [historyReload, setHistoryReload] = useState(0);
  // Догрузка следующей страницы истории: отдельные состояния, чтобы не
  // сбрасывать уже показанные батчи и показывать сбой кнопки видимо.
  const [historyLoadingMore, setHistoryLoadingMore] = useState(false);
  const [historyMoreError, setHistoryMoreError] = useState<ApiError | null>(null);
  const historyMoreController = useRef<AbortController | null>(null);

  useEffect(() => () => historyMoreController.current?.abort(), []);

  useEffect(() => {
    const controller = new AbortController();
    setHistory({ status: "loading" });
    void listBatches({ limit: BATCH_HISTORY_LIMIT }, controller.signal).then(
      (list) => setHistory({ status: "ready", items: list.items, total: list.total }),
      (error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        if (!(error instanceof ApiError)) {
          // request() бросает только ApiError — прочее ошибка программирования.
          throw error;
        }
        setHistory({ status: "error", error });
      },
    );
    return () => controller.abort();
  }, [historyReload]);

  const retryHistory = useCallback(() => setHistoryReload((value) => value + 1), []);

  /**
   * Догружает следующую порцию истории (`limit`/`offset`, api_contract.md,
   * 4.8): offset считается от уже показанных батчей, новое не сбрасывает
   * старое (frontend.md, панель «Предыдущие батчи»).
   */
  const loadMoreHistory = useCallback(() => {
    if (history.status !== "ready" || historyLoadingMore) {
      return;
    }
    const offset = history.items.length;
    historyMoreController.current?.abort();
    const controller = new AbortController();
    historyMoreController.current = controller;
    setHistoryLoadingMore(true);
    setHistoryMoreError(null);
    void listBatches(
      { limit: BATCH_HISTORY_LIMIT, offset },
      controller.signal,
    ).then(
      (list) => {
        setHistory((state) =>
          state.status === "ready"
            ? {
                status: "ready",
                // Между запросами история могла пополниться сместившими
                // offset новыми батчами — дубликаты отбрасываем по id.
                items: [
                  ...state.items,
                  ...list.items.filter(
                    (item) =>
                      !state.items.some(
                        (known) => known.batch_id === item.batch_id,
                      ),
                  ),
                ],
                total: list.total,
              }
            : state,
        );
        setHistoryLoadingMore(false);
      },
      (error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        if (!(error instanceof ApiError)) {
          // request() бросает только ApiError — прочее ошибка программирования.
          throw error;
        }
        setHistoryMoreError(error);
        setHistoryLoadingMore(false);
      },
    );
  }, [history, historyLoadingMore]);

  // Серверная копия авторитетна, пока загрузилась; иначе — локальная.
  const batch = remote.status === "ready" ? remote.batch : local.batch;
  const response = batch?.response ?? null;
  const showLocalFallbackNotice =
    local.fromState && local.batch !== null && remote.status !== "ready";

  return (
    <section className="page">
      <div>
        <h1>{t("pages.results.title")}</h1>
        <p className="page__description">{t("pages.results.description")}</p>
      </div>

      {remote.status === "error" ? <ErrorBanner error={remote.error} /> : null}
      {response !== null && response.persisted === false ? (
        <p className="notice" role="alert">
          {t("pages.results.notPersisted")}
        </p>
      ) : null}
      {showLocalFallbackNotice ? (
        <p className="notice" role="alert">
          {t("pages.results.localFallback")}
        </p>
      ) : null}

      {response !== null ? (
        <>
          <section className="panel">
            <h2 className="panel__title">{t("results.summary.title")}</h2>
            <ResultsSummary response={response} />
          </section>

          <section className="panel">
            <div className="panel__header">
              <h2 className="panel__title">{t("results.table.caption")}</h2>
              <div className="panel__actions">
                <ExportCsvButton results={response.results} cards={batch?.cards} />
              </div>
            </div>

            <StatusLegend threshold={batch?.threshold} />
            <ResultsTable results={response.results} threshold={batch?.threshold} />
          </section>
        </>
      ) : remote.status === "loading" ? (
        <Loader />
      ) : (
        <EmptyState message={t("pages.results.empty")} />
      )}

      <section className="panel">
        <div className="panel__header">
          <h2 className="panel__title">{t("pages.results.history.title")}</h2>
        </div>

        {history.status === "loading" ? <Loader /> : null}
        {history.status === "error" ? (
          <>
            <ErrorBanner error={history.error} />
            <button type="button" className="link" onClick={retryHistory}>
              {t("pages.results.history.retry")}
            </button>
          </>
        ) : null}
        {history.status === "ready" && history.items.length === 0 ? (
          <EmptyState message={t("pages.results.history.empty")} />
        ) : null}
        {history.status === "ready" && history.items.length > 0 ? (
          <>
            <ul className="history">
              {history.items.map((item) => (
                <li key={item.batch_id} className="history__item">
                  <Link
                    className="history__link"
                    to={`/results?batch_id=${encodeURIComponent(item.batch_id)}`}
                    aria-current={item.batch_id === batchId ? "true" : undefined}
                  >
                    <span className="history__date">
                      {formatDateTime(item.created_at, i18n.language)}
                    </span>
                    <span className="history__summary">
                      {t("pages.results.history.row", {
                        total: item.total,
                        ok: item.ok,
                        lowConfidence: item.low_confidence,
                        errors: item.errors,
                      })}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>

            {historyMoreError !== null ? (
              <ErrorBanner error={historyMoreError} />
            ) : null}

            <div className="history__footer">
              {/* Счётчик склоняется по числу показанных батчей
                  (plural-ключи с `count`, i18next). */}
              <p className="history__shown">
                {t("pages.results.history.shown", {
                  count: history.items.length,
                  total: history.total,
                })}
              </p>
              {history.items.length < history.total ? (
                <button
                  type="button"
                  className="link"
                  disabled={historyLoadingMore}
                  onClick={loadMoreHistory}
                >
                  {t("pages.results.history.showMore")}
                </button>
              ) : null}
            </div>
          </>
        ) : null}
      </section>
    </section>
  );
}
