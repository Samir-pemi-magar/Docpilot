export default function StreamingIndicator({ text }) {
  return (
    <div className="px-4 py-2">
      <div className="flex items-start gap-3 max-w-[88%]">
        <div className="w-6 h-6 rounded bg-[var(--primary)]/20 border border-[var(--primary)]/30 flex items-center justify-center flex-shrink-0 mt-0.5">
          <span className="text-[10px] font-bold text-[var(--primary)]">DP</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm text-[var(--foreground)] leading-relaxed">
            {text ? (
              <span>
                {text}
                <span className="inline-block w-0.5 h-3.5 bg-[var(--primary)] ml-0.5 animate-pulse align-middle" />
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-[var(--muted-foreground)]">
                <span className="flex gap-0.5">
                  <span className="w-1 h-1 rounded-full bg-[var(--muted-foreground)] animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-1 h-1 rounded-full bg-[var(--muted-foreground)] animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-1 h-1 rounded-full bg-[var(--muted-foreground)] animate-bounce" style={{ animationDelay: "300ms" }} />
                </span>
                <span className="text-xs font-mono">Retrieving context…</span>
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
