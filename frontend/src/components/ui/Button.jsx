export default function Button({
  children,
  variant = "default",
  size = "md",
  onClick,
  disabled,
  className = "",
  type = "button",
  title,
}) {
  const base =
    "inline-flex items-center justify-center gap-1.5 font-medium transition-colors focus:outline-none focus:ring-1 focus:ring-[var(--ring)] disabled:opacity-40 disabled:pointer-events-none select-none";

  const variants = {
    default:
      "bg-[var(--primary)] text-[var(--primary-foreground)] hover:bg-teal-300",
    secondary:
      "bg-[var(--secondary)] text-[var(--secondary-foreground)] border border-[var(--border)] hover:bg-[var(--muted)] hover:text-[var(--foreground)]",
    ghost:
      "text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)]",
    danger:
      "bg-red-900/30 text-red-400 border border-red-900/50 hover:bg-red-900/50",
  };

  const sizes = {
    sm: "h-7 px-2.5 text-xs rounded-[var(--radius)]",
    md: "h-8 px-3 text-sm rounded-[var(--radius)]",
    lg: "h-10 px-4 text-sm rounded-[var(--radius)]",
    icon: "h-8 w-8 rounded-[var(--radius)]",
  };

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`${base} ${variants[variant]} ${sizes[size]} ${className}`}
    >
      {children}
    </button>
  );
}
