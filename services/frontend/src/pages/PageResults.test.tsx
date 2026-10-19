// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "../i18n";
import { clearLastBatch, writeLastBatch } from "../lib/lastBatch";
import type { StoredBatch } from "../lib/lastBatch";
import type { BatchExtractResponse } from "../schemas/api";
import PageResults from "./PageResults";

afterEach(() => {
  cleanup();
  clearLastBatch();
});

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

function renderPage(batch?: StoredBatch) {
  if (batch !== undefined) {
    writeLastBatch(batch);
  }
  render(
    <MemoryRouter initialEntries={["/results"]}>
      <PageResults />
    </MemoryRouter>,
  );
}

describe("PageResults", () => {
  it("без сохранённого батча показывает пустое состояние", () => {
    renderPage();

    expect(
      screen.getByText("Результаты появятся после запуска обработки."),
    ).toBeDefined();
    expect(screen.queryByText("Как читать результаты")).toBeNull();
  });

  it("показывает сохранённый батч, легенду статусов и таблицу результатов", () => {
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

  it("не теряет результаты при переходе между страницами", async () => {
    writeLastBatch({ response: batchResponse() });
    render(
      <MemoryRouter initialEntries={["/"]}>
        <Link to="/">Домой</Link>
        <Link to="/results">Результаты</Link>
        <Routes>
          <Route path="/" element={<div>Главная</div>} />
          <Route path="/results" element={<PageResults />} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("link", { name: "Результаты" }));
    expect(await screen.findByText("sku-1")).toBeDefined();

    fireEvent.click(screen.getByRole("link", { name: "Домой" }));
    fireEvent.click(screen.getByRole("link", { name: "Результаты" }));

    expect(await screen.findByText("sku-1")).toBeDefined();
  });
});
