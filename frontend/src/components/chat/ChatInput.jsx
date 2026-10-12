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
      textareaRef.current.style.height = "44px";
    }
  }

  function handleInput(e) {
    setValue(e.target.value);

    const el = textareaRef.current;
    if (el) {
      el.style.height = "44px";
      el.style.height = Math.min(el.scrollHeight, 160) + "px";
    }
  }

  return (
    <div className="relative z-10 shrink-0 border-t-2 border-[var(--border)] bg-[var(--card)] px-3 py-4 shadow-[0_-6px_20px_rgba(0,0,0,0.08)] sm:px-5 sm:py-5">
      {!disabled && value === "" && (
        <div className="mb-3 flex flex-wrap gap-2">
          {SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => {
                setValue(suggestion);
                textareaRef.current?.focus();
              }}
              className="max-w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-xs font-medium text-[var(--foreground)] transition-colors hover:border-[var(--ring)] hover:bg-[var(--background)] sm:text-sm"
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="rounded-2xl border-2 border-[var(--muted-foreground)]/50 bg-[var(--background)] p-2 shadow-sm transition-colors focus-within:border-[var(--ring)] focus-within:ring-2 focus-within:ring-[var(--ring)]/20"
      >
        <div className="flex items-end gap-3">
          <textarea
            ref={textareaRef}
            rows={2}
            value={value}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            aria-label="Message"
            placeholder="Ask a question about your documents..."
            className="min-h-[44px] max-h-40 min-w-0 flex-1 resize-none bg-transparent px-3 py-2.5 text-base leading-relaxed text-[var(--foreground)] outline-none placeholder:text-[var(--muted-foreground)] disabled:cursor-not-allowed disabled:opacity-60"
            style={{ height: "44px" }}
          />

          <Button
            onClick={submit}
            disabled={disabled || !value.trim()}
            size="sm"
            variant="default"
            className="mb-0.5 flex min-h-[44px] shrink-0 items-center gap-2 px-4 text-sm font-semibold"
          >
            <span>Send</span>
            <svg
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="none"
              aria-hidden="true"
            >
              <path
                d="M2 8h12M9 3l5 5-5 5"
                stroke="currentColor"
                strokeWidth="1.7"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </Button>
        </div>
      </form>

      <div className="mt-2 flex flex-wrap items-center justify-between gap-1 px-1 text-xs text-[var(--muted-foreground)]">
        <span>Ask about your organization's documents</span>
        <span>
          <kbd className="rounded border border-[var(--border)] px-1.5 py-0.5 font-mono">
            Enter
          </kbd>{" "}
          to send ·{" "}
          <kbd className="rounded border border-[var(--border)] px-1.5 py-0.5 font-mono">
            Shift+Enter
          </kbd>{" "}
          for a new line
        </span>
      </div>
    </div>
  );
}
