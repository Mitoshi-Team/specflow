import { describe, expect, it } from "vitest";

import { MAX_UPLOAD_SIZE_BYTES } from "../constants";
import {
  detectFormat,
  parseFile,
  parseFileContent,
  type FileParseResult,
} from "./fileParser";

function expectFailure(result: FileParseResult, code: string, row?: number) {
  expect(result.ok).toBe(false);
  if (!result.ok) {
    expect(result.error).toMatchObject(row === undefined ? { code } : { code, row });
  }
}

describe("detectFormat", () => {
  it.each([
    ["cards.csv", "csv"],
    ["cards.CSV", "csv"],
    ["cards.json", "json"],
    ["cards.tsv", "tsv"],
  ])("определяет формат %s как %s", (name, expected) => {
    expect(detectFormat(name)).toBe(expected);
  });

  it("возвращает null для неизвестного расширения", () => {
    expect(detectFormat("cards.txt")).toBeNull();
  });

  it("возвращает null, если расширения нет", () => {
    expect(detectFormat("cards")).toBeNull();
  });
});

describe("parseFileContent: пустой ввод", () => {
  it("считает пустой файл ошибкой", () => {
    expectFailure(parseFileContent("", "csv"), "emptyFile");
  });

  it("считает файл из пробелов пустым", () => {
    expectFailure(parseFileContent("   \n  ", "json"), "emptyFile");
  });
});

describe("parseFileContent: CSV", () => {
  const csv = [
    "product_id,title,description,seller_attributes,category_id,category_name",
    'p-1,Телефон,"Описание товара","{""color"":""чёрный""}",c-1,Смартфоны',
  ].join("\n");

  it("разбирает карточку и приводит seller_attributes к объекту", () => {
    expect(parseFileContent(csv, "csv")).toEqual({
      ok: true,
      format: "csv",
      cards: [
        {
          product_id: "p-1",
          title: "Телефон",
          description: "Описание товара",
          seller_attributes: { color: "чёрный" },
          category_id: "c-1",
          category_name: "Смартфоны",
        },
      ],
    });
  });

  it("обрезает пробелы и опускает пустые поля", () => {
    const result = parseFileContent("title,description\n  Телефон  ,", "csv");

    expect(result).toEqual({
      ok: true,
      format: "csv",
      cards: [{ title: "Телефон" }],
    });
  });

  it("игнорирует неизвестные колонки", () => {
    const result = parseFileContent(
      "description,unknown\nОписание,значение",
      "csv",
    );

    expect(result).toEqual({
      ok: true,
      format: "csv",
      cards: [{ description: "Описание" }],
    });
  });

  it("сообщает о некорректном JSON в seller_attributes с номером строки", () => {
    expectFailure(
      parseFileContent(
        "description,seller_attributes\nОписание,not-json",
        "csv",
      ),
      "invalidSellerAttributes",
      2,
    );
  });

  it("сообщает об отсутствии колонки description", () => {
    expectFailure(
      parseFileContent("title,seller_attributes\nТелефон,{}", "csv"),
      "noContent",
    );
  });

  it("принимает файл, где description пуст в отдельных строках", () => {
    const result = parseFileContent("title,description\nТелефон,", "csv");

    expect(result).toEqual({
      ok: true,
      format: "csv",
      cards: [{ title: "Телефон" }],
    });
  });

  it("сообщает об отсутствии карточек, если есть только заголовок", () => {
    expectFailure(parseFileContent("title,description", "csv"), "noCards");
  });
});

describe("parseFileContent: TSV", () => {
  it("использует табуляцию как разделитель", () => {
    const result = parseFileContent(
      "product_id\tdescription\np-2\tНоутбук",
      "tsv",
    );

    expect(result).toEqual({
      ok: true,
      format: "tsv",
      cards: [{ product_id: "p-2", description: "Ноутбук" }],
    });
  });
});

describe("parseFileContent: JSON", () => {
  it("разбирает массив карточек", () => {
    const content = JSON.stringify([
      {
        product_id: "p-1",
        title: "Телефон",
        description: "Описание",
        seller_attributes: { color: "чёрный" },
      },
    ]);

    expect(parseFileContent(content, "json")).toEqual({
      ok: true,
      format: "json",
      cards: [
        {
          product_id: "p-1",
          title: "Телефон",
          description: "Описание",
          seller_attributes: { color: "чёрный" },
        },
      ],
    });
  });

  it("сообщает о невалидном JSON", () => {
    expectFailure(parseFileContent("{not json", "json"), "invalidJson");
  });

  it("требует массив на верхнем уровне", () => {
    expectFailure(parseFileContent('{"title":"x"}', "json"), "invalidStructure");
  });

  it("сообщает об отсутствии карточек для пустого массива", () => {
    expectFailure(parseFileContent("[]", "json"), "noCards");
  });

  it("сообщает об элементе не-объекте с номером элемента", () => {
    expectFailure(parseFileContent("[1]", "json"), "invalidStructure", 1);
  });

  it("сообщает об отсутствии поля description у элементов", () => {
    expectFailure(
      parseFileContent('[{"product_id":"p-1"}]', "json"),
      "noContent",
    );
  });

  it("принимает элемент без title, если есть description", () => {
    expect(parseFileContent('[{"product_id":"p-1","description":"Текст"}]', "json")).toEqual({
      ok: true,
      format: "json",
      cards: [{ product_id: "p-1", description: "Текст" }],
    });
  });

  it("отклоняет нестроковые значения строковых полей", () => {
    expectFailure(
      parseFileContent('[{"description":"x","title":123}]', "json"),
      "invalidStructure",
      1,
    );
  });

  it("отклоняет seller_attributes, не являющиеся объектом", () => {
    expectFailure(
      parseFileContent(
        '[{"description":"x","seller_attributes":"y"}]',
        "json",
      ),
      "invalidStructure",
      1,
    );
  });
});

describe("parseFile", () => {
  function fakeFile(name: string, content: string, size?: number): File {
    return {
      name,
      size: size ?? content.length,
      text: () => Promise.resolve(content),
    } as unknown as File;
  }

  it("отклоняет файл с неподдерживаемым расширением", async () => {
    const result = await parseFile(fakeFile("cards.txt", "description\nОписание"));
    expectFailure(result, "unsupportedFormat");
  });

  it("отклоняет слишком большой файл", async () => {
    const result = await parseFile(
      fakeFile("cards.csv", "", MAX_UPLOAD_SIZE_BYTES + 1),
    );
    expectFailure(result, "fileTooLarge");
  });

  it("отклоняет пустой файл", async () => {
    const result = await parseFile(fakeFile("cards.csv", ""));
    expectFailure(result, "emptyFile");
  });

  it("возвращает результат успешного разбора", async () => {
    const result = await parseFile(fakeFile("cards.csv", "description\nОписание"));
    expect(result).toEqual({
      ok: true,
      format: "csv",
      cards: [{ description: "Описание" }],
    });
  });

  it("возвращает readError, если файл не читается", async () => {
    const file = {
      name: "cards.csv",
      size: 3,
      text: () => Promise.reject(new Error("boom")),
    } as unknown as File;

    const result = await parseFile(file);
    expectFailure(result, "readError");
  });
});
