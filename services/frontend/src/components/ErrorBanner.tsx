import { useTranslation } from "react-i18next";

import type { ApiError } from "../api";
import { API_ERROR_KEYS } from "../api/constants";

export type ErrorBannerProps = {
  /**
   * Типизированная ошибка API или валидации (api/client.ts; api_contract.md,
   * раздел 3.8 `ErrorResponse`).
   */
  error: ApiError;
};

/**
 * Ключ i18n с безопасным следующим действием для ошибки.
 *
 * Категория выбирается по HTTP-статусу (api_contract.md, 3.8) и, когда он
 * есть, по машинному `code` ответа — так подсказка остаётся осмысленной даже
 * при одинаковых статусах. Текст не строится из сырых данных backend
 * (design.md, §7: пользователь видит объяснение, а не стек).
 */
export function apiErrorHintKey(error: ApiError): string {
  if (error.status === 0) {
    return "errorBanner.hints.network";
  }
  if (error.message === API_ERROR_KEYS.invalidResponse) {
    return "errorBanner.hints.invalidResponse";
  }

  switch (error.code) {
    case "rate_limited":
      return "errorBanner.hints.rateLimited";
    case "validation_error":
      return "errorBanner.hints.validation";
    case "bad_request":
      return "errorBanner.hints.badRequest";
    case "not_found":
      return "errorBanner.hints.notFound";
    case "internal_error":
    case "invariant_violation":
      return "errorBanner.hints.server";
    default:
      break;
  }

  if (error.status >= 500) {
    return "errorBanner.hints.server";
  }
  switch (error.status) {
    case 429:
      return "errorBanner.hints.rateLimited";
    case 422:
      return "errorBanner.hints.validation";
    case 400:
      return "errorBanner.hints.badRequest";
    case 404:
      return "errorBanner.hints.notFound";
    default:
      return "errorBanner.hints.generic";
  }
}

/**
 * Баннер ошибки (frontend.md, раздел 6.2 `ErrorBanner`; design.md, раздел 7).
 *
 * Показывает понятное сообщение (переведённый ключ `error.message`),
 * безопасное следующее действие (подсказка по категории ошибки) и, если
 * backend их предоставил, технические детали ошибки в разворачиваемой
 * диагностике: HTTP-статус, `detail` и список ошибок валидации. Сырой
 * stack trace не выводится (design.md, раздел 7). Регион `alert` оповещает
 * скринридер (design.md, раздел 11).
 */
export default function ErrorBanner({ error }: ErrorBannerProps) {
  const { t } = useTranslation();

  const hasDetails =
    error.status > 0 ||
    Boolean(error.detail) ||
    (error.errors !== undefined && error.errors.length > 0);

  return (
    <div className="error-banner" role="alert">
      <p className="error-banner__message">{t(error.message)}</p>
      <p className="error-banner__hint">{t(apiErrorHintKey(error))}</p>

      {hasDetails ? (
        <details className="error-banner__details">
          <summary className="error-banner__summary">
            {t("errorBanner.details")}
          </summary>

          {error.status > 0 ? (
            <p className="error-banner__detail">{`HTTP ${error.status}`}</p>
          ) : null}

          {error.detail ? (
            <p className="error-banner__detail">{error.detail}</p>
          ) : null}

          {error.errors && error.errors.length > 0 ? (
            <ul className="error-banner__list">
              {error.errors.map((item) => (
                <li key={`${item.loc.join(".")}:${item.msg}`}>
                  {`${item.loc.join(".")}: ${item.msg}`}
                </li>
              ))}
            </ul>
          ) : null}
        </details>
      ) : null}
    </div>
  );
}
