// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "../i18n";
import FileUpload from "./FileUpload";
import type { FileUploadProps } from "./FileUpload";

afterEach(cleanup);

function renderUpload(props: Partial<FileUploadProps> = {}) {
  const onFileSelect = vi.fn();
  render(
    <FileUpload status="idle" onFileSelect={onFileSelect} {...props} />,
  );
  const input = screen.getByLabelText("Выбор файла карточек") as HTMLInputElement;
  const dropzone = input.closest("label") as HTMLLabelElement;
  return { onFileSelect, input, dropzone };
}

function fakeFile(name: string): File {
  return { name } as unknown as File;
}

describe("FileUpload", () => {
  it("в состоянии ожидания показывает приглашение выбрать файл", () => {
    renderUpload();

    expect(screen.getByRole("status").textContent).toContain(
      "Нажмите, чтобы выбрать файл",
    );
  });

  it("не поддерживает перетаскивание: drop не выбирает файл", () => {
    const { onFileSelect, dropzone } = renderUpload();
    const file = fakeFile("cards.csv");

    fireEvent.drop(dropzone, { dataTransfer: { files: [file] } });

    expect(onFileSelect).not.toHaveBeenCalled();
  });

  it("передаёт файл, выбранный через input", () => {
    const { onFileSelect, input } = renderUpload();
    const file = fakeFile("cards.json");

    fireEvent.change(input, { target: { files: [file] } });

    expect(onFileSelect).toHaveBeenCalledWith(file);
  });

  it("в состоянии обработки блокирует input и показывает прогресс", () => {
    const { input } = renderUpload({ status: "parsing" });

    expect(screen.getByRole("status").textContent).toContain("Обработка файла…");
    expect(input.disabled).toBe(true);
  });

  it("в состоянии успеха показывает имя файла и число карточек", () => {
    renderUpload({
      status: "success",
      fileName: "cards.csv",
      cardCount: 3,
      onClear: vi.fn(),
    });

    const status = screen.getByRole("status").textContent ?? "";
    expect(status).toContain("cards.csv");
    expect(status).toContain("Карточек: 3");
    expect(screen.getByRole("button", { name: "Убрать файл" })).toBeDefined();
  });

  it("вызывает onClear по кнопке сброса", () => {
    const onClear = vi.fn();
    renderUpload({ status: "success", fileName: "cards.csv", onClear });

    fireEvent.click(screen.getByRole("button", { name: "Убрать файл" }));

    expect(onClear).toHaveBeenCalledTimes(1);
  });

  it("в состоянии ошибки переводит код ошибки и номер строки", () => {
    renderUpload({ status: "error", error: { code: "noContent", row: 3 } });

    const status = screen.getByRole("status").textContent ?? "";
    expect(status).toContain(
      "Строка не содержит title, description или seller_attributes",
    );
    expect(status).toContain("Строка 3");
  });

  it("блокирует input при disabled", () => {
    const { input } = renderUpload({ disabled: true });

    expect(input.disabled).toBe(true);
  });
});
