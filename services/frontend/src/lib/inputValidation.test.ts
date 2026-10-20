import { describe, expect, it } from "vitest";

import { hasMissingDescription, isFieldPresent } from "./inputValidation";

describe("isFieldPresent", () => {
  it("считает непустой title присутствующим", () => {
    expect(isFieldPresent({ title: "Телефон" }, "title")).toBe(true);
  });

  it("считает пустые строки отсутствующими", () => {
    expect(isFieldPresent({ title: "   " }, "title")).toBe(false);
    expect(isFieldPresent({}, "title")).toBe(false);
    expect(isFieldPresent({ description: "\n\t" }, "description")).toBe(false);
  });

  it("считает непустой description присутствующим", () => {
    expect(isFieldPresent({ description: "Ручная кофемолка" }, "description")).toBe(
      true,
    );
  });
});

describe("hasMissingDescription", () => {
  it("ложно, когда у всех карточек есть описание", () => {
    expect(
      hasMissingDescription([
        { title: "Телефон", description: "Описание" },
        { description: "Другое описание" },
      ]),
    ).toBe(false);
  });

  it("истинно, если хотя бы у одной карточки нет описания", () => {
    expect(
      hasMissingDescription([
        { title: "Телефон", description: "Описание" },
        { title: "Турка" },
      ]),
    ).toBe(true);
  });

  it("истинно, когда описание состоит только из пробелов", () => {
    expect(hasMissingDescription([{ description: "   " }])).toBe(true);
  });

  it("ложно для пустого набора карточек", () => {
    expect(hasMissingDescription([])).toBe(false);
  });
});
