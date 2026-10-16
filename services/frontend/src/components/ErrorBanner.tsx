import { useTranslation } from "react-i18next";

import type { ApiError } from "../api";

export type ErrorBannerProps = {
  /**
   * Типизированная ошибка API или валидации (api/client.ts; api_contract.md,
   * раздел 3.8 `ErrorResponse`).
   */
  error: ApiError;
};

/**
 * Баннер ошибки (frontend.md, раздел 6.2 `ErrorBanner`; design.md, раздел 7).
 *
 * Показывает понятное сообщение (переведённый ключ `error.message`) и, если
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
