// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "../i18n";
import type {
  BatchExtractResponse,
  ExtractionResponseItem,
} from "../schemas/api";
import ResultsSummary from "./ResultsSummary";

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

function response(
  overrides: Partial<BatchExtractResponse> = {},
): BatchExtractResponse {
  return {
    total: 3,
    ok: 2,
    low_confidence: 1,
    errors: 0,
    results: [],
    ...overrides,
  };
}

/** Значение метрики сводки по подписи её термина. */
function metricValue(label: string): string {
  const term = screen.getByText(label);
  return term.parentElement?.querySelector("dd")?.textContent ?? "";
}

describe("ResultsSummary", () => {
  it("показывает счётчики батча из ответа", () => {
    render(
      <ResultsSummary
        response={response({ total: 5, ok: 3, low_confidence: 1, errors: 1 })}
      />,
    );

    expect(metricValue("Обработано карточек")).toBe("5");
    expect(metricValue("Успешно")).toBe("3");
    expect(metricValue("Низкая уверенность")).toBe("1");
    expect(metricValue("Ошибки")).toBe("1");
  });

  it("считает число записей, требующих проверки", () => {
    render(
      <ResultsSummary
        response={response({
          results: [
            item({ needs_review: true }),
            item({ needs_review: true }),
            item({ needs_review: false }),
          ],
        })}
      />,
    );

    expect(metricValue("Требуют проверки")).toBe("2");
  });

  it("не показывает метаданные, если они не переданы", () => {
    const { container } = render(<ResultsSummary response={response()} />);

    expect(screen.queryByText("Батч")).toBeNull();
    expect(screen.queryByText("Версия пайплайна")).toBeNull();
    expect(screen.queryByText("Время обработки, мс")).toBeNull();
    expect(container.querySelector(".results-summary__meta")).toBeNull();
  });

  it("показывает метаданные батча: batch_id, версию пайплайна и время", () => {
    render(
      <ResultsSummary
        response={response({
          batch_id: "batch-42",
          processing_time_ms_total: 456,
          results: [item({ pipeline_version: "1.2.0" })],
        })}
      />,
    );

    expect(screen.getByText("batch-42")).toBeDefined();
    expect(screen.getByText("1.2.0")).toBeDefined();
    expect(screen.getByText("456")).toBeDefined();
  });

  it("не дублирует одинаковую версию пайплайна", () => {
    render(
      <ResultsSummary
        response={response({
          results: [
            item({ pipeline_version: "2.0.0" }),
            item({ pipeline_version: "2.0.0" }),
          ],
        })}
      />,
    );

    expect(screen.getByText("2.0.0")).toBeDefined();
  });

  it("показывает сводку при пустом списке результатов", () => {
    render(<ResultsSummary response={response({ results: [] })} />);

    expect(metricValue("Требуют проверки")).toBe("0");
    expect(screen.getByText("Обработано карточек")).toBeDefined();
  });
});
