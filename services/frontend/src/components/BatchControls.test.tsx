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
  const onResetAll = vi.fn();
  render(
    <BatchControls
      cards={CARDS}
      status="idle"
      progress={IDLE_PROGRESS}
      error={null}
      response={null}
      onStart={onStart}
      onResetAll={onResetAll}
      {...props}
    />,
  );
  return { onStart, onResetAll };
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
  it("показывает настройки по умолчанию без статусной строки", () => {
    renderControls();

    expect(input("Порог уверенности").value).toBe("0.8");
    // Размер батча больше не настраивается: он определяется числом карточек.
    expect(screen.queryByLabelText("Размер батча")).toBeNull();
    // Текстовый статус со страницы убран: во время обработки состояние
    // показывает оверлей загрузки на уровне страницы (PageHome).
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.queryByRole("progressbar")).toBeNull();
  });

  it("запускает батч с текущими настройками", () => {
    const { onStart } = renderControls();

    fireEvent.click(button("Обработать"));

    expect(onStart).toHaveBeenCalledWith(CARDS, { thresholdOverride: 0.8 });
  });

  it("блокирует запуск, когда нет валидных карточек", () => {
    const { onStart } = renderControls({ cards: [] });

    expect(button("Обработать").disabled).toBe(true);
    expect(screen.getByText("Нет валидных карточек для обработки")).toBeDefined();
    expect(onStart).not.toHaveBeenCalled();
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

    // Статусная строка убрана — остаётся только прогресс и блокировка
    // контролов; спиннер во время выполнения показывает оверлей PageHome.
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.getByText("Обработано 0 из 5")).toBeDefined();
    expect(button("Обработать").disabled).toBe(true);
    expect(button("Сброс").disabled).toBe(true);
    expect(input("Порог уверенности").disabled).toBe(true);

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
    expect(screen.getByText("Обработано 0 из 3")).toBeDefined();
  });

  it("сбрасывает порог и внешние данные по кнопке «Сброс»", () => {
    const { onResetAll } = renderControls();

    // Порог изменён, значит «Сброс» активен (есть что возвращать).
    fireEvent.change(input("Порог уверенности"), { target: { value: "0.4" } });
    fireEvent.click(button("Сброс"));

    expect(input("Порог уверенности").value).toBe("0.8");
    expect(onResetAll).toHaveBeenCalledTimes(1);
  });

  it("сбрасывает порог, когда загружены карточки", () => {
    renderControls();

    // Карточки есть, а порог по умолчанию: кнопка всё равно нужна, чтобы
    // очистить файл/текст страницы.
    expect(button("Сброс").disabled).toBe(false);

    fireEvent.change(input("Порог уверенности"), { target: { value: "0.4" } });
    fireEvent.click(button("Сброс"));

    expect(input("Порог уверенности").value).toBe("0.8");
  });

  it("блокирует «Сброс», когда нечего сбрасывать", () => {
    renderControls({ cards: [] });

    // Нет ни карточек, ни изменённого порога — сбрасывать нечего.
    expect(button("Сброс").disabled).toBe(true);
  });
});
