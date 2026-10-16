// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "../i18n";
import { useFileParser } from "../hooks/useFileParser";
import type { UseFileParserResult } from "../hooks/useFileParser";
import PageHome from "./PageHome";

vi.mock("../hooks/useFileParser", () => ({
  useFileParser: vi.fn(),
}));

const useFileParserMock = vi.mocked(useFileParser);

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

function fakeFile(name = "cards.csv"): File {
  return { name, size: 1024 } as unknown as File;
}

function renderHome() {
  return render(
    <MemoryRouter>
      <PageHome />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  // Результат парсинга зависит от выбранного файла: без файла — idle.
  useFileParserMock.mockImplementation((file) => (file === null ? IDLE : SUCCESS));
});

afterEach(cleanup);

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
    renderHome();

    expect(screen.queryByRole("button", { name: "Новый батч" })).toBeNull();
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
});
