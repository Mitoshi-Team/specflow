import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  extract,
  extractBatch,
  getBatch,
  getCategory,
  getConfig,
  getHealth,
  getInfo,
  listBatches,
  listCategories,
} from "./index";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockResolvedValue(new Response("{}", { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

function lastCall(): { url: string; method: string } {
  const [url, init] = fetchMock.mock.calls.at(-1) as [string, RequestInit];
  return { url, method: init.method ?? "GET" };
}

describe("endpoints", () => {
  it("extract → POST /extract с телом карточки", async () => {
    await extract({ title: "телефон" });

    const { url, method } = lastCall();
    expect(url).toBe("/api/v1/extract");
    expect(method).toBe("POST");
    expect(fetchMock.mock.calls.at(-1)?.[1].body).toBe(
      JSON.stringify({ title: "телефон" }),
    );
  });

  it("extractBatch → POST /extract/batch", async () => {
    await extractBatch({ items: [{ title: "a" }], batch_size: 10 });

    const { url, method } = lastCall();
    expect(url).toBe("/api/v1/extract/batch");
    expect(method).toBe("POST");
  });

  it("listCategories → GET /categories с query", async () => {
    await listCategories({ category: "phone", limit: 10, offset: 0 });

    const { url, method } = lastCall();
    expect(url).toBe("/api/v1/categories?category=phone&limit=10&offset=0");
    expect(method).toBe("GET");
  });

  it("listCategories без параметров → GET /categories без query", async () => {
    await listCategories();

    expect(lastCall().url).toBe("/api/v1/categories");
  });

  it("getCategory → GET /categories/{category} с кодированием", async () => {
    const category = "Смартфоны и гаджеты";

    await getCategory(category);

    expect(lastCall().url).toBe(
      `/api/v1/categories/${encodeURIComponent(category)}`,
    );
  });

  it("getHealth → GET /health", async () => {
    await getHealth();
    expect(lastCall().url).toBe("/api/v1/health");
  });

  it("getInfo → GET /info", async () => {
    await getInfo();
    expect(lastCall().url).toBe("/api/v1/info");
  });

  it("getConfig → GET /config", async () => {
    await getConfig();
    expect(lastCall().url).toBe("/api/v1/config");
  });

  it("listBatches → GET /batches с query истории", async () => {
    await listBatches({ limit: 10, offset: 20 });

    const { url, method } = lastCall();
    expect(url).toBe("/api/v1/batches?limit=10&offset=20");
    expect(method).toBe("GET");
  });

  it("listBatches без параметров → GET /batches без query", async () => {
    await listBatches();

    expect(lastCall().url).toBe("/api/v1/batches");
  });

  it("getBatch → GET /batches/{batch_id} с кодированием", async () => {
    const batchId = "батч / 1";

    await getBatch(batchId);

    expect(lastCall().url).toBe(
      `/api/v1/batches/${encodeURIComponent(batchId)}`,
    );
  });
});
