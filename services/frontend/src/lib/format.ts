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

/**
 * Дата и время из ISO-строки сервера в формате локали пользователя.
 *
 * Локаль передаётся из i18n (язык интерфейса), поэтому даты истории батчей
 * отображаются в привычном для пользователя виде. Некорректная строка
 * возвращается как есть — показать сырые данные честнее, чем молча скрыть.
 */
export function formatDateTime(iso: string, locale: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}
