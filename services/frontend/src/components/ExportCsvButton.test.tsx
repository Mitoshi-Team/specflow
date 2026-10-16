// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "../i18n";
import type { ExtractionResponseItem } from "../schemas/api";
import ExportCsvButton from "./ExportCsvButton";

const RESULTS: ExtractionResponseItem[] = [
  {
    product_id: "sku-1",
    attributes: [],
    status: "ok",
    needs_review: false,
    pipeline_version: "1.0.0",
  },
];

let createObjectURL: ReturnType<typeof vi.fn>;

beforeEach(() => {
  createObjectURL = vi.fn(() => "blob:mock");
  URL.createObjectURL = createObjectURL as unknown as typeof URL.createObjectURL;
  URL.revokeObjectURL = vi.fn(
    () => undefined,
  ) as unknown as typeof URL.revokeObjectURL;
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(
    () => undefined,
  );
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function button(): HTMLButtonElement {
  return screen.getByRole("button", {
    name: "Экспорт результатов в формате CSV",
  }) as HTMLButtonElement;
}

describe("ExportCsvButton", () => {
  it("отключена при отсутствии результатов", () => {
    render(<ExportCsvButton results={[]} />);

    expect(button().disabled).toBe(true);
    expect(button().textContent).toBe("Скачать CSV");
  });

  it("активна при наличии результатов", () => {
    render(<ExportCsvButton results={RESULTS} />);

    expect(button().disabled).toBe(false);
  });

  it("скачивает CSV по нажатию", () => {
    render(<ExportCsvButton results={RESULTS} />);

    fireEvent.click(button());

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(HTMLAnchorElement.prototype.click).toHaveBeenCalledTimes(1);
  });
});
