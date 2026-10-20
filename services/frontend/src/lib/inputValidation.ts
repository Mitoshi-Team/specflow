/**
 * Валидация входных карточек.
 *
 * Чистый модуль без React (frontend.md, 6.3; api_contract.md, 3.1). Результат
 * типизирован и не содержит пользовательского текста: код ошибки переводится
 * UI-слоем через i18n.
 */

import type { ProductCardRequest } from "../schemas/api";

/** Поля карточки, участвующие в проверке предпросмотра. */
export type PreviewField = "title" | "description";

/**
 * Непусто ли поле карточки. Пустая строка и пустой объект атрибутов
 * считаются отсутствием значения (frontend.md, 6.3 — «непустое»).
 */
export function isFieldPresent(
  card: ProductCardRequest,
  field: PreviewField,
): boolean {
  const value = card[field];
  return typeof value === "string" && value.trim() !== "";
}

/**
 * Есть ли хотя бы одна карточка без описания: предпросмотр показывает
 * предупреждение только в этом случае (заголовок не обязателен).
 */
export function hasMissingDescription(cards: ProductCardRequest[]): boolean {
  return cards.some((card) => !isFieldPresent(card, "description"));
}
