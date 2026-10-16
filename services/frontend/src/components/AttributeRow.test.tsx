// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "../i18n";
import type { AttributePrediction } from "../schemas/api";
import AttributeRow from "./AttributeRow";

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

/** `AttributeRow` рендерит `<tr>`, поэтому его нужно поместить в таблицу. */
function renderRow(props: Parameters<typeof AttributeRow>[0]) {
  return render(
    <table>
      <tbody>
        <AttributeRow {...props} />
      </tbody>
    </table>,
  );
}

describe("AttributeRow", () => {
  it("показывает значение, уверенность и метод", () => {
    renderRow({ attribute: attribute() });

    expect(screen.getByText("brand")).toBeDefined();
    expect(screen.getByText("Bosch")).toBeDefined();
    expect(screen.getByText("0.95")).toBeDefined();
    expect(screen.getByText("rule")).toBeDefined();
  });

  it("показывает подтверждающий фрагмент и подтверждение в тексте", () => {
    renderRow({
      attribute: attribute({ evidence_text: "Подтверждение из карточки" }),
    });

    expect(screen.getByText("Подтверждение из карточки")).toBeDefined();
    expect(screen.getByText("Подтверждено в тексте")).toBeDefined();
  });

  it("показывает source_spans как field: text [start–end]", () => {
    renderRow({
      attribute: attribute({
        source_spans: [
          { field: "title", text: "Bosch", start: 0, end: 5 },
        ],
      }),
    });

    expect(screen.getByText("title: Bosch [0–5]")).toBeDefined();
  });

  it("показывает source_spans без смещений, если они не заданы", () => {
    renderRow({
      attribute: attribute({
        source_spans: [{ field: "description", text: "чёрный" }],
      }),
    });

    expect(screen.getByText("description: чёрный")).toBeDefined();
  });

  it("явно помечает отсутствие подтверждающего фрагмента", () => {
    renderRow({ attribute: attribute({ evidence_text: undefined }) });

    expect(screen.getByText("Подтверждение не найдено")).toBeDefined();
  });

  it("явно помечает неподтверждённое значение", () => {
    const { container } = renderRow({
      attribute: attribute({ is_confirmed_in_text: false }),
    });

    expect(screen.getByText("Не подтверждено в тексте")).toBeDefined();
    expect(
      container.querySelector(".results-table__confirmed--no"),
    ).not.toBeNull();
  });

  it("передаёт порог в бейдж уверенности", () => {
    renderRow({ attribute: attribute({ confidence: 0.5 }), threshold: 0.8 });

    expect(screen.getByText("ниже порога")).toBeDefined();
  });

  it("не показывает список источников, если source_spans отсутствуют", () => {
    const { container } = renderRow({ attribute: attribute() });

    expect(container.querySelector(".results-table__spans")).toBeNull();
  });
});
