import { useId } from "react";
import { useTranslation } from "react-i18next";

/** Способ загрузки карточек: файлом либо текстом одной карточки. */
export type InputMode = "file" | "text";

/** Порядок опций отображения и порядок навигации стрелками. */
const MODES: readonly InputMode[] = ["file", "text"];

export type InputModeSwitchProps = {
  value: InputMode;
  onChange: (mode: InputMode) => void;
  /** Блокирует переключение (например, во время обработки). */
  disabled?: boolean;
};

/**
 * Переключатель способа загрузки: файл (CSV/JSON/TSV) или текстовое поле
 * с описанием одной карточки. Оба способа дают один и тот же результат —
 * список `ProductCardRequest` для предпросмотра и дальнейшей обработки
 * (frontend.md, сценарий 1; design.md, раздел 6, область «Загрузка»).
 *
 * Используются нативные radio-кнопки внутри `fieldset`: группировка,
 * переключение стрелками и озвучивание имени группы доступны без
 * дополнительного ARIA. Визуально это сегментный контрол из `index.css`.
 */
export default function InputModeSwitch({
  value,
  onChange,
  disabled = false,
}: InputModeSwitchProps) {
  const { t } = useTranslation();
  const groupId = useId();

  return (
    <fieldset className="mode-switch">
      <legend className="sr-only">{t("upload.mode.label")}</legend>
      {MODES.map((mode) => {
        const inputId = `${groupId}-${mode}`;
        return (
          <span className="mode-switch__option" key={mode}>
            <input
              className="mode-switch__input"
              type="radio"
              id={inputId}
              name={`${groupId}-mode`}
              value={mode}
              checked={value === mode}
              disabled={disabled}
              onChange={() => onChange(mode)}
            />
            <label className="mode-switch__label" htmlFor={inputId}>
              {t(`upload.mode.${mode}`)}
            </label>
          </span>
        );
      })}
    </fieldset>
  );
}
