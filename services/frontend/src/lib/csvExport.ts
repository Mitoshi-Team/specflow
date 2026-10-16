/**
 * Сериализация результатов батча в CSV формата PredictionRow
 * (domain-model.md, 3.7; frontend.md, 5.4 «Сценарий 4. Экспорт CSV»).
 *
 * Чистый модуль без React и DOM: он только строит CSV-строку. Скачивание
 * файла — задача хука `useCsvExport`; такое разделение позволяет покрыть
 * логику сериализации и экранирования тестами без браузерного окружения.
 *
 * Порядок колонок взят из таблицы PredictionRow (domain-model.md, 3.7):
 * `product_id`, `title`, `category`, затем пары колонок по каждому атрибуту
 * (`[attribute_code]`, `[attribute_code]_confidence`), затем `needs_review`
 * и `status`.
 */

import { CSV_DELIMITER } from "../constants";
import type { ExtractionResponseItem, ProductCardRequest } from "../schemas/api";

/**
 * Суффикс колонки уверенности: `[attribute_code]_confidence`
 * (frontend.md, 5.4; domain-model.md, 3.7).
 */
export const CONFIDENCE_COLUMN_SUFFIX = "_confidence";

/** Строковое представление булева значения в CSV (спецификация формат не задаёт). */
export const CSV_BOOLEAN_TRUE = "true";
export const CSV_BOOLEAN_FALSE = "false";

/** Символ экранирования значения — двойная кавычка (RFC 4180). */
const QUOTE = '"';

/**
 * Разделитель строк CSV. RFC 4180 предписывает CRLF; спецификация конкретный
 * перевод строки не оговаривает.
 */
const LINE_BREAK = "\r\n";

/**
 * Фиксированные колонки PredictionRow, идущие до блока атрибутов
 * (domain-model.md, 3.7).
 */
const LEADING_COLUMNS = ["product_id", "title", "category"] as const;

/**
 * Фиксированные колонки PredictionRow, идущие после блока атрибутов
 * (domain-model.md, 3.7).
 */
const TRAILING_COLUMNS = ["needs_review", "status"] as const;

/**
 * Экранирует значение для CSV по стандарту RFC 4180: значение берётся в
 * кавычки, если содержит разделитель, кавычку или перевод строки; внутренние
 * кавычки удваиваются.
 *
 * ⚠️ В спецификациях правила экранирования не описаны (frontend.md, 5.4
 * задаёт только разделитель `,` и кодировку UTF-8). Принят стандарт RFC 4180 —
 * он же используется `papaparse` при разборе CSV (frontend.md, 3.1).
 */
export function escapeCsvValue(value: string): string {
  const needsQuoting =
    value.includes(CSV_DELIMITER) ||
    value.includes(QUOTE) ||
    value.includes("\n") ||
    value.includes("\r");
  if (!needsQuoting) {
    return value;
  }
  return `${QUOTE}${value.split(QUOTE).join(QUOTE + QUOTE)}${QUOTE}`;
}

/**
 * Собирает коды атрибутов по всем результатам в порядке первого появления.
 * Каждому коду соответствуют две колонки: значение и уверенность
 * (domain-model.md, 3.7).
 */
export function collectAttributeCodes(
  results: ExtractionResponseItem[],
): string[] {
  const codes: string[] = [];
  const seen = new Set<string>();
  for (const result of results) {
    for (const attribute of result.attributes) {
      if (!seen.has(attribute.attribute_code)) {
        seen.add(attribute.attribute_code);
        codes.push(attribute.attribute_code);
      }
    }
  }
  return codes;
}

/** Заголовки колонок PredictionRow для переданных результатов. */
export function predictionColumns(
  results: ExtractionResponseItem[],
): string[] {
  const attributeColumns = collectAttributeCodes(results).flatMap((code) => [
    code,
    `${code}${CONFIDENCE_COLUMN_SUFFIX}`,
  ]);
  return [...LEADING_COLUMNS, ...attributeColumns, ...TRAILING_COLUMNS];
}

function indexTitlesByProductId(
  cards: ProductCardRequest[],
): Map<string, string> {
  const titleById = new Map<string, string>();
  for (const card of cards) {
    if (card.product_id !== undefined && !titleById.has(card.product_id)) {
      titleById.set(card.product_id, card.title ?? "");
    }
  }
  return titleById;
}

/**
 * Определяет исходное название карточки для строки предсказания.
 *
 * `ExtractionResponseItem` не содержит `title` (api_contract.md, 3.3), хотя
 * формат PredictionRow его требует (domain-model.md, 3.7). Значение берётся из
 * исходных карточек батча: по `product_id` (он предназначен «для сопоставления
 * с эталоном/выходом», domain-model.md, 3.1), иначе — по позиции результата,
 * так как результаты батча соответствуют отправленным карточкам по порядку.
 * Если карточек нет — ячейка остаётся пустой.
 */
function resolveTitle(
  result: ExtractionResponseItem,
  index: number,
  cards: ProductCardRequest[],
  titleById: Map<string, string>,
): string {
  if (result.product_id !== undefined) {
    const byId = titleById.get(result.product_id);
    if (byId !== undefined) {
      return byId;
    }
  }
  return cards[index]?.title ?? "";
}

function resultToRow(
  result: ExtractionResponseItem,
  index: number,
  attributeCodes: string[],
  cards: ProductCardRequest[],
  titleById: Map<string, string>,
): string[] {
  const values: string[] = [
    result.product_id ?? "",
    resolveTitle(result, index, cards, titleById),
    result.category_name ?? result.category_id ?? "",
  ];

  for (const code of attributeCodes) {
    const attribute = result.attributes.find(
      (candidate) => candidate.attribute_code === code,
    );
    values.push(attribute?.normalized_value ?? "");
    values.push(attribute === undefined ? "" : String(attribute.confidence));
  }

  values.push(result.needs_review ? CSV_BOOLEAN_TRUE : CSV_BOOLEAN_FALSE);
  values.push(result.status);

  return values;
}

/**
 * Строит CSV формата PredictionRow по результатам батча.
 *
 * @param results — результаты обработки по каждой карточке (api_contract.md, 3.3).
 * @param cards — исходные карточки батча; используются для колонки `title`,
 *   которой нет в ответе API (domain-model.md, 3.7).
 *
 * Экспортируются все результаты, как они пришли в ответе батча. Отсутствующие
 * значения записываются пустыми ячейками («Пустые ячейки для не извлечённых»,
 * frontend.md, 5.4). Каждое значение экранируется через `escapeCsvValue`.
 */
export function serializePredictionsCsv(
  results: ExtractionResponseItem[],
  cards: ProductCardRequest[] = [],
): string {
  const columns = predictionColumns(results);
  const attributeCodes = collectAttributeCodes(results);
  const titleById = indexTitlesByProductId(cards);

  const rows: string[][] = [columns];
  for (let index = 0; index < results.length; index += 1) {
    rows.push(
      resultToRow(results[index], index, attributeCodes, cards, titleById),
    );
  }

  return (
    rows
      .map((row) => row.map(escapeCsvValue).join(CSV_DELIMITER))
      .join(LINE_BREAK) + LINE_BREAK
  );
}
