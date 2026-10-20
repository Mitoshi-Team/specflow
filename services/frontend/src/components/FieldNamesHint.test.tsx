// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "../i18n";
import FieldNamesHint from "./FieldNamesHint";

afterEach(cleanup);

describe("FieldNamesHint", () => {
  it("показывает имена полей во всплывающем меню", () => {
    render(<FieldNamesHint />);

    const tooltip = screen.getByRole("tooltip");
    expect(tooltip.textContent).toContain("product_id");
    expect(tooltip.textContent).toContain("title");
    expect(tooltip.textContent).toContain("description");
  });

  it("связывает иконку с подсказкой для скринридера", () => {
    render(<FieldNamesHint />);

    const icon = screen.getByRole("button", {
      name: "Какие поля читает анализатор",
    });
    const tooltip = screen.getByRole("tooltip");
    expect(icon.getAttribute("aria-describedby")).toBe(tooltip.id);
  });
});
