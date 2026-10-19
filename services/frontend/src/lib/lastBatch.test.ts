// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";

import { LAST_BATCH_STORAGE_KEY } from "../constants";
import type { BatchExtractResponse } from "../schemas/api";
import {
  clearLastBatch,
  readLastBatch,
  writeLastBatch,
} from "./lastBatch";

afterEach(() => {
  window.localStorage.clear();
});

function batchResponse(): BatchExtractResponse {
  return {
    total: 1,
    ok: 1,
    low_confidence: 0,
    errors: 0,
    results: [],
  };
}

describe("lastBatch", () => {
  it("возвращает null, когда батч не сохранён", () => {
    expect(readLastBatch()).toBeNull();
  });

  it("сохраняет и читает последний батч вместе с порогом и карточками", () => {
    const batch = {
      response: batchResponse(),
      threshold: 0.8,
      cards: [{ title: "Кофемолка" }],
    };

    writeLastBatch(batch);

    expect(readLastBatch()).toEqual(batch);
  });

  it("удаляет сохранённый батч по clearLastBatch", () => {
    writeLastBatch({ response: batchResponse() });

    clearLastBatch();

    expect(readLastBatch()).toBeNull();
    expect(window.localStorage.getItem(LAST_BATCH_STORAGE_KEY)).toBeNull();
  });

  it("на повреждённых данных возвращает null и убирает запись", () => {
    window.localStorage.setItem(LAST_BATCH_STORAGE_KEY, "{ не json");

    expect(readLastBatch()).toBeNull();
    expect(window.localStorage.getItem(LAST_BATCH_STORAGE_KEY)).toBeNull();
  });

  it("на данных чужой формы возвращает null и убирает запись", () => {
    window.localStorage.setItem(LAST_BATCH_STORAGE_KEY, JSON.stringify({ foo: 1 }));

    expect(readLastBatch()).toBeNull();
    expect(window.localStorage.getItem(LAST_BATCH_STORAGE_KEY)).toBeNull();
  });
});
