// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "../i18n";
import StatusLegend from "./StatusLegend";

afterEach(cleanup);

describe("StatusLegend", () => {
  it("поясняет порог уверенности его значением", () => {
    render(<StatusLegend threshold={0.8} />);

    expect(screen.getByText(/Порог уверенности батча: 0\.8/)).toBeDefined();
  });

  it("без заданного порога показывает общее пояснение", () => {
    render(<StatusLegend />);

    expect(
      screen.getByText(/Значения ниже порога уверенности подсвечены/),
    ).toBeDefined();
  });

  it("расшифровывает низкую уверенность действием для пользователя", () => {
    render(<StatusLegend threshold={0.8} />);

    expect(
      screen.getByText(
        "Часть значений ниже порога — проверьте их вручную перед использованием.",
      ),
    ).toBeDefined();
  });

  it("показывает подписи всех статусов карточек", () => {
    render(<StatusLegend threshold={0.8} />);

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

    expect(screen.getByText(/«Ниже порога»/)).toBeDefined();
    expect(screen.getByText(/«Проверка»/)).toBeDefined();
  });
});
