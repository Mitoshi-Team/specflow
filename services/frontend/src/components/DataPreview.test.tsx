// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "../i18n";
import { PREVIEW_MAX_ROWS } from "../constants";
import { validateInput } from "../lib/inputValidation";
import type { ProductCardRequest } from "../schemas/api";
import DataPreview from "./DataPreview";
import type { DataPreviewProps } from "./DataPreview";

afterEach(cleanup);

function card(overrides: Partial<ProductCardRequest> = {}): ProductCardRequest {
  return {
    product_id: "sku-1",
    title: "Кофемолка",
    description: "Ручная кофемолка",
    ...overrides,
  };
}

/**
 * Рендер с валидацией, посчитанной вызывающим кодом: так компонент
 * получает проп `validation`, минуя его внутренний расчёт по умолчанию.
 */
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
    expect(screen.getByText(/Показаны первые 2 из 3 карточек/)).toBeDefined();
  });

  it("явно помечает недостающие поля в сводке", () => {
    renderPreview([{ title: "Телефон" }]);

    expect(screen.getByRole("status").textContent).toContain(
      "Отсутствуют поля: Описание, Атрибуты продавца",
    );

    const fields = screen.getAllByRole("listitem");
    expect(fields[0].textContent).toContain("Название");
    expect(fields[0].textContent).toContain("есть");
    expect(fields[1].textContent).toContain("Описание");
    expect(fields[1].textContent).toContain("нет");
  });

  it("подтверждает сводку, когда все обязательные поля заполнены", () => {
    renderPreview([card({ seller_attributes: { color: "чёрный" } })]);

    expect(screen.getByRole("status").textContent).toContain(
      "Все обязательные поля присутствуют",
    );
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
