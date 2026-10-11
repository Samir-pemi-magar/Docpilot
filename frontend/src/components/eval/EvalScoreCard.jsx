import Card from "../ui/Card";

export default function EvalScoreCard({ label, value, format = "pct", delta }) {
  const display =
    format === "pct"
      ? `${Math.round(value * 100)}%`
      : format === "count"
      ? value
      : value.toFixed(2);

  const deltaColor =
    delta === undefined
      ? ""
      : delta >= 0
      ? "text-teal-400"
      : "text-red-400";

  return (
    <Card className="px-4 py-3 flex flex-col gap-1">
      <p className="text-[10px] font-mono uppercase tracking-wider text-[var(--muted-foreground)]">
        {label}
      </p>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-semibold tabular-nums text-[var(--foreground)]">{display}</span>
        {delta !== undefined && (
          <span className={`text-xs font-mono ${deltaColor}`}>
            {delta >= 0 ? "+" : ""}{Math.round(delta * 100)}%
          </span>
        )}
      </div>
    </Card>
  );
}
