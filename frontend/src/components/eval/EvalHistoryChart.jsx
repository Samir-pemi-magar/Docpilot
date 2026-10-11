import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import Card from "../ui/Card";

function formatDate(value) {
  if (!value) return "Unknown date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown date";
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const item = payload[0].payload;
  return (
    <div className="rounded border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 text-[var(--muted-foreground)]">{label}</p>
      <p className="font-semibold text-[var(--primary)]">
        Hit rate@k: {(item.hitRate * 100).toFixed(1)}%
      </p>
      <p className="mt-1 text-[var(--muted-foreground)]">
        {item.completedCases}/{item.totalCases} cases completed
      </p>
      <p className="mt-1 font-mono text-[10px] text-[var(--muted-foreground)]">
        Run {item.id.slice(0, 8)}
      </p>
    </div>
  );
}

export default function EvalHistoryChart({ runs = [] }) {
  const data = runs
    .filter(
      (run) =>
        run.status === "completed" &&
        typeof run.metrics?.hit_rate_at_k === "number" &&
        Number.isFinite(run.metrics.hit_rate_at_k) &&
        Number(run.metrics.retrieval_evaluated_cases || 0) > 0
    )
    .slice(0, 6)
    .reverse()
    .map((run) => ({
      id: run.id,
      date: formatDate(run.completed_at || run.created_at),
      hitRate: run.metrics.hit_rate_at_k,
      completedCases: run.completed_cases,
      totalCases: run.total_cases,
    }));

  return (
    <Card className="p-4">
      <div className="mb-4 flex items-center justify-between gap-3">
        <p className="text-xs font-semibold text-[var(--foreground)]">
          Retrieval hit rate@k
        </p>
        <span className="text-[10px] text-[var(--muted-foreground)]">
          Up to 6 completed runs
        </span>
      </div>
      {!data.length ? (
        <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">
          No completed runs with retrieval relevance labels yet. Add relevant
          document IDs to evaluation questions and run an evaluation to track
          retrieval hit rate.
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
            <CartesianGrid
              strokeDasharray="2 4"
              stroke="var(--border)"
              vertical={false}
            />
            <XAxis
              dataKey="date"
              tick={{ fill: "var(--muted-foreground)", fontSize: 10 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              domain={[0, 1]}
              tickFormatter={(value) => `${Math.round(value * 100)}%`}
              tick={{ fill: "var(--muted-foreground)", fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              tickCount={5}
            />
            <Tooltip content={<CustomTooltip />} />
            <Line
              type="monotone"
              dataKey="hitRate"
              name="Hit rate@k"
              stroke="var(--primary)"
              strokeWidth={2}
              dot={{
                r: 3,
                fill: "var(--background)",
                stroke: "var(--primary)",
                strokeWidth: 1.5,
              }}
              activeDot={{
                r: 4,
                fill: "var(--primary)",
                stroke: "var(--background)",
                strokeWidth: 2,
              }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
      <p className="mt-2 text-xs text-[var(--muted-foreground)]">
        Hit rate measures how often at least one relevant document appears in
        the top-k retrieved results. It does not measure answer correctness.
      </p>
    </Card>
  );
}
