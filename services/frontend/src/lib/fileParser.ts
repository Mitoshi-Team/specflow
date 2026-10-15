/**
 * Разбор загружаемых файлов карточек (CSV/JSON/TSV).
 *
 * Чистый модуль без React: детекция формата, парсинг, нормализация и
 * валидация минимального набора полей (frontend.md, 6.3). UI не участвует
 * в разборе — компонент `FileUpload` лишь отображает результат, а хук
 * `useFileParser` управляет асинхронным состоянием.
 */

import * as Papa from "papaparse";

import {
  CSV_DELIMITER,
  MAX_UPLOAD_SIZE_BYTES,
  TSV_DELIMITER,
} from "../constants";
import type { ProductCardRequest, SellerAttributes } from "../schemas/api";

/** Поддерживаемые форматы входных файлов. */
export type FileFormat = "csv" | "json" | "tsv";

/**
 * Коды ошибок разбора. UI переводит их в тексты через i18n
 * (`fileUpload.errors.<code>`), поэтому модуль не формирует текст.
 */
export type FileParseErrorCode =
  | "emptyFile"
  | "unsupportedFormat"
  | "fileTooLarge"
  | "readError"
  | "invalidJson"
  | "invalidStructure"
  | "invalidSellerAttributes"
  | "noContent"
  | "noCards";

export type FileParseError = {
  code: FileParseErrorCode;
  /**
   * Позиция проблемного элемента (1-based): номер строки для CSV/TSV
   * (с учётом строки заголовка) или индекс элемента для JSON-массива.
   */
  row?: number;
};

export type FileParseResult =
  | { ok: true; format: FileFormat; cards: ProductCardRequest[] }
  | { ok: false; error: FileParseError };

type CardResult =
  | { ok: true; card: ProductCardRequest }
  | { ok: false; error: FileParseError };

const EXTENSION_TO_FORMAT: Record<string, FileFormat> = {
  csv: "csv",
  json: "json",
  tsv: "tsv",
};

/** Поля ProductCardRequest, значениями которых должны быть строки. */
const STRING_FIELDS = [
  "product_id",
  "title",
  "description",
  "category_id",
  "category_name",
  "language",
] as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Приводит значение к непустой строке, обрезая пробелы; иначе undefined. */
function normalizeText(value: unknown): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed === "" ? undefined : trimmed;
}

/** Минимум одно непустое из title | description | seller_attributes. */
function hasContent(card: ProductCardRequest): boolean {
  if (card.title || card.description) {
    return true;
  }
  return (
    card.seller_attributes !== undefined &&
    Object.keys(card.seller_attributes).length > 0
  );
}

/**
 * Определяет формат по расширению имени файла. Расширение в спецификации
 * считается опциональным признаком, поэтому неизвестное расширение — это
 * ошибка `unsupportedFormat` (содержимое не подбирается эвристикой).
 */
export function detectFormat(fileName: string): FileFormat | null {
  const dotIndex = fileName.lastIndexOf(".");
  if (dotIndex < 0 || dotIndex === fileName.length - 1) {
    return null;
  }
  const extension = fileName.slice(dotIndex + 1).toLowerCase();
  return EXTENSION_TO_FORMAT[extension] ?? null;
}

function csvRowToCard(row: Record<string, string>): CardResult {
  let sellerAttributes: SellerAttributes | undefined;
  const rawSellerAttributes = normalizeText(row.seller_attributes);
  if (rawSellerAttributes !== undefined) {
    let parsed: unknown;
    try {
      parsed = JSON.parse(rawSellerAttributes);
    } catch {
      return { ok: false, error: { code: "invalidSellerAttributes" } };
    }
    if (!isRecord(parsed)) {
      return { ok: false, error: { code: "invalidSellerAttributes" } };
    }
    sellerAttributes = parsed;
  }

  const card: ProductCardRequest = {};
  const productId = normalizeText(row.product_id);
  if (productId !== undefined) {
    card.product_id = productId;
  }
  const title = normalizeText(row.title);
  if (title !== undefined) {
    card.title = title;
  }
  const description = normalizeText(row.description);
  if (description !== undefined) {
    card.description = description;
  }
  if (sellerAttributes !== undefined) {
    card.seller_attributes = sellerAttributes;
  }
  const categoryId = normalizeText(row.category_id);
  if (categoryId !== undefined) {
    card.category_id = categoryId;
  }
  const categoryName = normalizeText(row.category_name);
  if (categoryName !== undefined) {
    card.category_name = categoryName;
  }
  const language = normalizeText(row.language);
  if (language !== undefined) {
    card.language = language;
  }

  if (!hasContent(card)) {
    return { ok: false, error: { code: "noContent" } };
  }
  return { ok: true, card };
}

