/**
 * Низкоуровневый HTTP-клиент: единая точка отправки запросов и единая
 * обработка ошибок в формате ErrorResponse (api_contract.md, раздел 3.8).
 */

import type { ErrorDetail, ErrorResponse } from "../schemas/api";
import { API_ERROR_KEYS, API_PREFIX } from "./constants";

/** Значения query-параметров, допустимые в запросе. */
export type QueryValue = string | number | boolean | undefined | null;

export type RequestOptions = {
  method?: string;
  body?: unknown;
  query?: Record<string, QueryValue>;
  signal?: AbortSignal;
};

type ApiErrorInit = {
  /** HTTP-статус ответа; 0 — сетевой сбой без ответа. */
  status: number;
  /** Ключ i18n или текст сообщения (см. API_ERROR_KEYS). */
  message: string;
  code?: string;
  detail?: string;
  errors?: ErrorDetail[];
  cause?: unknown;
};

/** Ошибка обращения к API. Содержит данные контрактного ErrorResponse. */
export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly detail?: string;
  readonly errors?: ErrorDetail[];

  constructor(init: ApiErrorInit) {
    super(init.message, { cause: init.cause });
    this.name = "ApiError";
    this.status = init.status;
    this.code = init.code;
    this.detail = init.detail;
    this.errors = init.errors;
  }
}

/**
 * Базовый URL читается при каждом запросе, а не на этапе загрузки модуля,
 * чтобы значение можно было переопределять в тестах и при конфигурации.
 */
function getBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL ?? "";
}

function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const url = `${getBaseUrl()}${API_PREFIX}${path}`;
  if (!query) {
    return url;
  }

  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null) {
      continue;
    }
    params.append(key, String(value));
  }

  const queryString = params.toString();
  return queryString ? `${url}?${queryString}` : url;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/**
 * Разбирает тело ответа в ErrorResponse, устойчиво к ответам, не
 * соответствующим контракту (например, нативный 422 FastAPI, где
 * detail является массивом).
 */
async function parseErrorResponse(response: Response): Promise<ErrorResponse | undefined> {
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return undefined;
  }

  if (!isRecord(payload)) {
    return undefined;
  }

  return {
    detail: typeof payload.detail === "string" ? payload.detail : "",
    code: typeof payload.code === "string" ? payload.code : undefined,
    errors: Array.isArray(payload.errors)
      ? (payload.errors as ErrorDetail[])
      : undefined,
  };
}

async function toApiError(response: Response): Promise<ApiError> {
  const payload = await parseErrorResponse(response);

  return new ApiError({
    status: response.status,
    message: API_ERROR_KEYS.http,
    code: payload?.code,
    detail: payload?.detail || undefined,
    errors: payload?.errors,
  });
}

/**
 * Выполняет запрос и возвращает типизированное тело ответа.
 *
 * @throws {ApiError} при сетевом сбое, не-2xx статусе или некорректном JSON.
 */
export async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = "GET", body, query, signal } = options;

  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers:
        body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (cause) {
    throw new ApiError({
      status: 0,
      message: API_ERROR_KEYS.network,
      cause,
    });
  }

  if (!response.ok) {
    throw await toApiError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  try {
    return (await response.json()) as T;
  } catch (cause) {
    throw new ApiError({
      status: response.status,
      message: API_ERROR_KEYS.invalidResponse,
      cause,
    });
  }
}
