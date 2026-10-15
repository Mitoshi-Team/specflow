/**
 * Константы клиента API.
 *
 * Значения, используемые в нескольких местах, вынесены сюда, чтобы не
 * дублировать их в бизнес-логике.
 */

/** Базовый префикс публичного API (api_contract.md, раздел 2). */
export const API_PREFIX = "/api/v1";

/**
 * Ключи i18n для сообщений об ошибках клиента.
 * Клиент не формирует пользовательский текст сам — он отдаёт ключ,
 * который переводит UI-слой.
 */
export const API_ERROR_KEYS = {
  network: "api.errors.network",
  http: "api.errors.http",
  invalidResponse: "api.errors.invalidResponse",
} as const;
