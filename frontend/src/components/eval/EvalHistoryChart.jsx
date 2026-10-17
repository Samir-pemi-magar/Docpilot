import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
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

function formatPercentage(value) {
  return typeof value === "number" && Number.isFinite(value)
    ? `${(value * 100).toFixed(1)}%`
    : "N/A";
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;

  const item = payload[0].payload;

  return (
    <div className="rounded border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-xs shadow-lg">
      <p className="mb-2 font-semibold text-[var(--foreground)]">{label}</p>

      <p style={{ color: "var(--primary)" }}>
        Hit rate@k: {formatPercentage(item.hitRate)}
      </p>

      <p style={{ color: "#16a34a" }} className="mt-1">
        Recall@k: {formatPercentage(item.recall)}
      </p>

      <p style={{ color: "#d97706" }} className="mt-1">
        Mean reciprocal rank: {formatPercentage(item.reciprocalRank)}
      </p>

      <p className="mt-2 text-[var(--muted-foreground)]">
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
    .filter((run) => {
      if (run.status !== "completed") return false;
      if (Number(run.metrics?.retrieval_evaluated_cases || 0) <= 0) {
        return false;
      }

      return [
        run.metrics?.hit_rate_at_k,
        run.metrics?.recall_at_k,
        run.metrics?.reciprocal_rank,
      ].some(
        (value) => typeof value === "number" && Number.isFinite(value)
      );
    })
    .slice(0, 6)
    .reverse()
    .map((run) => ({
      id: run.id,
      date: formatDate(run.completed_at || run.created_at),
      hitRate:
        typeof run.metrics?.hit_rate_at_k === "number" &&
        Number.isFinite(run.metrics.hit_rate_at_k)
          ? run.metrics.hit_rate_at_k
          : null,
      recall:
        typeof run.metrics?.recall_at_k === "number" &&
        Number.isFinite(run.metrics.recall_at_k)
          ? run.metrics.recall_at_k
          : null,
      reciprocalRank:
        typeof run.metrics?.reciprocal_rank === "number" &&
        Number.isFinite(run.metrics.reciprocal_rank)
          ? run.metrics.reciprocal_rank
          : null,
      completedCases: run.completed_cases,
      totalCases: run.total_cases,
    }));

  return (
    <Card className="p-4">
      <div className="mb-4 flex items-center justify-between gap-3">
        <p className="text-xs font-semibold text-[var(--foreground)]">
          Retrieval metrics
        </p>
        <span className="text-[10px] text-[var(--muted-foreground)]">
          Up to 6 completed runs
        </span>
      </div>

      {!data.length ? (
        <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">
          No completed runs with retrieval relevance labels yet. Add relevant
          document IDs to evaluation questions and run an evaluation to track
          retrieval metrics.
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <LineChart
            data={data}
            margin={{ top: 4, right: 12, bottom: 0, left: -16 }}
          >
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

            <Legend
              verticalAlign="bottom"
              height={32}
              wrapperStyle={{ fontSize: "11px" }}
            />

            <Line
              type="monotone"
              dataKey="hitRate"
              name="Hit rate@k"
              stroke="var(--primary)"
              strokeWidth={2}
              connectNulls={false}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
            />

            <Line
              type="monotone"
              dataKey="recall"
              name="Recall@k"
              stroke="#16a34a"
              strokeWidth={2}
              connectNulls={false}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
            />

            <Line
              type="monotone"
              dataKey="reciprocalRank"
              name="Mean reciprocal rank"
              stroke="#d97706"
              strokeWidth={2}
              connectNulls={false}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}

      <p className="mt-2 text-xs text-[var(--muted-foreground)]">
        Hit rate measures how often at least one relevant document appears in
        the top-k results. Recall measures how many relevant documents are
        retrieved. Mean reciprocal rank rewards retrieving the first relevant
        document near the top. These are retrieval metrics, not direct measures
        of answer correctness.
      </p>
    </Card>
  );
}
