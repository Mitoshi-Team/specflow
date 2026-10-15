// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "../i18n";
import DataPreview from "./DataPreview";
import type { DataPreviewProps } from "./DataPreview";
import { validateInput } from "../lib/inputValidation";
import type { ProductCardRequest } from "../schemas/api";

afterEach(cleanup);

function renderPreview(
  cards: ProductCardRequest[],
  props: Partial<Omit<DataPreviewProps, "cards" | "validation">> = {},
) {
  return render(
    <DataPreview cards={cards} validation={validateInput(cards)} {...props} />,
  );
}

function tableRows(): HTMLElement[] {
  return screen.getAllByRole("row");
}

describe("DataPreview", () => {
  it("показывает только первые maxRows строк", () => {
    const cards: ProductCardRequest[] = [
      { product_id: "p-1", title: "Первый" },
      { product_id: "p-2", title: "Второй" },
      { product_id: "p-3", title: "Третий" },
    ];

    renderPreview(cards, { maxRows: 2 });

    // одна строка заголовка + две строки данных
    expect(tableRows()).toHaveLength(3);
    expect(screen.queryByText("p-3")).toBeNull();
    expect(screen.getByText("Показано 2 из 3")).toBeDefined();
  });

  it("явно помечает недостающие поля в сводке", () => {
    renderPreview([{ title: "Телефон" }]);

    expect(screen.getByRole("status").textContent).toContain(
      "Отсутствуют поля: description, seller_attributes",
    );

    const fields = screen.getAllByRole("listitem");
    expect(fields[0].textContent).toContain("title");
    expect(fields[0].textContent).toContain("есть");
    expect(fields[1].textContent).toContain("description");
    expect(fields[1].textContent).toContain("нет");
  });

  it("помечает ячейки с отсутствующими значениями", () => {
    renderPreview([{ product_id: "p-1", title: "Телефон" }]);

    // description и seller_attributes отсутствуют
    expect(screen.getAllByText("—")).toHaveLength(2);
  });

  it("показывает ошибку, когда обязательных полей нет", () => {
    renderPreview([{ product_id: "p-1" }]);

    expect(screen.getByRole("alert").textContent).toContain(
      "нет ни одного из полей title, description или seller_attributes",
    );
  });

  it("сообщает об отсутствии данных предпросмотра", () => {
    renderPreview([]);

    expect(screen.getByText("Нет данных для предпросмотра")).toBeDefined();
  });

  it("сериализует seller_attributes в ячейке", () => {
    renderPreview([
      { product_id: "p-1", seller_attributes: { color: "чёрный" } },
    ]);

    expect(screen.getByText('{"color":"чёрный"}')).toBeDefined();
  });
});
