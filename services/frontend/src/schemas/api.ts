/**
 * TypeScript-типы, синхронизированные с API-контрактом.
 *
 * Источник: openspec/specs/api_contract.md. Имена полей, признак
 * optional и значения перечислений соответствуют контракту буквально.
 * При расхождении с доменной моделью (domain-model.md) приоритет у
 * API-контракта.
 */

/** Раздел 3.2: метод извлечения атрибута. */
export type ExtractionMethod =
  | "rule"
  | "dict"
  | "ner"
  | "classifier"
  | "ml_transformer"
  | "llm"
  | "hybrid";

/** Раздел 3.2: поле-источник упоминания (Span.field). */
export type SpanField = "title" | "description" | "seller_attributes";

/** Раздел 3.3: статус обработки карточки. */
export type ExtractionStatus =
  | "ok"
  | "low_confidence"
  | "partial"
  | "error"
  | "skipped";

/** Раздел 3.7: статус работоспособности сервиса. */
export type HealthStatus = "ok" | "degraded" | "down";

/**
 * Раздел 3.2: тип значения атрибута категории.
 * Контракт приводит только примеры "string" и "enum"; полный набор
 * значений задан в domain-model.md (раздел 3.2).
 */
export type AttributeValueType =
  | "string"
  | "number"
  | "enum"
  | "boolean"
  | "unit_value";

/** Раздел 3.1: seller_attributes — произвольный объект ключ-значение. */
export type SellerAttributes = Record<string, unknown>;

/** Раздел 3.1: ProductCardRequest. Все поля опциональны. */
export type ProductCardRequest = {
  product_id?: string;
  title?: string;
  description?: string;
  seller_attributes?: SellerAttributes;
  category_id?: string;
  category_name?: string;
  language?: string;
};

/** Раздел 3.2: Span. */
export type Span = {
  field: SpanField;
  text: string;
  start?: number;
  end?: number;
};

/** Раздел 3.2: AttributePrediction. */
export type AttributePrediction = {
  attribute_code: string;
  raw_value: string;
  normalized_value: string;
  confidence: number;
  evidence_text?: string;
  source_spans?: Span[];
  extraction_method: ExtractionMethod;
  is_confirmed_in_text: boolean;
};

/** Раздел 3.3: ExtractionResponseItem. */
export type ExtractionResponseItem = {
  product_id?: string;
  category_id?: string;
  category_name?: string;
  attributes: AttributePrediction[];
  status: ExtractionStatus;
  needs_review: boolean;
  low_confidence_count?: number;
  processing_time_ms?: number;
  pipeline_version: string;
};

/** Раздел 3.4: BatchExtractRequest. batch_size ∈ [1, 50]. */
export type BatchExtractRequest = {
  items: ProductCardRequest[];
  batch_id?: string;
  batch_size?: number;
  return_sources?: boolean;
  return_raw_values?: boolean;
  threshold_override?: number;
};

/** Раздел 3.5: BatchExtractResponse. */
export type BatchExtractResponse = {
  batch_id?: string;
  total: number;
  ok: number;
  low_confidence: number;
  errors: number;
  results: ExtractionResponseItem[];
  processing_time_ms_total?: number;
  /** Раздел 3.5: false — батч не сохранён в серверной истории. */
  persisted?: boolean;
};

/** Раздел 3.9: BatchSummary — краткая сводка сохранённого батча. */
export type BatchSummary = {
  batch_id: string;
  created_at: string;
  total: number;
  ok: number;
  low_confidence: number;
  errors: number;
  threshold?: number | null;
};

/** Раздел 3.10: BatchListResponse — история батчей, новые первыми. */
export type BatchListResponse = {
  items: BatchSummary[];
  total: number;
};

/** Раздел 3.11: StoredBatchResponse — полностью сохранённый батч. */
export type StoredBatchResponse = {
  batch_id: string;
  created_at: string;
  threshold?: number | null;
  cards?: ProductCardRequest[];
  response: BatchExtractResponse;
};

/**
 * Раздел 3.6: описание атрибута внутри CategorySchema.
 * Контракт показывает поля code, value_type, is_required и vocab без
 * отдельной именованной схемы; is_required/vocab присутствуют не во
 * всех примерах, поэтому помечены опциональными.
 */
export type CategoryAttribute = {
  code: string;
  value_type: AttributeValueType;
  is_required?: boolean;
  vocab?: string[];
};

/** Раздел 3.6: CategorySchema. */
export type CategorySchema = {
  category: string;
  category_id?: string;
  required_attributes: CategoryAttribute[];
  optional_attributes: CategoryAttribute[];
  schema_version: string;
};

/** Раздел 4.3: параметры запроса GET /categories. */
export type ListCategoriesParams = {
  category?: string;
  limit?: number;
  offset?: number;
};

/** Раздел 4.8: параметры запроса GET /batches. */
export type BatchListParams = {
  limit?: number;
  offset?: number;
};

/** Раздел 4.3: ответ GET /categories. */
export type CategoryListResponse = {
  items: CategorySchema[];
  total: number;
};

/**
 * Раздел 3.7: HealthResponse.
 * Контракт не перечисляет значения models_loaded как enum, поэтому
 * тип оставлен строковым.
 */
export type HealthResponse = {
  status: HealthStatus;
  version: string;
  pipeline_version: string;
  uptime_seconds: number;
  models_loaded: string[];
  cache_enabled: boolean;
};

/** Раздел 4.6: флаги возможностей сервиса. */
export type InfoFeatures = {
  grounding_required: boolean;
  normalization: boolean;
  unit_conversion: boolean;
  traffic_weighted_metrics: boolean;
};

/** Раздел 4.6: InfoResponse. */
export type InfoResponse = {
  service_name: string;
  version: string;
  pipeline_version: string;
  extraction_methods: ExtractionMethod[];
  default_threshold: number;
  supports_batch: boolean;
  max_batch_size: number;
  text_only: boolean;
  features: InfoFeatures;
};

/**
 * Раздел 4.7: ConfigResponse (read-only).
 * Внутренняя структура confidence_thresholds и method_weights в
 * контракте не описана, поэтому используются словари чисел.
 */
export type ConfigResponse = {
  confidence_thresholds: Record<string, number>;
  method_weights: Record<string, number>;
  hybrid_strategy: string;
  llm_enabled: boolean;
};

/** Раздел 3.8: элемент списка ошибок валидации. */
export type ErrorDetail = {
  loc: string[];
  msg: string;
  type: string;
};

/** Раздел 3.8: ErrorResponse. */
export type ErrorResponse = {
  detail: string;
  code?: string;
  errors?: ErrorDetail[];
};
