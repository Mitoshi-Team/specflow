// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "../i18n";
import Header from "./Header";

function renderHeader(path = "/") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Header />
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("Header", () => {
  it("показывает логотип с доступным именем", () => {
    renderHeader();

    const logo = screen.getByRole("img", { name: "SpecFlow" });
    expect(logo.getAttribute("src")).toBe("/specflow_logo.svg");
  });

  it("показывает название текущего раздела рядом с логотипом", () => {
    renderHeader("/");

    expect(
      screen.getByText("Извлечение атрибутов", {
        selector: ".header__section",
      }),
    ).toBeDefined();
  });

  it("показывает название раздела на странице результатов", () => {
    renderHeader("/results");

    expect(
      screen.getByText("Результаты", { selector: ".header__section" }),
    ).toBeDefined();
  });

  it("показывает ссылки навигации по разделам", () => {
    renderHeader();

    expect(screen.getByRole("link", { name: "Главная" })).toBeDefined();
    expect(screen.getByRole("link", { name: "Результаты" })).toBeDefined();
  });

  it("не показывает служебные индикаторы (версию пайплайна и статус API)", () => {
    renderHeader();

    expect(screen.queryByTitle("Версия пайплайна")).toBeNull();
    expect(screen.queryByLabelText(/Статус API/)).toBeNull();
  });
});
