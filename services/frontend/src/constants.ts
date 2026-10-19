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

/**
 * Имя CSV-файла с предсказаниями по умолчанию (frontend.md, 5.4).
 *
 * ⚠️ В спецификациях имя файла не задано; значение принято по умолчанию и
 * вынесено сюда, чтобы не хранить строку inline в бизнес-логике (rules.md).
 */
export const PREDICTIONS_CSV_FILENAME = "predictions.csv";

/**
 * MIME-тип CSV-файла предсказаний. Кодировка UTF-8 задана спецификацией
 * (frontend.md, 5.4); BOM не добавляется, так как спецификация его не
 * требует.
 */
export const CSV_MIME_TYPE = "text/csv;charset=utf-8";

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
 * Границы высоты поля описания одной карточки (px). Ниже поля не хватает
 * даже на несколько строк, выше — включается внутренний скролл, чтобы
 * текстовое поле нельзя было растянуть бесконечно (`CardTextInput`).
 */
export const CARD_TEXT_MIN_HEIGHT_PX = 160;
export const CARD_TEXT_MAX_HEIGHT_PX = 480;

/**
 * Размер батча по умолчанию.
 *
 * ⚠️ Отличается от значения в спецификации (frontend.md, 9.2:
 * `VITE_DEFAULT_BATCH_SIZE=10`; сценарий 2 — «по умолчанию 10–20, макс. 50»):
 * по требованию считается равным 1, чтобы карточки обрабатывались по одной.
 */
export const DEFAULT_BATCH_SIZE = 1;

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

/**
 * Ключ localStorage для последнего успешного батча (frontend.md, §7:
 * «useLocalStorage — сохранение последнего батча»). Нужен, чтобы результат не
 * терялся при переходах между страницами и перезагрузке.
 */
export const LAST_BATCH_STORAGE_KEY = "specflow.lastBatch";
