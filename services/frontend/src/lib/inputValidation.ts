/**
 * Валидация входных карточек: наличие обязательного контента
 * (хотя бы одно непустое из `title | description | seller_attributes`).
 *
 * Чистый модуль без React (frontend.md, 6.3; api_contract.md, 3.1). Результат
 * типизирован и не содержит пользовательского текста: код ошибки переводится
 * UI-слоем через i18n.
 */

import type { ProductCardRequest } from "../schemas/api";

/** Поля карточки, хотя бы одно из которых должно быть непустым. */
export type RequiredInputField = "title" | "description" | "seller_attributes";

export const REQUIRED_INPUT_FIELDS: readonly RequiredInputField[] = [
  "title",
  "description",
  "seller_attributes",
];

/** Коды ошибок валидации входных данных (UI переводит их через i18n). */
export type InputValidationErrorCode = "noContent";

export type InputValidationError = { code: InputValidationErrorCode };

export type InputValidationResult = {
  /** Истинно, если присутствует хотя бы одно обязательное поле. */
  valid: boolean;
  /** Обязательные поля, непустые хотя бы в одной карточке. */
  presentFields: RequiredInputField[];
  /** Обязательные поля, непустые ни в одной карточке. */
  missingFields: RequiredInputField[];
  /** Ошибки валидации; пусто, если `valid`. */
  errors: InputValidationError[];
};

/**
 * Непусто ли поле карточки. Пустая строка и пустой объект атрибутов
 * считаются отсутствием значения (frontend.md, 6.3 — «непустое»).
 */
export function isFieldPresent(
  card: ProductCardRequest,
  field: RequiredInputField,
): boolean {
  switch (field) {
    case "title":
      return typeof card.title === "string" && card.title.trim() !== "";
    case "description":
      return typeof card.description === "string" && card.description.trim() !== "";
    case "seller_attributes":
      return (
        card.seller_attributes !== undefined &&
        Object.keys(card.seller_attributes).length > 0
      );
  }
}

/** Минимум одно непустое из `title | description | seller_attributes`. */
export function hasRequiredContent(card: ProductCardRequest): boolean {
  return REQUIRED_INPUT_FIELDS.some((field) => isFieldPresent(card, field));
}

/**
 * Проверяет разобранные карточки: какие обязательные поля присутствуют,
 * каких не хватает, и валиден ли набор в целом. Набор валиден, если хотя бы
 * одно из полей title/description/seller_attributes непусто (api_contract.md,
 * 3.1).
 */
export function validateInput(
  cards: ProductCardRequest[],
): InputValidationResult {
  const presentFields = REQUIRED_INPUT_FIELDS.filter((field) =>
    cards.some((card) => isFieldPresent(card, field)),
  );
  const missingFields = REQUIRED_INPUT_FIELDS.filter(
    (field) => !presentFields.includes(field),
  );
  const valid = presentFields.length > 0;

  return {
    valid,
    presentFields,
    missingFields,
    errors: valid ? [] : [{ code: "noContent" }],
  };
}
