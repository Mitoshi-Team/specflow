import { useTranslation } from "react-i18next";

export type ConfidenceBadgeProps = {
  /** Уверенность атрибута, `confidence` ∈ [0.0, 1.0] (api_contract.md, 3.2). */
  confidence: number;
  /**
   * Порог уверенности, использованный в батче. Задаёт вызывающий код (значение
   * `threshold_override` или дефолтный порог); компонент не вводит собственных
   * порогов (design.md, §8: пороги определяет backend/продуктовая логика).
   */
  threshold?: number;
};

/**
 * Бейдж уверенности (frontend.md, 6.2 `ConfidenceBadge`; design.md, §8).
 *
 * Числовое значение показывается всегда. При заданном пороге значение ниже
 * порога получает нейтральную подсветку и видимую текстовую пометку «ниже
 * порога»: смысл не кодируется только цветом (design.md, §8, §11). Пометка
 * видима, а не только для скринридера, чтобы объяснение было доступно всем.
 * Низкая уверенность не помечается красным — это повод для проверки, а не
 * ошибка (design.md, §8).
 */
export default function ConfidenceBadge({
  confidence,
  threshold,
}: ConfidenceBadgeProps) {
  const { t } = useTranslation();
  const isLow = threshold !== undefined && confidence < threshold;

  return (
    <span className={`confidence${isLow ? " confidence--low" : ""}`}>
      {confidence}
      {isLow ? (
        <span className="confidence__note">
          {" "}
          {t("results.table.attributes.confidenceLow")}
        </span>
      ) : null}
    </span>
  );
}
