// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../api";
import type { BatchProgress, BatchStatus } from "../hooks/useBatchExtract";
import type { BatchExtractResponse, ProductCardRequest } from "../schemas/api";
import "../i18n";
import BatchControls from "./BatchControls";
import type { BatchControlsProps } from "./BatchControls";

afterEach(cleanup);

const CARDS: ProductCardRequest[] = [{ title: "Кофемолка" }];
const IDLE_PROGRESS: BatchProgress = { processed: 0, total: 0 };

function renderControls(props: Partial<BatchControlsProps> = {}) {
  const onStart = vi.fn().mockResolvedValue(undefined);
  const onReset = vi.fn();
  render(
    <BatchControls
      cards={CARDS}
      status="idle"
      progress={IDLE_PROGRESS}
      error={null}
      response={null}
      onStart={onStart}
      onReset={onReset}
      {...props}
    />,
  );
  return { onStart, onReset };
}

function button(name: string): HTMLButtonElement {
  return screen.getByRole("button", { name }) as HTMLButtonElement;
}

function input(label: string): HTMLInputElement {
  return screen.getByLabelText(label) as HTMLInputElement;
}

function successResponse(errors = 0): BatchExtractResponse {
  return {
    total: 3,
    ok: 3 - errors,
    low_confidence: 0,
    errors,
    results: [],
    processing_time_ms_total: 100,
  };
}

describe("BatchControls", () => {
  it("показывает настройки по умолчанию и статус ожидания", () => {
    renderControls();

    expect(input("Размер батча").value).toBe("1");
    expect(input("Порог уверенности").value).toBe("0.8");
    expect(screen.getByRole("status").textContent).toBe("Ожидает запуска");
    expect(screen.queryByRole("progressbar")).toBeNull();
  });

  it("запускает батч с текущими настройками", () => {
    const { onStart } = renderControls();

    fireEvent.change(input("Размер батча"), { target: { value: "20" } });
    fireEvent.click(button("Обработать"));

    expect(onStart).toHaveBeenCalledWith(CARDS, {
      batchSize: 20,
      thresholdOverride: 0.8,
    });
  });

  it("блокирует запуск, когда нет валидных карточек", () => {
    const { onStart } = renderControls({ cards: [] });

    expect(button("Обработать").disabled).toBe(true);
    expect(screen.getByText("Нет валидных карточек для обработки")).toBeDefined();
    expect(onStart).not.toHaveBeenCalled();
  });

  it("блокирует запуск и показывает ошибку диапазона при неверной настройке", () => {
    renderControls();

    fireEvent.change(input("Размер батча"), { target: { value: "99" } });

    expect(button("Обработать").disabled).toBe(true);
    expect(input("Размер батча").getAttribute("aria-invalid")).toBe("true");
    expect(
      screen.getByText("Значение вне диапазона от 1 до 50"),
    ).toBeDefined();
  });

  it("считает очищенный размер батча невалидным", () => {
    renderControls();

    fireEvent.change(input("Размер батча"), { target: { value: "" } });

    expect(input("Размер батча").getAttribute("aria-invalid")).toBe("true");
    expect(
      screen.getByText("Значение вне диапазона от 1 до 50"),
    ).toBeDefined();
  });

  it("блокирует запуск и показывает ошибку при пороге вне диапазона", () => {
    renderControls();

    fireEvent.change(input("Порог уверенности"), { target: { value: "1.5" } });

    expect(button("Обработать").disabled).toBe(true);
    expect(input("Порог уверенности").getAttribute("aria-invalid")).toBe("true");
    expect(screen.getByText("Значение вне диапазона от 0 до 1")).toBeDefined();
  });

  it("считает очищенный порог невалидным, а не нулевым", () => {
    const { onStart } = renderControls();

    // Пустое поле браузер отдаёт и при вводе мусора в input[type=number];
    // без проверки Number("") === 0 делал бы такой порог валидным.
    fireEvent.change(input("Порог уверенности"), { target: { value: "" } });

    expect(input("Порог уверенности").getAttribute("aria-invalid")).toBe("true");
    expect(screen.getByText("Значение вне диапазона от 0 до 1")).toBeDefined();
    expect(button("Обработать").disabled).toBe(true);

    fireEvent.click(button("Обработать"));
    expect(onStart).not.toHaveBeenCalled();
  });

  it("в состоянии выполнения блокирует контролы и показывает прогресс", () => {
    const status: BatchStatus = "running";
    renderControls({
      status,
      progress: { processed: 0, total: 5 },
    });

    expect(screen.getByRole("status").textContent).toBe("Обрабатывается");
    expect(screen.getByText("Обработано 0 из 5")).toBeDefined();
    expect(button("Обработать").disabled).toBe(true);
    expect(button("Сброс").disabled).toBe(true);
    expect(input("Размер батча").disabled).toBe(true);

    const bar = screen.getByRole("progressbar");
    expect(bar.getAttribute("aria-valuenow")).toBeNull();
    expect(bar.className).toContain("batch__bar--indeterminate");
  });

  it("показывает завершённый прогресс после успеха", () => {
    renderControls({
      status: "success",
      progress: { processed: 3, total: 3 },
      response: successResponse(),
    });

    expect(screen.getByRole("status").textContent).toBe("Завершён");
    expect(screen.getByText("Обработано 3 из 3")).toBeDefined();
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe(
      "3",
    );
    expect(button("Обработать").disabled).toBe(false);
    expect(button("Сброс").disabled).toBe(false);
  });

  it("показывает частичные ошибки завершённого батча", () => {
    renderControls({
      status: "success",
      progress: { processed: 3, total: 3 },
      response: successResponse(2),
    });

    expect(screen.getByRole("status").textContent).toBe(
      "Завершён с ошибками",
    );
    expect(screen.getByText("Ошибок обработки: 2")).toBeDefined();
  });

  it("показывает ошибку API в формате контракта", () => {
    const error = new ApiError({
      status: 422,
      message: "api.errors.http",
      detail: "Некорректный запрос",
      errors: [
        { loc: ["body", "items"], msg: "too many", type: "value_error" },
      ],
    });
    renderControls({ status: "error", error, progress: { processed: 0, total: 3 } });

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("Сервер вернул ошибку");
    expect(alert.textContent).toContain("HTTP 422");
    expect(alert.textContent).toContain("Некорректный запрос");
    expect(alert.textContent).toContain("body.items: too many");
    expect(screen.getByRole("status").textContent).toBe("Ошибка");
    expect(screen.getByText("Обработано 0 из 3")).toBeDefined();
  });

  it("сбрасывает состояние по кнопке «Сброс»", () => {
    const { onReset } = renderControls({
      status: "success",
      progress: { processed: 3, total: 3 },
      response: successResponse(),
    });

    fireEvent.click(button("Сброс"));

    expect(onReset).toHaveBeenCalledTimes(1);
  });

  it("блокирует «Сброс» в состоянии ожидания", () => {
    renderControls();

    expect(button("Сброс").disabled).toBe(true);
  });
});
