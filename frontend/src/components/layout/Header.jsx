import Button from "../ui/Button";

export default function Header({ title, onToggleTrace, onToggleSources, traceVisible, sourcesVisible }) {
  return (
    <header className="h-12 flex items-center justify-between px-4 border-b border-[var(--border)] flex-shrink-0">
      <div className="flex items-center gap-3">
        <h1 className="text-sm font-semibold text-[var(--foreground)]">{title}</h1>
      </div>
      <div className="flex items-center gap-1.5">
        {onToggleTrace && (
          <Button
            variant={traceVisible ? "secondary" : "ghost"}
            size="sm"
            onClick={onToggleTrace}
            title="Toggle agent trace"
          >
            <svg width="13" height="13" viewBox="0 0 16 16" fill="none" className="opacity-70">
              <path d="M8 1v14M1 8h14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              <circle cx="8" cy="4" r="1.5" fill="currentColor"/>
              <circle cx="8" cy="8" r="1.5" fill="currentColor"/>
              <circle cx="8" cy="12" r="1.5" fill="currentColor"/>
            </svg>
            Trace
          </Button>
        )}
        {onToggleSources && (
          <Button
            variant={sourcesVisible ? "secondary" : "ghost"}
            size="sm"
            onClick={onToggleSources}
            title="Toggle sources panel"
          >
            <svg width="13" height="13" viewBox="0 0 16 16" fill="none" className="opacity-70">
              <rect x="1" y="1" width="6" height="14" rx="1" stroke="currentColor" strokeWidth="1.5"/>
              <rect x="9" y="1" width="6" height="14" rx="1" stroke="currentColor" strokeWidth="1.5"/>
            </svg>
            Sources
          </Button>
        )}
      </div>
    </header>
  );
}
