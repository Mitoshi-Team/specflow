// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "../i18n";
import { useBatchExtract } from "../hooks/useBatchExtract";
import type { UseBatchExtractResult } from "../hooks/useBatchExtract";
import { useFileParser } from "../hooks/useFileParser";
import type { UseFileParserResult } from "../hooks/useFileParser";
import { readLastBatch, writeLastBatch } from "../lib/lastBatch";
import type { BatchExtractResponse } from "../schemas/api";
import PageHome from "./PageHome";

vi.mock("../hooks/useFileParser", () => ({
  useFileParser: vi.fn(),
}));

vi.mock("../hooks/useBatchExtract", () => ({
  useBatchExtract: vi.fn(),
}));

const useFileParserMock = vi.mocked(useFileParser);
const useBatchExtractMock = vi.mocked(useBatchExtract);

const IDLE: UseFileParserResult = {
  status: "idle",
  format: null,
  cards: [],
  error: null,
};

const SUCCESS: UseFileParserResult = {
  status: "success",
  format: "csv",
  cards: [
    {
      product_id: "sku-1",
      title: "Кофемолка",
      description: "Ручная кофемолка",
    },
  ],
  error: null,
};

const IDLE_BATCH: UseBatchExtractResult = {
  status: "idle",
  progress: { processed: 0, total: 0 },
  error: null,
  response: null,
  run: vi.fn().mockResolvedValue(undefined),
  reset: vi.fn(),
};

function fakeFile(name = "cards.csv"): File {
  return { name, size: 1024 } as unknown as File;
}

/** Показывает query текущего маршрута — фиксирует параметры перехода. */
function LocationProbe() {
  const location = useLocation();
  return (
    <div>
      <span>Страница результатов</span>
      <span>search:{location.search}</span>
    </div>
  );
}

function renderHome() {
  return render(
    <MemoryRouter>
      <PageHome />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  // Последний батч живёт в localStorage; изолируем тесты друг от друга.
  window.localStorage.clear();
  // Результат парсинга зависит от выбранного файла: без файла — idle.
  useFileParserMock.mockImplementation((file) => (file === null ? IDLE : SUCCESS));
  // Батч по умолчанию не запущен; отдельные тесты переопределяют состояние.
  useBatchExtractMock.mockReturnValue(IDLE_BATCH);
});

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});

