import { describe, expect, it } from "vitest";

import {
  hasRequiredContent,
  isFieldPresent,
  validateInput,
} from "./inputValidation";

describe("isFieldPresent", () => {
  it("считает непустой title присутствующим", () => {
    expect(isFieldPresent({ title: "Телефон" }, "title")).toBe(true);
  });

  it("считает пустой строки title отсутствующим", () => {
    expect(isFieldPresent({ title: "   " }, "title")).toBe(false);
    expect(isFieldPresent({}, "title")).toBe(false);
  });

  it("считает пустой объект seller_attributes отсутствующим", () => {
    expect(isFieldPresent({ seller_attributes: {} }, "seller_attributes")).toBe(
      false,
    );
  });

  it("считает непустой seller_attributes присутствующим", () => {
    expect(
      isFieldPresent(
        { seller_attributes: { color: "чёрный" } },
        "seller_attributes",
      ),
    ).toBe(true);
  });
});

describe("hasRequiredContent", () => {
  it("истинно при наличии только title", () => {
    expect(hasRequiredContent({ title: "Телефон" })).toBe(true);
  });

  it("истинно при наличии только seller_attributes", () => {
    expect(hasRequiredContent({ seller_attributes: { brand: "A" } })).toBe(
      true,
    );
  });

  it("ложно, когда все обязательные поля пусты", () => {
    expect(
      hasRequiredContent({ product_id: "p-1", seller_attributes: {} }),
    ).toBe(false);
  });
});

describe("validateInput", () => {
  it("перечисляет присутствующие поля, когда есть все три", () => {
    const result = validateInput([
      { title: "Телефон", description: "Описание", seller_attributes: { a: 1 } },
    ]);

    expect(result.valid).toBe(true);
    expect(result.presentFields).toEqual([
      "title",
      "description",
      "seller_attributes",
    ]);
    expect(result.missingFields).toEqual([]);
    expect(result.errors).toEqual([]);
  });

  it("показывает недостающие поля, даже если хотя бы одно присутствует", () => {
    const result = validateInput([{ title: "Телефон" }]);

    expect(result.valid).toBe(true);
    expect(result.presentFields).toEqual(["title"]);
    expect(result.missingFields).toEqual(["description", "seller_attributes"]);
    expect(result.errors).toEqual([]);
  });

  it("объединяет поля из разных карточек", () => {
    const result = validateInput([
      { title: "Телефон" },
      { description: "Описание" },
    ]);

    expect(result.presentFields).toEqual(["title", "description"]);
    expect(result.missingFields).toEqual(["seller_attributes"]);
  });

  it("невалиден и возвращает ошибку, когда обязательных полей нет", () => {
    const result = validateInput([
      { product_id: "p-1" },
      { seller_attributes: {} },
    ]);

    expect(result.valid).toBe(false);
    expect(result.presentFields).toEqual([]);
    expect(result.missingFields).toEqual([
      "title",
      "description",
      "seller_attributes",
    ]);
    expect(result.errors).toEqual([{ code: "noContent" }]);
  });

  it("невалиден для пустого набора карточек", () => {
    const result = validateInput([]);

    expect(result.valid).toBe(false);
    expect(result.errors).toEqual([{ code: "noContent" }]);
  });
});
