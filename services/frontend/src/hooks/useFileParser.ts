import { useEffect, useState } from "react";

import {
  parseFile,
  type FileFormat,
  type FileParseError,
} from "../lib/fileParser";
import type { ProductCardRequest } from "../schemas/api";

/** Состояние разбора файла. `idle` — файл не выбран. */
export type FileParserStatus = "idle" | "parsing" | "success" | "error";

export type UseFileParserResult = {
  status: FileParserStatus;
  format: FileFormat | null;
  cards: ProductCardRequest[];
  error: FileParseError | null;
};

const IDLE_RESULT: UseFileParserResult = {
  status: "idle",
  format: null,
  cards: [],
  error: null,
};

/**
 * Разбирает переданный файл и возвращает результат либо типизированную
 * ошибку (`useFileParser`, frontend.md, раздел 7).
 *
 * При смене файла запускается новый разбор; результат устаревшего разбора
 * игнорируется. `null` переводит хук в состояние `idle`.
 */
export function useFileParser(file: File | null): UseFileParserResult {
  const [result, setResult] = useState<UseFileParserResult>(IDLE_RESULT);

  useEffect(() => {
    if (file === null) {
      setResult(IDLE_RESULT);
      return;
    }

    let cancelled = false;
    setResult({ status: "parsing", format: null, cards: [], error: null });

    void parseFile(file).then((parsed) => {
      if (cancelled) {
        return;
      }
      if (parsed.ok) {
        setResult({
          status: "success",
          format: parsed.format,
          cards: parsed.cards,
          error: null,
        });
      } else {
        setResult({
          status: "error",
          format: null,
          cards: [],
          error: parsed.error,
        });
      }
    });

    return () => {
      cancelled = true;
    };
  }, [file]);

  return result;
}
