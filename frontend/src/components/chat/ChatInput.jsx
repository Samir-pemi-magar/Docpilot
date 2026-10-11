import { useState, useRef } from "react";
import Button from "../ui/Button";

const SUGGESTIONS = [
  "Summarize the key points in my documents.",
  "What procedures or policies are documented?",
  "Find important requirements and explain them.",
];

export default function ChatInput({ onSend, disabled }) {
  const [value, setValue] = useState("");
  const textareaRef = useRef(null);

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }

  function handleInput(e) {
    setValue(e.target.value);
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 120) + "px";
    }
  }

  return (
    <div className="border-t border-[var(--border)] bg-[var(--background)] px-4 py-3">
      {/* Suggestion chips */}
      {!disabled && value === "" && (
        <div className="flex gap-1.5 mb-2 flex-wrap">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => { setValue(s); textareaRef.current?.focus(); }}
              className="text-[10px] font-mono px-2 py-1 rounded border border-[var(--border)] text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:border-[var(--muted-foreground)]/40 transition-colors truncate max-w-xs"
            >
              {s.length > 48 ? s.slice(0, 48) + "…" : s}
            </button>
          ))}
        </div>
      )}

      {/* Input row */}
      <div className="flex items-end gap-2 bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius)] px-3 py-2 focus-within:border-[var(--ring)]/50 transition-colors">
        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder="Ask about your documents…"
          className="flex-1 bg-transparent text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] resize-none outline-none leading-relaxed min-h-[22px]"
          style={{ height: "22px" }}
        />
        <Button
          onClick={submit}
          disabled={disabled || !value.trim()}
          size="sm"
          variant="default"
          className="flex-shrink-0"
        >
          <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
            <path d="M2 8h12M9 3l5 5-5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </Button>
      </div>

      <p className="text-[10px] text-[var(--muted-foreground)] mt-1.5 px-0.5">
        Ask questions about your organization's documents · <span className="font-mono">Shift+Enter</span> for newline
      </p>
    </div>
  );
}
