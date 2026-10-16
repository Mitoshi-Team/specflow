// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "../i18n";
import ConfidenceBadge from "./ConfidenceBadge";

afterEach(cleanup);

describe("ConfidenceBadge", () => {
  it("показывает числовое значение уверенности", () => {
    render(<ConfidenceBadge confidence={0.95} />);

    expect(screen.getByText("0.95")).toBeDefined();
  });

  it("не помечает значение без заданного порога", () => {
    render(<ConfidenceBadge confidence={0.5} />);

    expect(screen.queryByText("ниже порога")).toBeNull();
  });

  it("помечает значение ниже порога текстом, а не только цветом", () => {
    const { container } = render(
      <ConfidenceBadge confidence={0.5} threshold={0.8} />,
    );

    expect(screen.getByText("ниже порога")).toBeDefined();
    expect(container.querySelector(".confidence--low")).not.toBeNull();
  });

  it("не помечает значение, равное порогу", () => {
    const { container } = render(
      <ConfidenceBadge confidence={0.8} threshold={0.8} />,
    );

    expect(screen.queryByText("ниже порога")).toBeNull();
    expect(container.querySelector(".confidence--low")).toBeNull();
  });

  it("не помечает значение выше порога", () => {
    const { container } = render(
      <ConfidenceBadge confidence={0.9} threshold={0.8} />,
    );

    expect(screen.queryByText("ниже порога")).toBeNull();
    expect(container.querySelector(".confidence--low")).toBeNull();
  });
});
