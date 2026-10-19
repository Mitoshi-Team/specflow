/**
 * Сохранение последнего успешного батча между переходами по маршрутам.
 *
 * API не хранит выполненные батчи (api_contract.md), а ответ нужен странице
 * результатов после перехода с главной. Держать его в `location.state` нельзя:
 * при повторном переходе по ссылке навигации состояние маршрута теряется.
 * Поэтому последний батч кладётся в localStorage (frontend.md, §7:
 * «useLocalStorage — сохранение последнего батча»).
 *
 * Чтение терпимо к повреждённым данным: при ошибке разбора запись удаляется и
 * возвращается `null`, чтобы страница показала пустое состояние, а не упала.
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
 * Переполнение квоты localStorage не является фатальным: навигация и показ
 * результатов текущего перехода продолжают работать, а между переходами
 * результат может не пережить перезагрузку.
 */
export function writeLastBatch(batch: StoredBatch): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(LAST_BATCH_STORAGE_KEY, JSON.stringify(batch));
  } catch {
    // Квота исчерпана или localStorage недоступен — сохранять некуда.
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
