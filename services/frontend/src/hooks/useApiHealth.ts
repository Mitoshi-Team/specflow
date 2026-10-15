import { useEffect, useState } from "react";

import { getHealth } from "../api";
import { API_HEALTH_POLL_INTERVAL_MS } from "../constants";

/**
 * Состояние индикатора здоровья API.
 *
 * `loading` — первый запрос ещё не завершился; `ok`/`degraded`/`down` —
 * статусы из HealthResponse (api_contract.md, раздел 3.7); `error` — запрос
 * не удался (сеть или ответ, не соответствующий контракту).
 */
export type ApiHealthState = "loading" | "ok" | "degraded" | "down" | "error";

/**
 * Периодически проверяет доступность API через `GET /api/v1/health`.
 *
 * Проверка выполняется сразу при монтировании, затем с заданным интервалом.
 * При размонтировании незавершённый запрос отменяется, а таймер очищается.
 */
export function useApiHealth(
  intervalMs: number = API_HEALTH_POLL_INTERVAL_MS,
): ApiHealthState {
  const [state, setState] = useState<ApiHealthState>("loading");

  useEffect(() => {
    const controller = new AbortController();

    const check = async (): Promise<void> => {
      try {
        const health = await getHealth(controller.signal);
        if (!controller.signal.aborted) {
          setState(health.status);
        }
      } catch {
        if (!controller.signal.aborted) {
          setState("error");
        }
      }
    };

    void check();
    const timer = window.setInterval(() => void check(), intervalMs);

    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, [intervalMs]);

  return state;
}
