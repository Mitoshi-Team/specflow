// @vitest-environment jsdom
import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "../i18n";
import { CARD_TEXT_MAX_HEIGHT_PX, CARD_TEXT_MIN_HEIGHT_PX } from "../constants";
import CardTextInput from "./CardTextInput";

afterEach(cleanup);

/** Управляемый компонент: обёртка с состоянием для проверки ввода. */
function Harness({ onClear }: { onClear?: () => void }) {
  const [value, setValue] = useState("");
  return <CardTextInput value={value} onChange={setValue} onClear={onClear} />;
}

describe("CardTextInput", () => {
  it("в состоянии ожидания показывает подсказку и не предлагает сброс", () => {
    render(<CardTextInput value="" onChange={vi.fn()} onClear={vi.fn()} />);

    expect(screen.getByLabelText("Описание карточки")).toBeDefined();
    expect(screen.getByRole("status").textContent).toBe(
      "Вставьте описание карточки",
    );
    expect(screen.queryByRole("button", { name: "Очистить текст" })).toBeNull();
  });

  it("переходит в состояние готовности при вводе текста", () => {
    render(<Harness onClear={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Описание карточки"), {
      target: { value: "Ручная кофемолка" },
    });

    const textarea = screen.getByLabelText(
      "Описание карточки",
    ) as HTMLTextAreaElement;
    expect(textarea.value).toBe("Ручная кофемолка");
    expect(screen.getByRole("status").textContent).toBe(
      "Карточка готова к обработке",
    );
    expect(
      screen.getByRole("button", { name: "Очистить текст" }),
    ).toBeDefined();
  });

  it("считает текст из одних пробелов пустым вводом", () => {
    render(<CardTextInput value="   " onChange={vi.fn()} onClear={vi.fn()} />);

    expect(screen.getByRole("status").textContent).toBe(
      "Вставьте описание карточки",
    );
    expect(screen.queryByRole("button", { name: "Очистить текст" })).toBeNull();
  });

  it("вызывает onClear и возвращается в исходное состояние", () => {
    const onClear = vi.fn();
    render(<CardTextInput value="Текст" onChange={vi.fn()} onClear={onClear} />);

    fireEvent.click(screen.getByRole("button", { name: "Очистить текст" }));

    expect(onClear).toHaveBeenCalledTimes(1);
  });

  it("блокирует поле ввода при disabled", () => {
    render(<CardTextInput value="" onChange={vi.fn()} disabled />);

    expect(
      (screen.getByLabelText("Описание карточки") as HTMLTextAreaElement)
        .disabled,
    ).toBe(true);
  });

  it("растёт по содержимому в пределах допустимой высоты", () => {
    render(<Harness onClear={vi.fn()} />);
    const textarea = screen.getByLabelText(
      "Описание карточки",
    ) as HTMLTextAreaElement;

    const setScrollHeight = (height: number): void => {
      Object.defineProperty(textarea, "scrollHeight", {
        value: height,
        configurable: true,
      });
    };

    // Короткий текст — минимальная высота.
    setScrollHeight(40);
    fireEvent.change(textarea, { target: { value: "Одна строка" } });
    expect(textarea.style.height).toBe(`${CARD_TEXT_MIN_HEIGHT_PX}px`);

    // Средний текст — высота по содержимому.
    setScrollHeight(300);
    fireEvent.change(textarea, { target: { value: "Несколько строк" } });
    expect(textarea.style.height).toBe("300px");

    // Очень длинный текст упирается в максимум, дальше — внутренний скролл.
    setScrollHeight(2000);
    fireEvent.change(textarea, { target: { value: "Много строк" } });
    expect(textarea.style.height).toBe(`${CARD_TEXT_MAX_HEIGHT_PX}px`);
  });
});
