// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { ExtractionMethod } from "../schemas/api";
import MethodBadge from "./MethodBadge";

afterEach(cleanup);

/** Набор методов из контракта (api_contract.md, 3.2). */
const METHODS: ExtractionMethod[] = [
  "rule",
  "dict",
  "ner",
  "classifier",
  "ml_transformer",
  "llm",
  "hybrid",
];

describe("MethodBadge", () => {
  it("показывает метод извлечения как есть", () => {
    render(<MethodBadge method="rule" />);

    expect(screen.getByText("rule")).toBeDefined();
  });

  it("поддерживает все методы контракта", () => {
    for (const method of METHODS) {
      const { unmount } = render(<MethodBadge method={method} />);
      expect(screen.getByText(method)).toBeDefined();
      unmount();
    }
  });
});
