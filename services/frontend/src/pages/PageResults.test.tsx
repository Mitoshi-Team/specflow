// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "../i18n";
import type { BatchExtractResponse } from "../schemas/api";
import PageResults from "./PageResults";
import type { ResultsLocationState } from "./PageResults";

afterEach(cleanup);

function batchResponse(): BatchExtractResponse {
  return {
    total: 1,
    ok: 1,
    low_confidence: 0,
    errors: 0,
    results: [
      {
        product_id: "sku-1",
        attributes: [],
        status: "ok",
        needs_review: false,
        pipeline_version: "1.0.0",
      },
    ],
  };
}

function renderPage(state?: ResultsLocationState) {
  render(
    <MemoryRouter initialEntries={[{ pathname: "/results", state }]}>
      <PageResults />
    </MemoryRouter>,
  );
}

describe("PageResults", () => {
  it("без данных батча показывает пустое состояние", () => {
    renderPage();

    expect(
      screen.getByText("Результаты появятся после запуска обработки."),
    ).toBeDefined();
    expect(screen.queryByText("Как читать результаты")).toBeNull();
  });

  it("показывает сводку, легенду статусов и таблицу результатов", () => {
    renderPage({
      response: batchResponse(),
      threshold: 0.8,
      cards: [{ title: "Кофемолка" }],
    });

    expect(screen.getByText("Сводка батча")).toBeDefined();
    expect(screen.getByText("Как читать результаты")).toBeDefined();
    expect(screen.getByText("sku-1")).toBeDefined();
    expect(
      screen.getByRole("button", {
        name: "Экспорт результатов в формате CSV",
      }),
    ).toBeDefined();
  });

  it("передаёт порог в пояснение низкоуверенных значений", () => {
    renderPage({ response: batchResponse(), threshold: 0.8 });

    expect(screen.getByText(/Порог уверенности батча: 0\.8/)).toBeDefined();
  });
});
