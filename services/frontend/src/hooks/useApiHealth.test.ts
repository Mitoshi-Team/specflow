// @vitest-environment jsdom
import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getHealth } from "../api";
import type { HealthResponse, HealthStatus } from "../schemas/api";
import { useApiHealth } from "./useApiHealth";

vi.mock("../api", () => ({
  getHealth: vi.fn(),
}));

const getHealthMock = vi.mocked(getHealth);

function healthResponse(status: HealthStatus): HealthResponse {
  return {
    status,
    version: "1.0.0",
    pipeline_version: "0.1.0",
    uptime_seconds: 1,
    models_loaded: [],
    cache_enabled: true,
  };
}

/** Даёт разрешиться микрозадачам, запущенным хуком. */
async function flush(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  getHealthMock.mockReset();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("useApiHealth", () => {
  it("начинает в состоянии loading", () => {
    getHealthMock.mockResolvedValue(healthResponse("ok"));

    const { result } = renderHook(() => useApiHealth(1000));

    expect(result.current).toBe("loading");
  });

  it("отражает статус из /health после успешной проверки", async () => {
    getHealthMock.mockResolvedValue(healthResponse("degraded"));

    const { result } = renderHook(() => useApiHealth(1000));
    await flush();

    expect(result.current).toBe("degraded");
  });

  it("переходит в error при сбое запроса", async () => {
    getHealthMock.mockRejectedValue(new Error("network"));

    const { result } = renderHook(() => useApiHealth(1000));
    await flush();

    expect(result.current).toBe("error");
  });

  it("повторяет проверку с заданным интервалом и обновляет состояние", async () => {
    getHealthMock.mockResolvedValue(healthResponse("ok"));

    const { result } = renderHook(() => useApiHealth(1000));
    await flush();

    expect(getHealthMock).toHaveBeenCalledTimes(1);
    expect(result.current).toBe("ok");

    getHealthMock.mockResolvedValue(healthResponse("down"));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(getHealthMock).toHaveBeenCalledTimes(2);
    expect(result.current).toBe("down");
  });

  it("останавливает опрос при размонтировании", async () => {
    getHealthMock.mockResolvedValue(healthResponse("ok"));

    const { unmount } = renderHook(() => useApiHealth(1000));
    await flush();
    unmount();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });

    expect(getHealthMock).toHaveBeenCalledTimes(1);
  });
});
