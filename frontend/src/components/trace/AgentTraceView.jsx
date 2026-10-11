import ToolCallStep from "./ToolCallStep";

export default function AgentTraceView({ trace, visible }) {
  if (!visible) return null;

  const steps = Array.isArray(trace) ? trace : [];
  const totalDuration = steps.reduce(
    (sum, step) => sum + (Number(step.duration) || 0),
    0,
  );

  return (
    <div className="border-t border-[var(--border)] bg-[var(--card)] flex-shrink-0">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[var(--border)]">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-[var(--foreground)]">
            Agent Trace
          </span>
          <span className="font-mono text-[10px] text-[var(--muted-foreground)]">
            {steps.length} steps
          </span>
        </div>
        {steps.length > 0 && (
          <span className="font-mono text-[10px] text-[var(--muted-foreground)]">
            {totalDuration}ms total
          </span>
        )}
      </div>

      {steps.length === 0 ? (
        <div className="px-4 py-4">
          <p className="text-xs text-[var(--muted-foreground)]">
            No trace data is available for this request yet.
          </p>
        </div>
      ) : (
        <div className="px-4 pt-3 pb-1 max-h-56 overflow-y-auto">
          {steps.map((step, index) => (
            <ToolCallStep
              key={step.id ?? `${step.name ?? "step"}-${index}`}
              step={step}
              isLast={index === steps.length - 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}