describe("PageHome", () => {
  it("показывает панель загрузки до выбора файла", () => {
    renderHome();

    expect(screen.getByText("Загрузка карточек")).toBeDefined();
    expect(
      screen.getByText("Нажмите, чтобы выбрать файл"),
    ).toBeDefined();
    expect(screen.queryByText("Предпросмотр данных")).toBeNull();
  });

  it("показывает предпросмотр после успешного разбора файла", () => {
    renderHome();

    fireEvent.change(screen.getByLabelText("Выбор файла карточек"), {
      target: { files: [fakeFile()] },
    });

    expect(screen.getByText("Предпросмотр данных")).toBeDefined();
    expect(screen.getByText("cards.csv")).toBeDefined();
    expect(screen.getByText("Кофемолка")).toBeDefined();
  });

  it("возвращает страницу в исходное состояние после очистки файла", () => {
    renderHome();

    fireEvent.change(screen.getByLabelText("Выбор файла карточек"), {
      target: { files: [fakeFile()] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Убрать файл" }));

    expect(screen.queryByText("Предпросмотр данных")).toBeNull();
    expect(useFileParserMock).toHaveBeenLastCalledWith(null);
  });

  it("переключается на текстовый режим и показывает предпросмотр карточки", () => {
    renderHome();

    fireEvent.click(screen.getByRole("radio", { name: "Текст карточки" }));

    expect(screen.queryByLabelText("Выбор файла карточек")).toBeNull();
    expect(screen.queryByText("Предпросмотр данных")).toBeNull();

    fireEvent.change(screen.getByLabelText("Описание карточки"), {
      target: { value: "  Ручная кофемолка  " },
    });

    const preview = screen.getByText("Предпросмотр данных").closest("section");
    expect(preview).not.toBeNull();
    expect(
      within(preview as HTMLElement).getByText("Ручная кофемолка"),
    ).toBeDefined();
    expect(
      within(preview as HTMLElement).getByText("Текст карточки"),
    ).toBeDefined();
    expect(
      within(preview as HTMLElement).getByText("Карточек: 1"),
    ).toBeDefined();
  });

  it("делает текстовую карточку доступной для запуска батча", () => {
    renderHome();

    fireEvent.click(screen.getByRole("radio", { name: "Текст карточки" }));
    fireEvent.change(screen.getByLabelText("Описание карточки"), {
      target: { value: "Ручная кофемолка" },
    });

    expect(
      (screen.getByRole("button", { name: "Обработать" }) as HTMLButtonElement)
        .disabled,
    ).toBe(false);
  });

  it("возвращает загрузку файла при переключении режима обратно", () => {
    renderHome();

    fireEvent.click(screen.getByRole("radio", { name: "Текст карточки" }));
    fireEvent.change(screen.getByLabelText("Описание карточки"), {
      target: { value: "Ручная кофемолка" },
    });
    fireEvent.click(screen.getByRole("radio", { name: "Файл" }));

    expect(screen.getByLabelText("Выбор файла карточек")).toBeDefined();
    expect(screen.queryByLabelText("Описание карточки")).toBeNull();
    expect(screen.queryByText("Предпросмотр данных")).toBeNull();
    expect(
      (screen.getByRole("button", { name: "Обработать" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
  });

  it("не показывает кнопку «Новый батч», когда нечего сбрасывать", () => {
    const { container } = renderHome();

    expect(screen.queryByRole("button", { name: "Новый батч" })).toBeNull();
    // Без активной обработки оверлей загрузки не показывается.
    expect(container.querySelector(".loading-overlay")).toBeNull();
  });

  it("сбрасывает данные по кнопке «Новый батч» и возвращает экран загрузки", () => {
    renderHome();

    fireEvent.change(screen.getByLabelText("Выбор файла карточек"), {
      target: { files: [fakeFile()] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Новый батч" }));

    expect(screen.queryByText("Предпросмотр данных")).toBeNull();
    expect(useFileParserMock).toHaveBeenLastCalledWith(null);
  });

  it("сбрасывает текстовую карточку по кнопке «Новый батч»", () => {
    renderHome();

    fireEvent.click(screen.getByRole("radio", { name: "Текст карточки" }));
    fireEvent.change(screen.getByLabelText("Описание карточки"), {
      target: { value: "Ручная кофемолка" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Новый батч" }));

    expect(screen.queryByText("Предпросмотр данных")).toBeNull();
    expect(screen.getByLabelText("Выбор файла карточек")).toBeDefined();
  });

  it("показывает оверлей загрузки поверх страницы во время батча", () => {
    useBatchExtractMock.mockReturnValue({
      ...IDLE_BATCH,
      status: "running",
      progress: { processed: 0, total: 5 },
    });
    const { container } = renderHome();

    // Во время обработки поверх всего — крупный акцентный спиннер строго
    // по центру, без видимой подписи, вместо статусной строки в панели батча.
    const overlay = container.querySelector(".loading-overlay");
    expect(overlay).not.toBeNull();
    expect(
      within(overlay as HTMLElement).getByRole("status", {
        name: "Загрузка…",
      }),
    ).toBeDefined();
    expect(screen.queryByText("Загрузка…")).toBeNull();
    expect(screen.queryByText("Обрабатывается")).toBeNull();
    expect(screen.getByText("Обработано 0 из 5")).toBeDefined();
  });

  it("переходит на страницу результатов после успешного батча", async () => {
    const response: BatchExtractResponse = {
      total: 1,
      ok: 1,
      low_confidence: 0,
      errors: 0,
      results: [],
    };
    useBatchExtractMock.mockReturnValue({
      ...IDLE_BATCH,
      status: "success",
      progress: { processed: 1, total: 1 },
      response,
    });

    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<PageHome />} />
          <Route path="/results" element={<div>Страница результатов</div>} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("radio", { name: "Текст карточки" }));
    fireEvent.change(screen.getByLabelText("Описание карточки"), {
      target: { value: "Ручная кофемолка" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Обработать" }));

    expect(await screen.findByText("Страница результатов")).toBeDefined();
    // Результат сохранён для страницы результатов: держать его в
    // location.state нельзя — при переходе из навигации он теряется.
    const stored = readLastBatch();
    expect(stored?.response).toEqual(response);
    expect(stored?.cards).toEqual([{ description: "Ручная кофемолка" }]);
  });

  it("переходит по batch_id, когда сервер сохранил батч", async () => {
    useBatchExtractMock.mockReturnValue({
      ...IDLE_BATCH,
      status: "success",
      progress: { processed: 1, total: 1 },
      response: {
        total: 1,
        ok: 1,
        low_confidence: 0,
        errors: 0,
        results: [],
        batch_id: "b-42",
        persisted: true,
      },
    });

    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<PageHome />} />
          <Route path="/results" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("radio", { name: "Текст карточки" }));
    fireEvent.change(screen.getByLabelText("Описание карточки"), {
      target: { value: "Ручная кофемолка" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Обработать" }));

    // Страница результатов подтянет сохранённый серверный батч из истории.
    expect(await screen.findByText("search:?batch_id=b-42")).toBeDefined();
  });

  it("переходит на результаты без batch_id, если батч не сохранён", async () => {
    useBatchExtractMock.mockReturnValue({
      ...IDLE_BATCH,
      status: "success",
      progress: { processed: 1, total: 1 },
      response: {
        total: 1,
        ok: 1,
        low_confidence: 0,
        errors: 0,
        results: [],
        batch_id: "b-42",
        persisted: false,
      },
    });

    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<PageHome />} />
          <Route path="/results" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("radio", { name: "Текст карточки" }));
    fireEvent.change(screen.getByLabelText("Описание карточки"), {
      target: { value: "Ручная кофемолка" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Обработать" }));

    // persisted=false → без ссылки на серверную историю; локальная копия
    // остаётся фолбэком, страница результатов покажет предупреждение.
    expect(await screen.findByText("search:")).toBeDefined();
    expect(readLastBatch()?.response.persisted).toBe(false);
  });

  it("очищает сохранённый батч по кнопке «Новый батч»", () => {
    writeLastBatch({
      response: {
        total: 0,
        ok: 0,
        low_confidence: 0,
        errors: 0,
        results: [],
      },
    });
    renderHome();

    fireEvent.change(screen.getByLabelText("Выбор файла карточек"), {
      target: { files: [fakeFile()] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Новый батч" }));

    expect(readLastBatch()).toBeNull();
  });
});
