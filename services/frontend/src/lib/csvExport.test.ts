import { describe, expect, it } from "vitest";

import type {
  AttributePrediction,
  ExtractionResponseItem,
  ProductCardRequest,
} from "../schemas/api";
import {
  collectAttributeCodes,
  escapeCsvValue,
  predictionColumns,
  serializePredictionsCsv,
} from "./csvExport";

function attribute(
  overrides: Partial<AttributePrediction> = {},
): AttributePrediction {
  return {
    attribute_code: "brand",
    raw_value: "Bosch",
    normalized_value: "Bosch",
    confidence: 0.95,
    extraction_method: "rule",
    is_confirmed_in_text: true,
    ...overrides,
  };
}

function result(
  overrides: Partial<ExtractionResponseItem> = {},
): ExtractionResponseItem {
  return {
    product_id: "sku-1",
    attributes: [],
    status: "ok",
    needs_review: false,
    pipeline_version: "1.0.0",
    ...overrides,
  };
}

describe("escapeCsvValue", () => {
  it("не экранирует простое значение", () => {
    expect(escapeCsvValue("Bosch")).toBe("Bosch");
  });

  it("берёт в кавычки значение с разделителем-запятой", () => {
    expect(escapeCsvValue("Bosch, 2 шт")).toBe('"Bosch, 2 шт"');
  });

  it("удваивает кавычки и обрамляет значение", () => {
    expect(escapeCsvValue('Модель "X"')).toBe('"Модель ""X"""');
  });

  it("берёт в кавычки значение с переводом строки", () => {
    expect(escapeCsvValue("первая\nвторая")).toBe('"первая\nвторая"');
    expect(escapeCsvValue("первая\r\nвторая")).toBe('"первая\r\nвторая"');
  });

  it("сохраняет пустое значение пустым", () => {
    expect(escapeCsvValue("")).toBe("");
  });
});

describe("collectAttributeCodes", () => {
  it("собирает коды в порядке первого появления без дублей", () => {
    const codes = collectAttributeCodes([
      result({ attributes: [attribute({ attribute_code: "brand" })] }),
      result({
        attributes: [
          attribute({ attribute_code: "color" }),
          attribute({ attribute_code: "brand" }),
        ],
      }),
    ]);

    expect(codes).toEqual(["brand", "color"]);
  });

  it("возвращает пустой список, если атрибутов нет", () => {
    expect(collectAttributeCodes([result()])).toEqual([]);
  });
});

describe("predictionColumns", () => {
  it("строит колонки PredictionRow в заданном порядке", () => {
    const columns = predictionColumns([
      result({ attributes: [attribute({ attribute_code: "brand" })] }),
    ]);

    expect(columns).toEqual([
      "product_id",
      "title",
      "category",
      "brand",
      "brand_confidence",
      "needs_review",
      "status",
    ]);
  });
});

describe("serializePredictionsCsv", () => {
  it("формирует заголовок и строку для одной карточки", () => {
    const cards: ProductCardRequest[] = [
      { product_id: "sku-1", title: "Кофемолка" },
    ];
    const csv = serializePredictionsCsv(
      [
        result({
          category_name: "Кофемолки",
          attributes: [attribute()],
        }),
      ],
      cards,
    );

    expect(csv).toBe(
      "product_id,title,category,brand,brand_confidence,needs_review,status\r\n" +
        "sku-1,Кофемолка,Кофемолки,Bosch,0.95,false,ok\r\n",
    );
  });

  it("экспортирует все результаты батча в исходном порядке", () => {
    const csv = serializePredictionsCsv([
      result({ product_id: "sku-1" }),
      result({ product_id: "sku-2" }),
    ]);

    const lines = csv.split("\r\n");
    expect(lines[0]).toBe("product_id,title,category,needs_review,status");
    expect(lines[1]).toBe("sku-1,,,false,ok");
    expect(lines[2]).toBe("sku-2,,,false,ok");
  });

  it("оставляет пустые ячейки для не извлечённых атрибутов", () => {
    const csv = serializePredictionsCsv([
      result({
        product_id: "sku-1",
        attributes: [attribute({ attribute_code: "brand" })],
      }),
      result({
        product_id: "sku-2",
        attributes: [
          attribute({
            attribute_code: "color",
            normalized_value: "чёрный",
            confidence: 0.9,
          }),
        ],
      }),
    ]);

    const lines = csv.split("\r\n");
    expect(lines[0]).toBe(
      "product_id,title,category,brand,brand_confidence,color,color_confidence,needs_review,status",
    );
    // У первой карточки нет color, у второй — brand.
    expect(lines[1]).toBe("sku-1,,,Bosch,0.95,,,false,ok");
    expect(lines[2]).toBe("sku-2,,,,,чёрный,0.9,false,ok");
  });

  it("использует category_id, когда нет названия категории", () => {
    const csv = serializePredictionsCsv([
      result({ category_id: "cat-7", category_name: undefined }),
    ]);

    expect(csv.split("\r\n")[1]).toBe("sku-1,,cat-7,false,ok");
  });

  it("предпочитает category_name вместо category_id", () => {
    const csv = serializePredictionsCsv([
      result({ category_id: "cat-7", category_name: "Кофемолки" }),
    ]);

    expect(csv.split("\r\n")[1]).toBe("sku-1,,Кофемолки,false,ok");
  });

  it("сериализует needs_review как true/false", () => {
    const csv = serializePredictionsCsv([
      result({ needs_review: true, status: "low_confidence" }),
    ]);

    expect(csv.split("\r\n")[1]).toBe("sku-1,,,true,low_confidence");
  });

  it("подставляет title из исходной карточки по product_id", () => {
    const csv = serializePredictionsCsv(
      [result({ product_id: "sku-2" })],
      [
        { product_id: "sku-1", title: "Первая" },
        { product_id: "sku-2", title: "Вторая" },
      ],
    );

    expect(csv.split("\r\n")[1]).toBe("sku-2,Вторая,,false,ok");
  });

  it("подставляет title по позиции, если нет совпадения по product_id", () => {
    const csv = serializePredictionsCsv(
      [result({ product_id: undefined })],
      [{ title: "Единственная" }],
    );

    expect(csv.split("\r\n")[1]).toBe(",Единственная,,false,ok");
  });

  it("оставляет title пустым без исходных карточек", () => {
    const csv = serializePredictionsCsv([result({ product_id: "sku-1" })]);

    expect(csv.split("\r\n")[1]).toBe("sku-1,,,false,ok");
  });

  it("экранирует значения с запятыми, кавычками и переносами строк", () => {
    const csv = serializePredictionsCsv(
      [
        result({
          product_id: "sku,1",
          attributes: [
            attribute({
              attribute_code: "brand",
              normalized_value: 'Модель "Pro", 2 шт',
            }),
          ],
        }),
      ],
      [{ product_id: "sku,1", title: "Строка\nпереноса" }],
    );

    const lines = csv.split("\r\n");
    expect(lines[0]).toBe(
      "product_id,title,category,brand,brand_confidence,needs_review,status",
    );
    expect(lines[1]).toBe(
      '"sku,1","Строка\nпереноса",,"Модель ""Pro"", 2 шт",0.95,false,ok',
    );
  });

  it("возвращает только заголовок при отсутствии результатов", () => {
    expect(serializePredictionsCsv([])).toBe(
      "product_id,title,category,needs_review,status\r\n",
    );
  });
});
