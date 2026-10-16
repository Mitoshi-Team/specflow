import type { ExtractionMethod } from "../schemas/api";

export type MethodBadgeProps = {
  /**
   * Метод извлечения. Набор значений задан контрактом
   * (api_contract.md, 3.2; schemas/api.ts `ExtractionMethod`).
   */
  method: ExtractionMethod;
};

/**
 * Бейдж метода извлечения (frontend.md, 6.2 `MethodBadge`; design.md, §7, §9).
 *
 * Значение метода — техническое, поэтому показывается моноширинно как есть
 * (design.md, §9). Внешний вид бейджа переиспользует нейтральную базу
 * `.status` (design.md, §8: нейтральная серо-светлая маркировка), модификатор
 * `.method-badge` добавляет только моноширинный шрифт.
 */
export default function MethodBadge({ method }: MethodBadgeProps) {
  return <span className="status method-badge">{method}</span>;
}
