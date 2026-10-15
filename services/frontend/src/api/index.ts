/**
 * Типизированные методы API — по одному на эндпоинт контракта
 * (openspec/specs/api_contract.md, раздел 4).
 */

import type {
  BatchExtractRequest,
  BatchExtractResponse,
  CategoryListResponse,
  CategorySchema,
  ConfigResponse,
  ExtractionResponseItem,
  HealthResponse,
  InfoResponse,
  ListCategoriesParams,
  ProductCardRequest,
} from "../schemas/api";
import { request } from "./client";

export { ApiError, request } from "./client";
export type { QueryValue, RequestOptions } from "./client";

/** POST /extract — извлечение атрибутов для одной карточки. */
export function extract(
  card: ProductCardRequest,
  signal?: AbortSignal,
): Promise<ExtractionResponseItem> {
  return request<ExtractionResponseItem>("/extract", {
    method: "POST",
    body: card,
    signal,
  });
}

/** POST /extract/batch — пакетное извлечение. */
export function extractBatch(
  payload: BatchExtractRequest,
  signal?: AbortSignal,
): Promise<BatchExtractResponse> {
  return request<BatchExtractResponse>("/extract/batch", {
    method: "POST",
    body: payload,
    signal,
  });
}

/** GET /categories — список категорий со схемами. */
export function listCategories(
  params: ListCategoriesParams = {},
  signal?: AbortSignal,
): Promise<CategoryListResponse> {
  return request<CategoryListResponse>("/categories", { query: params, signal });
}

/** GET /categories/{category} — схема конкретной категории. */
export function getCategory(
  category: string,
  signal?: AbortSignal,
): Promise<CategorySchema> {
  return request<CategorySchema>(
    `/categories/${encodeURIComponent(category)}`,
    { signal },
  );
}

/** GET /health — проверка работоспособности сервиса. */
export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>("/health", { signal });
}

/** GET /info — информация о сервисе и пайплайне. */
export function getInfo(signal?: AbortSignal): Promise<InfoResponse> {
  return request<InfoResponse>("/info", { signal });
}

/** GET /config — текущая конфигурация пайплайна (read-only). */
export function getConfig(signal?: AbortSignal): Promise<ConfigResponse> {
  return request<ConfigResponse>("/config", { signal });
}
