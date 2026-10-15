// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "../i18n";
import { useApiHealth } from "../hooks/useApiHealth";
import type { ApiHealthState } from "../hooks/useApiHealth";
import Header from "./Header";

vi.mock("../hooks/useApiHealth", () => ({
  useApiHealth: vi.fn(),
}));

const useApiHealthMock = vi.mocked(useApiHealth);

function renderHeader() {
  return render(
    <MemoryRouter>
      <Header />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  useApiHealthMock.mockReset();
});

afterEach(() => {
  cleanup();
});

describe("Header", () => {
  it.each<[ApiHealthState, string]>([
    ["loading", "проверяется…"],
    ["ok", "доступен"],
    ["degraded", "ограниченно"],
    ["down", "недоступен"],
    ["error", "нет связи"],
  ])("показывает состояние API «%s» как «%s»", (state, expected) => {
    useApiHealthMock.mockReturnValue(state);

    renderHeader();

    expect(screen.getByRole("status").textContent).toContain(expected);
  });
});
