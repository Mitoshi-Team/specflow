// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "../i18n";
import StatusLegend from "./StatusLegend";

afterEach(cleanup);

/**
 * Кнопка раскрытия легенды: вся строка заголовка (текст + галочка).
 * Раздел свёрнут по умолчанию.
 */
function legendToggle() {
  return screen.getByRole("button", { name: "Как читать результаты" });
}

/** Раскрывает легенду (и возвращает кнопку в новом состоянии). */
function expandLegend() {
  const toggle = screen.getByRole("button", { name: "Как читать результаты" });
  fireEvent.click(toggle);
  return toggle;
}

describe("StatusLegend", () => {
  it("свёрнут по умолчанию", () => {
    render(<StatusLegend threshold={0.8} />);

    expect(legendToggle().getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText(/Порог уверенности батча/)).toBeNull();
    expect(screen.queryByText("Низкая уверенность")).toBeNull();
  });

  it("разворачивает и снова сворачивает раздел по клику на заголовок", () => {
    render(<StatusLegend threshold={0.8} />);

    const toggle = expandLegend();
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText(/Порог уверенности батча: 0\.8/)).toBeDefined();

    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText(/Порог уверенности батча/)).toBeNull();
  });

  it("делает заголовок и галочку одной кнопкой-раскрытием", () => {
    render(<StatusLegend threshold={0.8} />);
    const toggle = legendToggle();

    // Кликабельна вся строка заголовка, а не только шеврон: кнопка содержит
    // и текст заголовка (он же её accessible name), и декоративную галочку.
    expect(toggle.textContent).toBe("Как читать результаты");
    expect(toggle.querySelector('[aria-hidden="true"]')).not.toBeNull();
    expect(toggle.getAttribute("aria-label")).toBeNull();
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
  });

  it("связывает кнопку раскрытия с раскрытым содержимым", () => {
    render(<StatusLegend threshold={0.8} />);

    const toggle = expandLegend();

    const contentId = toggle.getAttribute("aria-controls");
    expect(contentId).not.toBeNull();
    expect(document.getElementById(contentId ?? "")).not.toBeNull();
  });

  it("поясняет порог уверенности его значением", () => {
    render(<StatusLegend threshold={0.8} />);
    expandLegend();

    expect(screen.getByText(/Порог уверенности батча: 0\.8/)).toBeDefined();
  });

  it("без заданного порога показывает общее пояснение", () => {
    render(<StatusLegend />);
    expandLegend();

    expect(
      screen.getByText(/Значения ниже порога уверенности подсвечены/),
    ).toBeDefined();
  });

  it("расшифровывает низкую уверенность действием для пользователя", () => {
    render(<StatusLegend threshold={0.8} />);
    expandLegend();

    expect(
      screen.getByText(
        "Часть значений ниже порога — проверьте их вручную перед использованием.",
      ),
    ).toBeDefined();
  });

  it("показывает подписи всех статусов карточек", () => {
    render(<StatusLegend threshold={0.8} />);
    expandLegend();

    for (const label of [
      "Успешно",
      "Низкая уверенность",
      "Частично",
      "Ошибка",
      "Пропущено",
    ]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
  });

  it("поясняет служебные колонки таблицы", () => {
    render(<StatusLegend threshold={0.8} />);
    expandLegend();

    expect(screen.getByText(/«Ниже порога»/)).toBeDefined();
    expect(screen.getByText(/«Проверка»/)).toBeDefined();
  });
});
