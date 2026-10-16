// @vitest-environment jsdom
import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, extractBatch } from "../api";
import type { BatchExtractResponse } from "../schemas/api";
import { useBatchExtract, type BatchSettings } from "./useBatchExtract";

vi.mock("../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api")>();
  return { ...actual, extractBatch: vi.fn() };
});

const extractBatchMock = vi.mocked(extractBatch);

afterEach(() => {
  cleanup();
  extractBatchMock.mockReset();
});

const CARDS = [{ title: "Кофемолка" }];
const SETTINGS: BatchSettings = { batchSize: 10, thresholdOverride: 0.8 };

const RESPONSE: BatchExtractResponse = {
  batch_id: "b-1",
  total: 1,
  ok: 1,
  low_confidence: 0,
  errors: 0,
  results: [
    {
      product_id: "sku-1",
      attributes: [
        {
          attribute_code: "brand",
          raw_value: "Melitta",
          normalized_value: "Melitta",
          confidence: 0.95,
          extraction_method: "rule",
          is_confirmed_in_text: true,
        },
      ],
      status: "ok",
      needs_review: false,
      pipeline_version: "1.0.0",
    },
  ],
  processing_time_ms_total: 42,
};

describe("useBatchExtract", () => {
  it("начинает в состоянии idle", () => {
    const { result } = renderHook(() => useBatchExtract());

    expect(result.current.status).toBe("idle");
    expect(result.current.progress).toEqual({ processed: 0, total: 0 });
    expect(result.current.error).toBeNull();
    expect(result.current.response).toBeNull();
  });

  it("отправляет батч с настройками и завершается успешно", async () => {
    extractBatchMock.mockResolvedValue(RESPONSE);
    const { result } = renderHook(() => useBatchExtract());

    await act(async () => {
      await result.current.run(CARDS, SETTINGS);
    });

    expect(extractBatchMock).toHaveBeenCalledWith({
      items: CARDS,
      batch_size: 10,
      threshold_override: 0.8,
    });
    expect(result.current.status).toBe("success");
    expect(result.current.progress).toEqual({ processed: 1, total: 1 });
    expect(result.current.response).toEqual(RESPONSE);
    expect(result.current.error).toBeNull();
  });

  it("блокирует повторный запуск во время выполнения", async () => {
    let resolveBatch: (value: BatchExtractResponse) => void = () => {};
    extractBatchMock.mockReturnValue(
      new Promise<BatchExtractResponse>((resolve) => {
        resolveBatch = resolve;
      }),
    );
    const { result } = renderHook(() => useBatchExtract());

    await act(async () => {
      const first = result.current.run(CARDS, SETTINGS);
      const second = result.current.run(CARDS, SETTINGS);
      resolveBatch(RESPONSE);
      await Promise.all([first, second]);
    });

    expect(extractBatchMock).toHaveBeenCalledTimes(1);
    expect(result.current.status).toBe("success");
  });

  it("переводит в error и сохраняет данные ErrorResponse", async () => {
    const apiError = new ApiError({
      status: 422,
      message: "api.errors.http",
      detail: "Некорректный запрос",
      errors: [
        { loc: ["body", "items"], msg: "too many", type: "value_error" },
      ],
    });
    extractBatchMock.mockRejectedValue(apiError);
    const { result } = renderHook(() => useBatchExtract());

    await act(async () => {
      await result.current.run(CARDS, SETTINGS);
    });

    expect(result.current.status).toBe("error");
    expect(result.current.error).toBe(apiError);
    expect(result.current.error?.detail).toBe("Некорректный запрос");
    expect(result.current.error?.errors).toHaveLength(1);
    expect(result.current.response).toBeNull();
  });

  it("не запускается без карточек", async () => {
    const { result } = renderHook(() => useBatchExtract());

    await act(async () => {
      await result.current.run([], SETTINGS);
    });

    expect(extractBatchMock).not.toHaveBeenCalled();
    expect(result.current.status).toBe("idle");
  });

  it("не запускается при настройках вне диапазона контракта", async () => {
    const { result } = renderHook(() => useBatchExtract());

    await act(async () => {
      await result.current.run(CARDS, { ...SETTINGS, batchSize: 51 });
      await result.current.run(CARDS, { ...SETTINGS, batchSize: 1.5 });
      await result.current.run(CARDS, { ...SETTINGS, thresholdOverride: 1.5 });
    });

    expect(extractBatchMock).not.toHaveBeenCalled();
    expect(result.current.status).toBe("idle");
  });

  it("сбрасывает состояние после завершения", async () => {
    extractBatchMock.mockResolvedValue(RESPONSE);
    const { result } = renderHook(() => useBatchExtract());

    await act(async () => {
      await result.current.run(CARDS, SETTINGS);
      result.current.reset();
    });

    expect(result.current.status).toBe("idle");
    expect(result.current.progress).toEqual({ processed: 0, total: 0 });
    expect(result.current.response).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("игнорирует сброс во время выполнения", async () => {
    let resolveBatch: (value: BatchExtractResponse) => void = () => {};
    extractBatchMock.mockReturnValue(
      new Promise<BatchExtractResponse>((resolve) => {
        resolveBatch = resolve;
      }),
    );
    const { result } = renderHook(() => useBatchExtract());

    await act(async () => {
      const pending = result.current.run(CARDS, SETTINGS);
      result.current.reset();
      resolveBatch(RESPONSE);
      await pending;
    });

    expect(result.current.status).toBe("success");
    expect(result.current.response).toEqual(RESPONSE);
  });
});
