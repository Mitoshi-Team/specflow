// @vitest-environment jsdom
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { useFileParser } from "./useFileParser";

function fakeFile(name: string, content: string): File {
  return {
    name,
    size: content.length,
    text: () => Promise.resolve(content),
  } as unknown as File;
}

afterEach(cleanup);

describe("useFileParser", () => {
  it("начинает в состоянии idle без файла", () => {
    const { result } = renderHook(() => useFileParser(null));

    expect(result.current).toEqual({
      status: "idle",
      format: null,
      cards: [],
      error: null,
    });
  });

  it("разбирает файл и возвращает карточки", async () => {
    const file = fakeFile("cards.csv", "product_id,description\np-1,Описание");

    const { result } = renderHook(() => useFileParser(file));

    await waitFor(() => expect(result.current.status).toBe("success"));
    expect(result.current.format).toBe("csv");
    expect(result.current.cards).toEqual([
      { product_id: "p-1", description: "Описание" },
    ]);
    expect(result.current.error).toBeNull();
  });

  it("возвращает типизированную ошибку при сбое разбора", async () => {
    const file = fakeFile("cards.txt", "description\nОписание");

    const { result } = renderHook(() => useFileParser(file));

    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(result.current.error).toEqual({ code: "unsupportedFormat" });
    expect(result.current.cards).toEqual([]);
  });

  it("сбрасывается в idle, когда файл убран", async () => {
    const file = fakeFile("cards.csv", "description\nОписание");

    const { result, rerender } = renderHook(
      ({ value }: { value: File | null }) => useFileParser(value),
      { initialProps: { value: file as File | null } },
    );

    await waitFor(() => expect(result.current.status).toBe("success"));

    rerender({ value: null });

    await waitFor(() => expect(result.current.status).toBe("idle"));
    expect(result.current.cards).toEqual([]);
  });
});
