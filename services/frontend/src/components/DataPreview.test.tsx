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

function tableRows(): HTMLElement[] {
  return screen.getAllByRole("row");
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

  it("не показывает колонку атрибутов продавца", () => {
    render(<DataPreview cards={[card()]} />);

    expect(screen.queryByText("Атрибуты продавца")).toBeNull();
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

    // Без описания остаётся одна незаполненная ячейка.
    const empty = screen.getAllByTitle("поле не заполнено");
    expect(empty).toHaveLength(1);
    expect(empty[0].textContent).toBe("—");
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

  it("показывает только первые maxRows строк", () => {
    const cards: ProductCardRequest[] = [
      { product_id: "p-1", title: "Первый" },
      { product_id: "p-2", title: "Второй" },
      { product_id: "p-3", title: "Третий" },
    ];

    render(<DataPreview cards={cards} maxRows={2} />);

    // одна строка заголовка + две строки данных
    expect(tableRows()).toHaveLength(3);
    expect(screen.queryByText("p-3")).toBeNull();
    expect(screen.getByText(/Показаны первые 2 из 3 карточек/)).toBeDefined();
  });

  it("предупреждает, если хотя бы в одной записи нет описания", () => {
    render(
      <DataPreview
        cards={[card(), { product_id: "p-2", title: "Турка" }]}
      />,
    );

    expect(screen.getByRole("status").textContent).toContain(
      "В одной или нескольких записях отсутствует описание.",
    );
  });

  it("не показывает предупреждений, когда описание есть во всех записях", () => {
    render(<DataPreview cards={[card(), card({ product_id: "sku-2" })]} />);

    expect(screen.queryByRole("status")).toBeNull();
  });

  it("предупреждает и при записи вообще без обязательных полей", () => {
    render(<DataPreview cards={[{ product_id: "p-1" }]} />);

    expect(screen.getByRole("status").textContent).toContain(
      "В одной или нескольких записях отсутствует описание.",
    );
  });

  it("сообщает об отсутствии данных предпросмотра", () => {
    render(<DataPreview cards={[]} />);

    expect(screen.getByText("Нет данных для предпросмотра")).toBeDefined();
  });
});
