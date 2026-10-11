import { useState } from "react";

export function Tabs({ tabs, defaultTab, onChange, className = "" }) {
  const [active, setActive] = useState(defaultTab || tabs[0]?.id);

  function handleSelect(id) {
    setActive(id);
    onChange?.(id);
  }

  return (
    <div className={`flex items-center gap-1 border-b border-[var(--border)] ${className}`}>
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => handleSelect(tab.id)}
          className={`px-3 py-2 text-sm font-medium transition-colors relative -mb-px border-b-2 ${
            active === tab.id
              ? "text-[var(--foreground)] border-[var(--primary)]"
              : "text-[var(--muted-foreground)] border-transparent hover:text-[var(--foreground)]"
          }`}
        >
          {tab.label}
          {tab.badge !== undefined && (
            <span className="ml-1.5 text-xs font-mono text-[var(--muted-foreground)]">
              {tab.badge}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
