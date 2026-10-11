import { useState } from "react";
import Badge from "../ui/Badge";

const TYPE_CONFIG = {
  retrieval: { color: "text-blue-400", bg: "bg-blue-950/50 border-blue-900/50", dot: "bg-blue-400" },
  reason: { color: "text-violet-400", bg: "bg-violet-950/50 border-violet-900/50", dot: "bg-violet-400" },
  answer: { color: "text-teal-400", bg: "bg-teal-950/50 border-teal-900/50", dot: "bg-teal-400" },
  tool: { color: "text-amber-400", bg: "bg-amber-950/50 border-amber-900/50", dot: "bg-amber-400" },
};

const STATUS_ICON = {
  success: (
    <svg width="10" height="10" viewBox="0 0 12 12" fill="none">
      <circle cx="6" cy="6" r="5.5" stroke="currentColor" strokeWidth="1"/>
      <path d="M3.5 6l2 2 3-3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  warning: (
    <svg width="10" height="10" viewBox="0 0 12 12" fill="none">
      <path d="M6 1L11 10H1L6 1z" stroke="currentColor" strokeWidth="1"/>
      <path d="M6 5v2.5M6 9h.01" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  ),
};

export default function ToolCallStep({ step, isLast }) {
  const [expanded, setExpanded] = useState(false);
  const cfg = TYPE_CONFIG[step.type] || TYPE_CONFIG.tool;

  return (
    <div className="flex gap-3">
      {/* Timeline */}
      <div className="flex flex-col items-center flex-shrink-0 w-4">
        <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${cfg.dot}`} />
        {!isLast && <div className="w-px flex-1 bg-[var(--border)] mt-1" />}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 pb-4">
        <button
          onClick={() => setExpanded((v) => !v)}
          className="w-full text-left group"
        >
          <div className="flex items-center gap-2 mb-0.5">
            <span className={`font-mono text-[10px] font-semibold uppercase tracking-wider ${cfg.color}`}>
              {step.tool}
            </span>
            <span className={`text-[var(--${step.status === "warning" ? "amber" : "teal"}-400)] opacity-70`}>
              {STATUS_ICON[step.status]}
            </span>
            <span className="font-mono text-[10px] text-[var(--muted-foreground)] ml-auto">
              {step.duration}ms
            </span>
          </div>
          <p className="text-xs font-medium text-[var(--foreground)] group-hover:text-[var(--primary)] transition-colors">
            {step.label}
          </p>
          <p className="text-[10px] text-[var(--muted-foreground)] font-mono mt-0.5 truncate">
            {step.detail}
          </p>
        </button>

        {expanded && (
          <div className={`mt-2 px-2.5 py-2 rounded border text-[11px] font-mono text-[var(--muted-foreground)] leading-relaxed ${cfg.bg}`}>
            <span className="text-[var(--muted-foreground)] opacity-60 text-[9px] block mb-0.5">{step.timestamp}</span>
            {step.result}
          </div>
        )}
      </div>
    </div>
  );
}
