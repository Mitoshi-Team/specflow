// @vitest-environment jsdom
import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ExtractionResponseItem } from "../schemas/api";
import { useCsvExport } from "./useCsvExport";

const RESULTS: ExtractionResponseItem[] = [
  {
    product_id: "sku-1",
    attributes: [
      {
        attribute_code: "brand",
        raw_value: "Bosch",
        normalized_value: "Bosch",
        confidence: 0.95,
        extraction_method: "rule",
        is_confirmed_in_text: true,
      },
    ],
    status: "ok",
    needs_review: false,
    pipeline_version: "1.0.0",
  },
];

let createdAnchor: HTMLAnchorElement | null = null;
let createObjectURL: ReturnType<typeof vi.fn>;

beforeEach(() => {
  createObjectURL = vi.fn(() => "blob:mock");
  // jsdom не реализует Object URL API — подменяем вручную.
  URL.createObjectURL = createObjectURL as unknown as typeof URL.createObjectURL;
  URL.revokeObjectURL = vi.fn(
    () => undefined,
  ) as unknown as typeof URL.revokeObjectURL;

  const realCreateElement = document.createElement.bind(document);
  createdAnchor = null;
  vi.spyOn(document, "createElement").mockImplementation(((
    tagName: string,
    options?: ElementCreationOptions,
  ) => {
    const element = realCreateElement(tagName, options);
    if (tagName === "a") {
      createdAnchor = element as HTMLAnchorElement;
    }
    return element;
  }) as typeof document.createElement);

  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(
    () => undefined,
  );
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

/** jsdom-овый Blob не имеет `text()`; читаем содержимое через FileReader. */
function readBlob(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });
}

describe("useCsvExport", () => {
  it("недоступен при отсутствии результатов", () => {
    const { result } = renderHook(() => useCsvExport([]));

    expect(result.current.disabled).toBe(true);
  });

  it("доступен при наличии результатов", () => {
    const { result } = renderHook(() => useCsvExport(RESULTS));

    expect(result.current.disabled).toBe(false);
  });

  it("ничего не скачивает при отсутствии результатов", () => {
    const { result } = renderHook(() => useCsvExport([]));

    act(() => {
      result.current.exportCsv();
    });

    expect(createObjectURL).not.toHaveBeenCalled();
    expect(HTMLAnchorElement.prototype.click).not.toHaveBeenCalled();
  });

  it("формирует CSV PredictionRow и инициирует скачивание", async () => {
    const { result } = renderHook(() =>
      useCsvExport(RESULTS, {
        cards: [{ product_id: "sku-1", title: "Кофемолка" }],
      }),
    );

    act(() => {
      result.current.exportCsv();
    });

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    const blob = createObjectURL.mock.calls[0][0] as Blob;
    expect(await readBlob(blob)).toBe(
      "product_id,title,category,brand,brand_confidence,needs_review,status\r\n" +
        "sku-1,Кофемолка,,Bosch,0.95,false,ok\r\n",
    );
    expect(createdAnchor?.download).toBe("predictions.csv");
    expect(createdAnchor?.href).toBe("blob:mock");
    expect(HTMLAnchorElement.prototype.click).toHaveBeenCalledTimes(1);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:mock");
  });

  it("использует переданное имя файла", () => {
    const { result } = renderHook(() =>
      useCsvExport(RESULTS, { filename: "batch-42.csv" }),
    );

    act(() => {
      result.current.exportCsv();
    });

    expect(createdAnchor?.download).toBe("batch-42.csv");
  });
});
