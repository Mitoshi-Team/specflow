// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import EmptyState from "./EmptyState";

afterEach(cleanup);

describe("EmptyState", () => {
  it("показывает текст пустого состояния в регионе status", () => {
    render(<EmptyState message="Нет данных" />);

    const status = screen.getByRole("status");
    expect(status.textContent).toBe("Нет данных");
    expect(status.className).toContain("empty-state");
  });
});
