// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "../i18n";
import { clearLastBatch, writeLastBatch } from "../lib/lastBatch";
import type { StoredBatch } from "../lib/lastBatch";
import type {
  BatchExtractResponse,
  BatchSummary,
  StoredBatchResponse,
} from "../schemas/api";
import PageResults from "./PageResults";

const fetchMock = vi.fn();

/** Ответ истории по умолчанию: пусто, но успешно — страница не падает без сети. */
const EMPTY_HISTORY = { items: [], total: 0 };

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockResolvedValue(jsonResponse(EMPTY_HISTORY));
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  cleanup();
  clearLastBatch();
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Путь запроса без query-строки — для маршрутизации по эндпоинту. */
function pathOf(url: string): string {
  return url.split("?")[0] ?? url;
}

/** Маршрутизация заглушки fetch по путям: `{путь: {status, body}}`. */
function mockRoutes(
  routes: Record<string, { status: number; body: unknown }>,
): void {
  fetchMock.mockImplementation((url: string) => {
    const route = routes[pathOf(String(url))];
    if (route === undefined) {
      return Promise.reject(new Error(`неожиданный запрос: ${String(url)}`));
    }
    return Promise.resolve(jsonResponse(route.body, route.status));
  });
}

function batchResponse(
  overrides: Partial<BatchExtractResponse> = {},
): BatchExtractResponse {
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
    ...overrides,
  };
}

function summary(batchId: string, total: number, ok: number): BatchSummary {
  return {
    batch_id: batchId,
    created_at: "2026-10-20T12:00:00Z",
    total,
    ok,
    low_confidence: total - ok,
    errors: 0,
    threshold: null,
  };
}

/** Страница истории: `count` батчей начиная с `from`, общий `total`. */
function historyPage(from: number, count: number, total: number) {
  return {
    items: Array.from({ length: count }, (_, i) =>
      summary(`b-${from + i}`, 1, 1),
    ),
    total,
  };
}

function storedBatchBody(
  batchId: string,
  productId: string,
): StoredBatchResponse {
  return {
    batch_id: batchId,
    created_at: "2026-10-20T12:00:00Z",
    threshold: null,
    cards: [{ title: "Кофемолка" }],
    response: batchResponse({
      results: [
        {
          product_id: productId,
          attributes: [],
          status: "ok",
          needs_review: false,
          pipeline_version: "1.0.0",
        },
      ],
      persisted: true,
    }),
  };
}

function renderPage(batch?: StoredBatch, initialEntry = "/results") {
  if (batch !== undefined) {
    writeLastBatch(batch);
  }
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <PageResults />
    </MemoryRouter>,
  );
}

