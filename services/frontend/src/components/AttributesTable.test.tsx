// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "../i18n";
import type { AttributePrediction } from "../schemas/api";
import AttributesTable from "./AttributesTable";

afterEach(cleanup);

function attribute(
  overrides: Partial<AttributePrediction> = {},
): AttributePrediction {
  return {
    attribute_code: "brand",
    raw_value: "Bosch",
    normalized_value: "Bosch",
    confidence: 0.95,
    extraction_method: "rule",
    is_confirmed_in_text: true,
    ...overrides,
  };
}

describe("AttributesTable", () => {
  it("показывает заголовки колонок таблицы атрибутов", () => {
    render(<AttributesTable attributes={[attribute()]} />);

    expect(screen.getByText("Атрибут")).toBeDefined();
    expect(screen.getByText("Значение")).toBeDefined();
    expect(screen.getByText("Уверенность")).toBeDefined();
    expect(screen.getByText("Метод")).toBeDefined();
    expect(screen.getByText("Подтверждение")).toBeDefined();
  });

  it("показывает строку на каждый атрибут", () => {
    render(
      <AttributesTable
        attributes={[
          attribute({ attribute_code: "brand", normalized_value: "Bosch" }),
          attribute({
            attribute_code: "color",
            normalized_value: "чёрный",
            extraction_method: "dict",
          }),
        ]}
      />,
    );

    expect(screen.getByText("brand")).toBeDefined();
    expect(screen.getByText("Bosch")).toBeDefined();
    expect(screen.getByText("color")).toBeDefined();
    expect(screen.getByText("чёрный")).toBeDefined();
    expect(screen.getByText("dict")).toBeDefined();
  });

  it("показывает пустое состояние без атрибутов", () => {
    render(<AttributesTable attributes={[]} />);

    expect(screen.getByText("Атрибуты не извлечены")).toBeDefined();
  });

  it("передаёт порог в строки атрибутов", () => {
    render(
      <AttributesTable
        attributes={[attribute({ confidence: 0.5 })]}
        threshold={0.8}
      />,
    );

    expect(screen.getByText("ниже порога")).toBeDefined();
  });
});
