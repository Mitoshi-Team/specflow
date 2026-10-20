import { describe, expect, it } from "vitest";

import { formatDateTime, formatFileSize } from "./format";

describe("formatFileSize", () => {
  it("показывает байты без дробной части", () => {
    expect(formatFileSize(0)).toBe("0 B");
    expect(formatFileSize(512)).toBe("512 B");
  });

  it("переводит в килобайты с одним знаком после запятой", () => {
    expect(formatFileSize(1024)).toBe("1 KB");
    expect(formatFileSize(1536)).toBe("1.5 KB");
  });

  it("переводит в мегабайты для больших файлов", () => {
    expect(formatFileSize(5 * 1024 * 1024)).toBe("5 MB");
    expect(formatFileSize(1_572_864)).toBe("1.5 MB");
  });

  it("не ломается на некорректных значениях", () => {
    expect(formatFileSize(-1)).toBe("0 B");
    expect(formatFileSize(Number.NaN)).toBe("0 B");
  });
});

describe("formatDateTime", () => {
  const iso = "2026-10-20T12:00:00Z";

  it("форматирует дату в локали интерфейса", () => {
    // Эталон строится тем же Intl, что и в коде, — результат не зависит
    // от таймзоны машины, на которой идут тесты.
    const expected = new Intl.DateTimeFormat("en-US", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));

    expect(formatDateTime(iso, "en-US")).toBe(expected);
  });

  it("разные локали дают разное представление", () => {
    expect(formatDateTime(iso, "ru-RU")).not.toBe(
      formatDateTime(iso, "en-US"),
    );
  });

  it("некорректная строка возвращается как есть", () => {
    expect(formatDateTime("не дата", "ru-RU")).toBe("не дата");
  });
});
