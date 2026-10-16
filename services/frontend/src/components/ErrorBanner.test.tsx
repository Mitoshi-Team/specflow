// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ApiError } from "../api";
import "../i18n";
import ErrorBanner from "./ErrorBanner";

afterEach(cleanup);

describe("ErrorBanner", () => {
  it("показывает переведённое сообщение ошибки", () => {
    const error = new ApiError({ status: 500, message: "api.errors.http" });

    render(<ErrorBanner error={error} />);

    expect(screen.getByRole("alert").textContent).toContain(
      "Сервер вернул ошибку",
    );
  });

  it("показывает HTTP-статус, detail и ошибки валидации", () => {
    const error = new ApiError({
      status: 422,
      message: "api.errors.http",
      detail: "Некорректный запрос",
      errors: [
        { loc: ["body", "items"], msg: "too many", type: "value_error" },
      ],
    });

    render(<ErrorBanner error={error} />);

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("HTTP 422");
    expect(alert.textContent).toContain("Некорректный запрос");
    expect(alert.textContent).toContain("body.items: too many");
    expect(screen.getByText("Технические детали")).toBeDefined();
  });

  it("не показывает диагностику для сетевой ошибки без деталей", () => {
    const error = new ApiError({ status: 0, message: "api.errors.network" });

    render(<ErrorBanner error={error} />);

    expect(screen.getByRole("alert").textContent).toContain(
      "Не удалось соединиться с сервером",
    );
    expect(screen.queryByText("Технические детали")).toBeNull();
  });
});
