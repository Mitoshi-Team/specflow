import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, request } from "./client";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("request", () => {
  it("отправляет GET на базовый URL с префиксом /api/v1", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ status: "ok" }));

    await request("/health");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/health");
    expect(init.method).toBe("GET");
    expect(init.body).toBeUndefined();
  });

  it("подставляет VITE_API_BASE_URL, если он задан", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.com");
    fetchMock.mockResolvedValue(jsonResponse({}));

    await request("/health");

    expect(fetchMock.mock.calls[0][0]).toBe(
      "https://api.example.com/api/v1/health",
    );
  });

  it("добавляет query-параметры и пропускает null/undefined", async () => {
    fetchMock.mockResolvedValue(jsonResponse({}));

    await request("/categories", {
      query: { category: "phone", limit: 50, offset: undefined, extra: null },
    });

    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/v1/categories?category=phone&limit=50",
    );
  });

  it("отправляет JSON-тело и заголовок Content-Type при наличии body", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }));

    await request("/extract", { method: "POST", body: { title: "товар" } });

    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
    expect(init.body).toBe(JSON.stringify({ title: "товар" }));
  });

  it("возвращает разобранный JSON успешного ответа", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ status: "ok" }));

    await expect(request("/health")).resolves.toEqual({ status: "ok" });
  });

  it("возвращает undefined для ответа 204", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    await expect(request("/config")).resolves.toBeUndefined();
  });

  it("преобразует ErrorResponse в ApiError", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(
        {
          detail: "Некорректный запрос",
          code: "bad_request",
          errors: [{ loc: ["body", "items"], msg: "too many", type: "value_error" }],
        },
        400,
      ),
    );

    await expect(request("/extract/batch")).rejects.toMatchObject({
      name: "ApiError",
      status: 400,
      code: "bad_request",
      detail: "Некорректный запрос",
      errors: [{ loc: ["body", "items"], msg: "too many", type: "value_error" }],
    });
  });

  it("устойчив к телу ошибки, не соответствующему контракту", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: [{ loc: [], msg: "x", type: "y" }] }), {
        status: 422,
      }),
    );

    const error = await request("/extract").catch((cause: unknown) => cause);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 422, detail: undefined });
  });

  it("преобразует сетевой сбой в ApiError со status 0", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(request("/health")).rejects.toMatchObject({
      name: "ApiError",
      status: 0,
      message: "api.errors.network",
    });
  });

  it("бросает ApiError при некорректном JSON успешного ответа", async () => {
    fetchMock.mockResolvedValue(new Response("not json", { status: 200 }));

    await expect(request("/health")).rejects.toMatchObject({
      name: "ApiError",
      status: 200,
      message: "api.errors.invalidResponse",
    });
  });
});
