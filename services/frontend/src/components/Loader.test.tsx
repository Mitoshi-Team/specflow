// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "../i18n";
import Loader from "./Loader";

afterEach(cleanup);

describe("Loader", () => {
  it("показывает спиннер и общую подпись по умолчанию", () => {
    render(<Loader />);

    expect(screen.getByRole("status").textContent).toContain("Загрузка…");
    expect(screen.queryByRole("progressbar")).toBeNull();
  });

  it("показывает переданную подпись", () => {
    render(<Loader label="Обработка файла…" />);

    expect(screen.getByRole("status").textContent).toContain(
      "Обработка файла…",
    );
  });

  it("добавляет определённый прогресс, когда он передан", () => {
    render(<Loader label="Обрабатывается" progress={{ processed: 3, total: 5 }} />);

    const bar = screen.getByRole("progressbar");
    expect(bar.getAttribute("aria-valuemin")).toBe("0");
    expect(bar.getAttribute("aria-valuemax")).toBe("5");
    expect(bar.getAttribute("aria-valuenow")).toBe("3");
    expect(bar.getAttribute("aria-label")).toBe("Обработано 3 из 5");
  });

  it("поддерживает компактный вариант для строки", () => {
    const { container } = render(<Loader inline />);

    expect(container.querySelector(".loader--inline")).not.toBeNull();
  });
});