describe("PageResults", () => {
  it("без сохранённого батча показывает пустое состояние", async () => {
    renderPage();

    expect(
      screen.getByText("Результаты появятся после запуска обработки."),
    ).toBeDefined();
    expect(screen.queryByText("Как читать результаты")).toBeNull();
    expect(
      await screen.findByText(
        "Сохранённых батчей пока нет — запустите обработку на главной странице.",
      ),
    ).toBeDefined();
  });

  it("показывает сохранённый батч, легенду статусов и таблицу результатов", () => {
    renderPage({
      response: batchResponse(),
      threshold: 0.8,
      cards: [{ title: "Кофемолка" }],
    });

    expect(screen.getByText("Сводка батча")).toBeDefined();
    const legendToggle = screen.getByRole("button", {
      name: "Как читать результаты",
    });
    expect(legendToggle).toBeDefined();
    expect(legendToggle.getAttribute("aria-expanded")).toBe("false");
    expect(screen.getByText("sku-1")).toBeDefined();
    expect(
      screen.getByRole("button", {
        name: "Экспорт результатов в формате CSV",
      }),
    ).toBeDefined();
  });

  it("передаёт порог в пояснение низкоуверенных значений", () => {
    renderPage({ response: batchResponse(), threshold: 0.8 });

    // Легенда свёрнута по умолчанию — раскрываем её кликом по заголовку.
    fireEvent.click(
      screen.getByRole("button", { name: "Как читать результаты" }),
    );

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

  it("показывает историю батчей с сервера и открывает батч по ссылке", async () => {
    mockRoutes({
      "/api/v1/batches/b-2": { status: 200, body: storedBatchBody("b-2", "sku-server-2") },
      "/api/v1/batches": {
        status: 200,
        body: { items: [summary("b-2", 2, 1), summary("b-1", 3, 3)], total: 2 },
      },
    });
    renderPage();

    expect(await screen.findByText("Показано 2 батча из 2")).toBeDefined();
    const historyRow = await screen.findByRole("link", {
      name: /2 карточек · ok 1/,
    });

    fireEvent.click(historyRow);

    // Серверная копия батча подгружена по ссылке из истории.
    expect(await screen.findByText("sku-server-2")).toBeDefined();
    expect(
      fetchMock.mock.calls.some(
        ([url]) => pathOf(String(url)) === "/api/v1/batches/b-2",
      ),
    ).toBe(true);
  });

  it("пагинирует историю: 10 последних, «Показать ещё» догружает следующие", async () => {
    fetchMock.mockImplementation((url: string) => {
      const target = String(url);
      if (pathOf(target) !== "/api/v1/batches") {
        return Promise.reject(new Error(`неожиданный запрос: ${target}`));
      }
      return Promise.resolve(
        jsonResponse(target.includes("offset=10") ? historyPage(10, 10, 25) : historyPage(0, 10, 25)),
      );
    });
    renderPage();

    // Первая порция: показано 10 из 25, кнопка догрузки видна.
    expect(await screen.findByText("Показано 10 батчей из 25")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Показать ещё" }));

    expect(await screen.findByText("Показано 20 батчей из 25")).toBeDefined();
    // Запрос догрузки ушёл со сдвинутым offset…
    expect(
      fetchMock.mock.calls.some(([url]) => String(url).includes("offset=10")),
    ).toBe(true);
    // …а новая порция добавлена к прежней, а не заменила её.
    expect(
      screen.getAllByRole("link", { name: /карточек · ok/ }).length,
    ).toBe(20);
    expect(
      (screen.getByRole("button", { name: "Показать ещё" }) as HTMLButtonElement)
        .disabled,
    ).toBe(false);
  });

  it("скрывает «Показать ещё», когда история показана целиком", async () => {
    mockRoutes({
      "/api/v1/batches": { status: 200, body: historyPage(0, 3, 3) },
    });
    renderPage();

    // Множественное число склоняется по числу показанных батчей.
    expect(await screen.findByText("Показано 3 батча из 3")).toBeDefined();
    expect(screen.queryByRole("button", { name: "Показать ещё" })).toBeNull();
  });

  it("показывает ошибку догрузки и не теряет уже загруженные батчи", async () => {
    let call = 0;
    fetchMock.mockImplementation(() => {
      call += 1;
      if (call > 1) {
        return Promise.reject(new TypeError("network down"));
      }
      return Promise.resolve(
        jsonResponse(historyPage(0, 10, 25)),
      );
    });
    renderPage();

    expect(await screen.findByText("Показано 10 батчей из 25")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Показать ещё" }));

    expect(
      await screen.findByText(
        "Проверьте соединение с сервером и попробуйте ещё раз.",
      ),
    ).toBeDefined();
    // Уже загруженные батчи не пропали, кнопка доступна для повтора.
    expect(screen.getByText("Показано 10 батчей из 25")).toBeDefined();
    expect(
      (screen.getByRole("button", { name: "Показать ещё" }) as HTMLButtonElement)
        .disabled,
    ).toBe(false);
  });

  it("загружает батч с сервера по batch_id в адресной строке", async () => {
    mockRoutes({
      "/api/v1/batches/b-9": { status: 200, body: storedBatchBody("b-9", "sku-server-9") },
      "/api/v1/batches": { status: 200, body: EMPTY_HISTORY },
    });
    renderPage(undefined, "/results?batch_id=b-9");

    expect(await screen.findByText("sku-server-9")).toBeDefined();
    // Локальной копии нет — предупреждений о фолбэке не должно быть.
    expect(screen.queryByText(/Локальное хранилище/)).toBeNull();
    expect(screen.queryByText(/Сервер не сохранил этот батч/)).toBeNull();
  });

  it("предупреждает о недоступности истории и показывает локальный фолбэк", async () => {
    mockRoutes({
      "/api/v1/batches/missing": {
        status: 404,
        body: { detail: "batch not found: missing", code: "not_found" },
      },
      "/api/v1/batches": { status: 200, body: EMPTY_HISTORY },
    });
    renderPage({ response: batchResponse() }, "/results?batch_id=missing");

    // Батч не найден на сервере → ErrorBanner с подсказкой «не найден»…
    expect(
      await screen.findByText(
        "Запрошенный ресурс не найден. Обновите страницу и попробуйте снова.",
      ),
    ).toBeDefined();
    // …а результаты взяты из локальной копии.
    expect(screen.getByText("sku-1")).toBeDefined();
  });

  it("предупреждает, если батч не сохранён в серверной истории", () => {
    renderPage({ response: batchResponse({ persisted: false }) });

    expect(
      screen.getByText(/Сервер не сохранил этот батч в истории/),
    ).toBeDefined();
    expect(screen.getByText("sku-1")).toBeDefined();
  });

  it("показывает батч из state маршрута с предупреждением о локальной копии", async () => {
    // localStorage недоступен/пуст — батч приходит через state (PageHome).
    render(
      <MemoryRouter initialEntries={["/"]}>
        <Link
          to="/results"
          state={{ batch: { response: batchResponse() } satisfies StoredBatch }}
        >
          Результаты
        </Link>
        <Routes>
          <Route path="/" element={<div>Главная</div>} />
          <Route path="/results" element={<PageResults />} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("link", { name: "Результаты" }));

    expect(await screen.findByText("sku-1")).toBeDefined();
    expect(
      await screen.findByText(/Локальное хранилище браузера недоступно/),
    ).toBeDefined();
  });

  it("показывает ошибку недоступности истории и позволяет повторить", async () => {
    fetchMock.mockRejectedValue(new TypeError("network down"));
    renderPage();

    expect(
      await screen.findByText(
        "Проверьте соединение с сервером и попробуйте ещё раз.",
      ),
    ).toBeDefined();

    // Повтор: сеть восстановилась — история догружается кнопкой «Повторить».
    fetchMock.mockResolvedValue(jsonResponse(EMPTY_HISTORY));
    fireEvent.click(screen.getByRole("button", { name: "Повторить" }));

    expect(
      await screen.findByText(
        "Сохранённых батчей пока нет — запустите обработку на главной странице.",
      ),
    ).toBeDefined();
  });
});
