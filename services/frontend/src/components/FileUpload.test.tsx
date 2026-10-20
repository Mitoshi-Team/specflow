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

  it("выбирает файл при перетаскивании в область", () => {
    const { onFileSelect, dropzone } = renderUpload();
    const file = fakeFile("cards.csv");

    fireEvent.drop(dropzone, { dataTransfer: { files: [file] } });

    expect(onFileSelect).toHaveBeenCalledWith(file);
  });

  it("подсвечивает область при перетаскивании и снимает подсветку", () => {
    const { dropzone } = renderUpload();

    fireEvent.dragOver(dropzone);
    expect(dropzone.className).toContain("file-upload__zone--dragover");

    fireEvent.dragLeave(dropzone);
    expect(dropzone.className).not.toContain("file-upload__zone--dragover");
  });

  it("игнорирует перетаскивание, когда взаимодействие заблокировано", () => {
    const { onFileSelect, dropzone } = renderUpload({ disabled: true });
    const file = fakeFile("cards.csv");

    fireEvent.drop(dropzone, { dataTransfer: { files: [file] } });

    expect(onFileSelect).not.toHaveBeenCalled();
  });

  it("игнорирует drop без файлов", () => {
    const { onFileSelect, dropzone } = renderUpload();

    fireEvent.drop(dropzone, { dataTransfer: { files: [] } });

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
    expect(status).toContain("Файл не содержит столбца description");
    expect(status).toContain("Строка 3");
  });
  it("в состоянии ошибки подсказывает, что исправить", () => {
    renderUpload({ status: "error", error: { code: "unsupportedFormat" } });

    expect(
      screen.getByText(
        "Сохраните данные в формате CSV, JSON или TSV и выберите файл снова.",
      ),
    ).toBeDefined();
  });

  it("не показывает подсказку об ошибке вне состояния error", () => {
    renderUpload({ status: "idle" });

    expect(screen.queryByText(/Сохраните данные в формате/)).toBeNull();
  });

  it("блокирует input при disabled", () => {
    const { input } = renderUpload({ disabled: true });

    expect(input.disabled).toBe(true);
  });
});
