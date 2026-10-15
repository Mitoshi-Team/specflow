/**
 * Форматирование значений для отображения в интерфейсе.
 */

const SIZE_UNITS = ["B", "KB", "MB", "GB"] as const;

/** Размер файла в человекочитаемом виде: `12.3 KB`, `1.5 MB`. */
export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) {
    return "0 B";
  }

  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < SIZE_UNITS.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  const digits = unitIndex === 0 || Number.isInteger(value) ? 0 : 1;
  return `${value.toFixed(digits)} ${SIZE_UNITS[unitIndex]}`;
}
