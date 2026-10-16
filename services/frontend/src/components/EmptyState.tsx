export type EmptyStateProps = {
  /** Локализованный текст пустого состояния (i18n на стороне вызывающего). */
  message: string;
};

/**
 * Явное пустое состояние (frontend.md, раздел 6.2 `EmptyState`;
 * design.md, раздел 7). Регион `status` оповещает скринридер
 * (design.md, раздел 11).
 */
export default function EmptyState({ message }: EmptyStateProps) {
  return (
    <p className="empty-state" role="status">
      {message}
    </p>
  );
}
