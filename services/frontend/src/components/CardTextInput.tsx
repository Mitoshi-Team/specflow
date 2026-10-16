import { useId, useLayoutEffect, useRef } from "react";
import type { ChangeEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  CARD_TEXT_MAX_HEIGHT_PX,
  CARD_TEXT_MIN_HEIGHT_PX,
} from "../constants";

export type CardTextInputProps = {
  /** Текст описания одной карточки (управляемое поле). */
  value: string;
  /** Блокирует ввод (например, во время обработки). */
  disabled?: boolean;
  onChange: (value: string) => void;
  /** Показывается, когда есть что сбрасывать. */
  onClear?: () => void;
};

/**
 * Ввод описания одной карточки в текстовое поле — второй способ загрузки
 * наравне с выбором файла (PageHome).
 *
 * Компонент ничего не валидирует сам: непустой после обрезки пробелов
 * текст — это готовая карточка с полем `description` (frontend.md, 6.3:
 * минимум одно непустое из title/description/seller_attributes), пустой —
 * состояние ожидания. Состояние отражается текстом в `role="status"`,
 * цветом компонент не дублируется (design.md, раздел 8).
 *
 * Высота поля растёт по числу строк и ограничена сверху
 * `CARD_TEXT_MAX_HEIGHT_PX` (дальше — внутренний скролл); ручное
 * растягивание за угол отключено (`resize: none`).
 */
export default function CardTextInput({
  value,
  disabled = false,
  onChange,
  onClear,
}: CardTextInputProps) {
  const { t } = useTranslation();
  const inputId = useId();
  const hintId = `${inputId}-hint`;
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // `useLayoutEffect` — чтобы высота пересчитывалась до отрисовки и поле
  // не «прыгало» между кадрами. Сначала сбрасываем высоту в auto, иначе
  // `scrollHeight` вернёт текущую (уже увеличенную) высоту.
  useLayoutEffect(() => {
    const textarea = textareaRef.current;
    if (textarea === null) {
      return;
    }
    textarea.style.height = "auto";
    const contentHeight = Math.max(
      textarea.scrollHeight,
      CARD_TEXT_MIN_HEIGHT_PX,
    );
    textarea.style.height = `${Math.min(
      contentHeight,
      CARD_TEXT_MAX_HEIGHT_PX,
    )}px`;
  }, [value]);

  const hasText = value.trim() !== "";
  const statusText = hasText ? t("textInput.ready") : t("textInput.idle");
  const showClear = onClear !== undefined && hasText;

  const handleInputChange = (event: ChangeEvent<HTMLTextAreaElement>): void => {
    onChange(event.target.value);
  };

  return (
    <div
      className={`card-text ${hasText ? "card-text--ready" : "card-text--idle"}`}
    >
      <label className="card-text__label" htmlFor={inputId}>
        {t("textInput.label")}
      </label>
      <textarea
        id={inputId}
        ref={textareaRef}
        className="card-text__textarea"
        value={value}
        disabled={disabled}
        placeholder={t("textInput.placeholder")}
        aria-describedby={hintId}
        onChange={handleInputChange}
      />
      <p className="card-text__status" role="status">
        {statusText}
      </p>
      <p className="card-text__hint" id={hintId}>
        {t("textInput.hint")}
      </p>
      {showClear ? (
        <button
          type="button"
          className="btn btn--secondary card-text__clear"
          onClick={onClear}
        >
          {t("textInput.clear")}
        </button>
      ) : null}
    </div>
  );
}
