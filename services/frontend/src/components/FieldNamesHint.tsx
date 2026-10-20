import { useId } from "react";
import { useTranslation } from "react-i18next";

/**
 * Подсказка об именах полей, которые анализатор читает из файла.
 *
 * Всплывающее меню кастомное, а не нативный `title`: последний показывается
 * только после системной задержки. Здесь тултип открывается сразу при
 * наведении или фокусе (CSS `:hover`/`:focus-visible`, без `transition`).
 * Иконка — кнопка, доступная с клавиатуры; текст связан через
 * `aria-describedby`, поэтому подсказка не «только для мыши»
 * (a11y: design.md, §11). Имена полей приходят из перевода, не из кода.
 */
export default function FieldNamesHint() {
  const { t } = useTranslation();
  const tooltipId = useId();

  return (
    <span className="field-names-hint">
      <button
        type="button"
        className="field-names-hint__icon"
        aria-describedby={tooltipId}
        aria-label={t("fileUpload.fieldNamesHintLabel")}
      >
        ?
      </button>
      <span
        id={tooltipId}
        role="tooltip"
        className="field-names-hint__tooltip"
      >
        {t("fileUpload.fieldNamesHint")}
      </span>
    </span>
  );
}
