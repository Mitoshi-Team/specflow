// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "../i18n";
import { PREVIEW_MAX_ROWS } from "../constants";
import type { ProductCardRequest } from "../schemas/api";
import DataPreview from "./DataPreview";

afterEach(cleanup);

function card(overrides: Partial<ProductCardRequest> = {}): ProductCardRequest {
  return {
    product_id: "sku-1",
    title: "Кофемолка",
    description: "Ручная кофемолка",
    ...overrides,
  };
}

describe("DataPreview", () => {
  it("показывает первые строки с ключевыми полями", () => {
    render(
      <DataPreview
        cards={[
          card({ title: "Кофемолка ручная" }),
          card({ product_id: "sku-2", title: "Турка" }),
        ]}
      />,
    );

    expect(screen.getByText("sku-1")).toBeDefined();
    expect(screen.getByText("sku-2")).toBeDefined();
    expect(screen.getByText("Кофемолка ручная")).toBeDefined();
    expect(screen.getByText("Турка")).toBeDefined();
  });

  it("показывает не больше PREVIEW_MAX_ROWS строк и сообщает общее число", () => {
    const cards = Array.from({ length: PREVIEW_MAX_ROWS + 5 }, (_, index) =>
      card({ product_id: `sku-${index}` }),
    );

    render(<DataPreview cards={cards} />);

    expect(screen.getByText("sku-0")).toBeDefined();
    expect(screen.queryByText(`sku-${PREVIEW_MAX_ROWS}`)).toBeNull();
    expect(screen.getByText(/Показаны первые 20 из 25 карточек/)).toBeDefined();
  });

  it("отмечает незаполненные поля отдельной меткой", () => {
    render(<DataPreview cards={[card({ description: undefined })]} />);

    // Без описания и атрибутов продавца остаются две незаполненные ячейки.
    const empty = screen.getAllByTitle("поле не заполнено");
    expect(empty).toHaveLength(2);
    expect(empty.every((cell) => cell.textContent === "—")).toBe(true);
  });

  it("раскрывает длинное значение по действию пользователя", () => {
    const longDescription = "Очень длинное описание ".repeat(10);
    render(<DataPreview cards={[card({ description: longDescription })]} />);

    const toggle = screen.getByRole("button", { name: "Показать полностью" });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");

    fireEvent.click(toggle);

    expect(screen.getByRole("button", { name: "Свернуть" })).toBeDefined();
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
  });

  it("не показывает действие раскрытия для коротких значений", () => {
    render(<DataPreview cards={[card()]} />);

    expect(screen.queryByRole("button")).toBeNull();
  });
});
