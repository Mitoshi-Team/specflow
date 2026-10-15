/**
 * Константы уровня приложения.
 *
 * Значения, используемые в бизнес-логике, вынесены сюда, чтобы не хранить
 * «магические числа» inline (см. rules.md).
 */

/** Расширения файлов, принимаемых загрузчиком карточек (frontend.md, 6.3). */
export const ACCEPTED_FILE_EXTENSIONS = [".csv", ".json", ".tsv"] as const;

/** Разделитель полей CSV-файла (frontend.md, 5.4). */
export const CSV_DELIMITER = ",";

/** Разделитель полей TSV-файла. */
export const TSV_DELIMITER = "\t";

/**
 * Максимальный размер загружаемого файла в байтах.
 *
 * ⚠️ В спецификациях задано только «разумный размер» без конкретного
 * значения (frontend.md, 6.3). Здесь принято допущение 5 МиБ; при
 * необходимости значение уточняется вместе с лимитом nginx
 * (`client_max_body_size`).
 */
export const MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024;

/**
 * Сколько первых строк файла показывать в предпросмотре
 * (frontend.md, 9.2: `VITE_MAX_PREVIEW`, по умолчанию 20).
 */
export const PREVIEW_MAX_ROWS = 20;

/**
 * Размер батча по умолчанию (frontend.md, 9.2: `VITE_DEFAULT_BATCH_SIZE=10`;
 * сценарий 2 — «`batch_size` по умолчанию 10–20, макс. 50»).
 */
export const DEFAULT_BATCH_SIZE = 10;

/** Минимальный размер батча (api_contract.md, раздел 2: `batch_size` ∈ [1, 50]). */
export const MIN_BATCH_SIZE = 1;

/** Максимальный размер батча (api_contract.md, раздел 2: `batch_size` ∈ [1, 50]). */
export const MAX_BATCH_SIZE = 50;

/**
 * Порог уверенности по умолчанию (frontend.md, 9.2:
 * `VITE_DEFAULT_THRESHOLD=0.80`; совпадает с `default_threshold` из GET /info).
 */
export const DEFAULT_CONFIDENCE_THRESHOLD = 0.8;

/**
 * Границы порога уверенности: `confidence` ∈ [0.0, 1.0]
 * (api_contract.md, раздел 3.2; `threshold_override` переопределяет порог).
 */
export const MIN_CONFIDENCE_THRESHOLD = 0;
export const MAX_CONFIDENCE_THRESHOLD = 1;

/** Шаг ввода порога уверенности в UI (десятые доли единицы). */
export const CONFIDENCE_THRESHOLD_STEP = 0.01;