function parseDelimited(content: string, format: "csv" | "tsv"): FileParseResult {
  const delimiter = format === "tsv" ? TSV_DELIMITER : CSV_DELIMITER;
  const { data } = Papa.parse<Record<string, string>>(content, {
    header: true,
    delimiter,
    skipEmptyLines: true,
  });

  if (data.length === 0) {
    return { ok: false, error: { code: "noCards" } };
  }

  const cards: ProductCardRequest[] = [];
  for (let index = 0; index < data.length; index += 1) {
    const rowResult = csvRowToCard(data[index]);
    if (!rowResult.ok) {
      // Строка 1 — заголовок, поэтому данные начинаются со строки 2.
      return { ok: false, error: { ...rowResult.error, row: index + 2 } };
    }
    cards.push(rowResult.card);
  }

  return { ok: true, format, cards };
}

function jsonItemToCard(item: Record<string, unknown>): CardResult {
  let sellerAttributes: SellerAttributes | undefined;
  if (item.seller_attributes !== undefined && item.seller_attributes !== null) {
    if (!isRecord(item.seller_attributes)) {
      return { ok: false, error: { code: "invalidStructure" } };
    }
    sellerAttributes = item.seller_attributes;
  }

  const card: ProductCardRequest = {};
  for (const field of STRING_FIELDS) {
    const value = item[field];
    if (value === undefined || value === null) {
      continue;
    }
    if (typeof value !== "string") {
      return { ok: false, error: { code: "invalidStructure" } };
    }
    const trimmed = value.trim();
    if (trimmed === "") {
      continue;
    }
    card[field] = trimmed;
  }
  if (sellerAttributes !== undefined) {
    card.seller_attributes = sellerAttributes;
  }

  if (!hasContent(card)) {
    return { ok: false, error: { code: "noContent" } };
  }
  return { ok: true, card };
}

function parseJson(content: string): FileParseResult {
  let parsed: unknown;
  try {
    parsed = JSON.parse(content);
  } catch {
    return { ok: false, error: { code: "invalidJson" } };
  }

  if (!Array.isArray(parsed)) {
    return { ok: false, error: { code: "invalidStructure" } };
  }
  if (parsed.length === 0) {
    return { ok: false, error: { code: "noCards" } };
  }

  const cards: ProductCardRequest[] = [];
  for (let index = 0; index < parsed.length; index += 1) {
    const item = parsed[index];
    if (!isRecord(item)) {
      return { ok: false, error: { code: "invalidStructure", row: index + 1 } };
    }
    const itemResult = jsonItemToCard(item);
    if (!itemResult.ok) {
      return { ok: false, error: { ...itemResult.error, row: index + 1 } };
    }
    cards.push(itemResult.card);
  }

  return { ok: true, format: "json", cards };
}

/**
 * Разбирает текстовое содержимое файла заданного формата.
 * Пустое содержимое (в т.ч. из одних пробелов) считается ошибкой `emptyFile`.
 */
export function parseFileContent(
  content: string,
  format: FileFormat,
): FileParseResult {
  if (content.trim() === "") {
    return { ok: false, error: { code: "emptyFile" } };
  }
  if (format === "json") {
    return parseJson(content);
  }
  return parseDelimited(content, format);
}

/**
 * Читает и разбирает файл. Формат определяется по расширению, затем
 * проверяются размер и содержимое.
 */
export async function parseFile(file: File): Promise<FileParseResult> {
  const format = detectFormat(file.name);
  if (format === null) {
    return { ok: false, error: { code: "unsupportedFormat" } };
  }
  if (file.size > MAX_UPLOAD_SIZE_BYTES) {
    return { ok: false, error: { code: "fileTooLarge" } };
  }
  if (file.size === 0) {
    return { ok: false, error: { code: "emptyFile" } };
  }

  let content: string;
  try {
    content = await file.text();
  } catch {
    return { ok: false, error: { code: "readError" } };
  }

  return parseFileContent(content, format);
}
