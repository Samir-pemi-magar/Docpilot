export default function Badge({ children, variant = "default", className = "" }) {
  const variants = {
    default: "bg-[var(--secondary)] text-[var(--secondary-foreground)] border border-[var(--border)]",
    pass: "bg-teal-950/60 text-teal-400 border border-teal-900/50",
    fail: "bg-red-950/60 text-red-400 border border-red-900/50",
    partial: "bg-amber-950/60 text-amber-400 border border-amber-900/50",
    accent: "bg-teal-950/60 text-teal-300 border border-teal-800/50",
    mono: "bg-[var(--muted)] text-[var(--muted-foreground)] border border-[var(--border)] font-mono",
  };

  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${variants[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
