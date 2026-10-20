/**
 * Сохранение последнего успешного батча между переходами по маршрутам.
 *
 * Сервер хранит историю батчей (api_contract.md, 4.8/4.9), но страница
 * результатов показывает батч сразу после запуска с главной — для этого
 * служит локальная копия. Она же остаётся фолбэком для dev-режима без
 * настроенной БД и для батчей, которые сервер не успел сохранить
 * (`persisted=false`). Держать батч в `location.state` нельзя как основной
 * путь: при повторном переходе по ссылке навигации состояние теряется
 * (state используется только как последний шанс при недоступном
 * localStorage — см. PageHome).
 *
 * Чтение терпимо к повреждённым данным: при ошибке разбора запись удаляется и
 * возвращается `null`, чтобы страница показала пустое состояние, а не упала.
 * Ошибка записи не подавляется молча (замечание ревью): `writeLastBatch`
 * возвращает успех, и вызывающий код решает, как предупредить пользователя.
 */

import { LAST_BATCH_STORAGE_KEY } from "../constants";
import type { BatchExtractResponse, ProductCardRequest } from "../schemas/api";

/** Данные последнего успешного батча, нужные странице результатов. */
export type StoredBatch = {
  /** Успешный ответ батча — источник сводки и строк таблицы. */
  response: BatchExtractResponse;
  /**
   * Порог уверенности батча для подсветки и пояснения низкоуверенных значений
   * (design.md, §8); может отсутствовать, если батч запускался без
   * переопределения.
   */
  threshold?: number;
  /** Исходные карточки батча — источник колонки `title` в CSV-экспорте. */
  cards?: ProductCardRequest[];
};

function isStoredBatch(value: unknown): value is StoredBatch {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const response = (value as { response?: unknown }).response;
  return typeof response === "object" && response !== null;
}

/** Читает последний сохранённый батч или `null`, если его нет/данные битые. */
export function readLastBatch(): StoredBatch | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(LAST_BATCH_STORAGE_KEY);
    if (raw === null) {
      return null;
    }
    const parsed: unknown = JSON.parse(raw);
    if (!isStoredBatch(parsed)) {
      // Запись не той формы (например, оставшаяся от старой версии) — убираем,
      // чтобы не отдавать странице мусор.
      clearLastBatch();
      return null;
    }
    return parsed;
  } catch {
    // Повреждённый JSON или недоступный localStorage (приватный режим):
    // не роняем страницу, просто считаем, что батча нет.
    clearLastBatch();
    return null;
  }
}

/**
 * Сохраняет последний батч.
 *
 * @returns `true`, если запись выполнена (или окружение без `window`);
 * `false` — запись не удалась (исчерпана квота, localStorage недоступен).
 * Причина не печатается в консоль (клиентская библиотека без side-эффектов
 * логирования) — сигнал вызывающему коду: он обязан учесть потерю локальной
 * копии (например, передать батч через state маршрута или предупредить).
 */
export function writeLastBatch(batch: StoredBatch): boolean {
  if (typeof window === "undefined") {
    return true;
  }
  try {
    window.localStorage.setItem(LAST_BATCH_STORAGE_KEY, JSON.stringify(batch));
    return true;
  } catch {
    // Квота исчерпана или localStorage недоступен (приватный режим):
    // сохранять некуда, но молчать об этом нельзя — см. возвращаемое значение.
    return false;
  }
}

/** Удаляет сохранённый батч (кнопка «Новый батч», frontend.md, §8.2). */
export function clearLastBatch(): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.removeItem(LAST_BATCH_STORAGE_KEY);
  } catch {
    // localStorage недоступен — удалять нечего.
  }
}
