export default function Card({ children, className = "", onClick }) {
  return (
    <div
      onClick={onClick}
      className={`bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius)] ${onClick ? "cursor-pointer hover:border-[var(--muted-foreground)]/40 transition-colors" : ""} ${className}`}
    >
      {children}
    </div>
  );
}
