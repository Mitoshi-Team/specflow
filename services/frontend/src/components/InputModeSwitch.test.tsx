// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "../i18n";
import InputModeSwitch from "./InputModeSwitch";

afterEach(cleanup);

describe("InputModeSwitch", () => {
  it("показывает обе опции и отмечает выбранный режим", () => {
    render(<InputModeSwitch value="text" onChange={vi.fn()} />);

    const file = screen.getByRole("radio", { name: "Файл" }) as HTMLInputElement;
    const text = screen.getByRole("radio", {
      name: "Текст карточки",
    }) as HTMLInputElement;

    expect(file.checked).toBe(false);
    expect(text.checked).toBe(true);
  });

  it("передаёт выбранный режим через onChange", () => {
    const onChange = vi.fn();
    render(<InputModeSwitch value="file" onChange={onChange} />);

    fireEvent.click(screen.getByRole("radio", { name: "Текст карточки" }));

    expect(onChange).toHaveBeenCalledWith("text");
  });

  it("блокирует переключение при disabled", () => {
    render(<InputModeSwitch value="file" onChange={vi.fn()} disabled />);

    // jsdom диспатчит синтетический click на disabled-элемент напрямую
    // (реальный браузер событие не порождает), поэтому проверяем состояние
    // контролов, а не отсутствие вызова onChange.
    expect(
      (screen.getByRole("radio", { name: "Файл" }) as HTMLInputElement).disabled,
    ).toBe(true);
    expect(
      (screen.getByRole("radio", { name: "Текст карточки" }) as HTMLInputElement)
        .disabled,
    ).toBe(true);
  });
});
