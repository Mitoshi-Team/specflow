// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "../i18n";
import type {
  AttributePrediction,
  ExtractionResponseItem,
} from "../schemas/api";
import ResultsTable from "./ResultsTable";

afterEach(cleanup);

function item(
  overrides: Partial<ExtractionResponseItem> = {},
): ExtractionResponseItem {
  return {
    product_id: "sku-1",
    attributes: [],
    status: "ok",
    needs_review: false,
    pipeline_version: "1.0.0",
    ...overrides,
  };
}

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

describe("ResultsTable", () => {
  it("показывает строку карточки с ключевыми полями", () => {
    render(
      <ResultsTable
        results={[
          item({
            product_id: "sku-7",
            category_name: "Кофемолки",
            status: "partial",
            needs_review: true,
            low_confidence_count: 2,
            processing_time_ms: 12,
          }),
        ]}
      />,
    );

    expect(screen.getByText("sku-7")).toBeDefined();
    expect(screen.getByText("Кофемолки")).toBeDefined();
    expect(screen.getByText("Частично")).toBeDefined();
    expect(screen.getByText("Требует проверки")).toBeDefined();
    expect(screen.getByText("2")).toBeDefined();
    expect(screen.getByText("12")).toBeDefined();
  });

  it("использует category_id, когда нет названия категории", () => {
    render(<ResultsTable results={[item({ category_id: "cat-1" })]} />);

    expect(screen.getByText("cat-1")).toBeDefined();
  });

  it("помечает отсутствующие значения знаком пустой ячейки", () => {
    render(<ResultsTable results={[item({ product_id: undefined })]} />);

    // product_id, needs_review, low_confidence_count и processing_time_ms
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(4);
  });

  it("показывает статус ошибки текстом", () => {
    render(<ResultsTable results={[item({ status: "error" })]} />);

    expect(screen.getByText("Ошибка")).toBeDefined();
  });

  it("показывает пустое состояние при отсутствии результатов", () => {
    render(<ResultsTable results={[]} />);

    expect(screen.getByRole("status").textContent).toBe(
      "Нет результатов для отображения",
    );
  });

  it("скрывает атрибуты до раскрытия карточки", () => {
    render(
      <ResultsTable results={[item({ attributes: [attribute()] })]} />,
    );

    expect(screen.queryByText("brand")).toBeNull();
    expect(
      screen.getByRole("button", { name: "Показать атрибуты" }),
    ).toBeDefined();
  });

  it("раскрывает атрибуты карточки с уверенностью, методом и подтверждением", () => {
    render(
      <ResultsTable
        results={[
          item({
            attributes: [
              attribute({
                evidence_text: "Подтверждение из карточки",
                source_spans: [
                  { field: "title", text: "фрагмент", start: 0, end: 13 },
                ],
              }),
            ],
          }),
        ]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Показать атрибуты" }));

    expect(screen.getByText("brand")).toBeDefined();
    expect(screen.getByText("Bosch")).toBeDefined();
    expect(screen.getByText("0.95")).toBeDefined();
    expect(screen.getByText("rule")).toBeDefined();
    expect(screen.getByText("Подтверждение из карточки")).toBeDefined();
    expect(screen.getByText(/title: фрагмент \[0–13\]/)).toBeDefined();
    expect(screen.getByText("Подтверждено в тексте")).toBeDefined();
  });

  it("сворачивает атрибуты повторным действием", () => {
    render(<ResultsTable results={[item({ attributes: [attribute()] })]} />);

    fireEvent.click(screen.getByRole("button", { name: "Показать атрибуты" }));
    fireEvent.click(screen.getByRole("button", { name: "Свернуть атрибуты" }));

    expect(screen.queryByText("brand")).toBeNull();
  });

  it("явно помечает отсутствующее подтверждение", () => {
    render(
      <ResultsTable results={[item({ attributes: [attribute()] })]} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Показать атрибуты" }));

    expect(screen.getByText("Подтверждение не найдено")).toBeDefined();
  });

  it("сообщает, что атрибуты не извлечены", () => {
    render(<ResultsTable results={[item({ attributes: [] })]} />);

    fireEvent.click(screen.getByRole("button", { name: "Показать атрибуты" }));

    expect(screen.getByText("Атрибуты не извлечены")).toBeDefined();
  });

  it("подсвечивает уверенность ниже заданного порога текстом", () => {
    render(
      <ResultsTable
        threshold={0.8}
        results={[item({ attributes: [attribute({ confidence: 0.5 })] })]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Показать атрибуты" }));

    expect(screen.getByText("ниже порога")).toBeDefined();
  });

  it("не подсвечивает уверенность не ниже порога", () => {
    render(
      <ResultsTable
        threshold={0.8}
        results={[item({ attributes: [attribute({ confidence: 0.9 })] })]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Показать атрибуты" }));

    expect(screen.queryByText("ниже порога")).toBeNull();
  });
});
