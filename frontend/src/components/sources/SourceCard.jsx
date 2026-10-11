import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function displayMarkdown(value = "") {
  // The indexed Markdown excerpts may contain backslash-escaped
  // punctuation. Undo that escaping for display only.
  return value.replace(/\\([\\`*_{}[\]()#+.!|>~-])/g, "$1");
}

function MarkdownExcerpt({ text }) {
  return (
    <div className="text-xs leading-relaxed break-words [&_p]:my-2 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0 [&_strong]:font-semibold [&_ul]:list-disc [&_ul]:pl-4 [&_ol]:list-decimal [&_ol]:pl-4 [&_li]:my-1 [&_h1]:font-semibold [&_h2]:font-semibold [&_h3]:font-semibold [&_table]:w-full [&_table]:border-collapse [&_th]:font-semibold [&_th]:text-left [&_th]:p-1 [&_td]:p-1 [&_th]:border [&_td]:border [&_th]:border-[var(--border)] [&_td]:border-[var(--border)] [&_blockquote]:border-l-2 [&_blockquote]:border-[var(--border)] [&_blockquote]:pl-2 [&_code]:font-mono [&_code]:text-[11px]">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {displayMarkdown(text)}
      </ReactMarkdown>
    </div>
  );
}

export default function SourceCard({ source, rank }) {
  const [expanded, setExpanded] = useState(false);
  const chunks = source.chunks || [];
  const preview = displayMarkdown(chunks[0]?.text || "")
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/[#>*_`|~-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  return (
    <article className="rounded-lg border border-[var(--border)] bg-[var(--background)] overflow-hidden">
      <div className="p-3">
        <div className="flex items-start gap-2">
          <div className="w-8 h-8 rounded-md bg-[var(--secondary)] flex items-center justify-center flex-shrink-0">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              className="w-4 h-4 text-[var(--muted-foreground)]"
              aria-hidden="true"
            >
              <path d="M6 3.75h8l4 4v12.5H6z" />
              <path d="M14 3.75v4h4M9 12h6M9 15.5h6" />
            </svg>
          </div>

          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold leading-relaxed text-[var(--foreground)] break-words">
              {source.name}
            </p>
            <p className="mt-1 text-[10px] text-[var(--muted-foreground)]">
              Source {rank}
              {chunks.length > 1 ? ` · ${chunks.length} excerpts` : ""}
            </p>
          </div>
        </div>

        <p className="mt-2 text-xs leading-relaxed text-[var(--muted-foreground)]">
          {preview
            ? `${preview.slice(0, 150)}${preview.length > 150 ? "…" : ""}`
            : "Relevant information from this document."}
        </p>

        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          aria-expanded={expanded}
          className="mt-3 flex items-center gap-1.5 text-xs font-medium text-[var(--primary)] hover:opacity-80"
        >
          {expanded ? "Hide excerpts" : "View excerpts"}
          <svg
            viewBox="0 0 20 20"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            className={`w-3.5 h-3.5 transition-transform ${expanded ? "rotate-180" : ""}`}
            aria-hidden="true"
          >
            <path d="m5 7.5 5 5 5-5" />
          </svg>
        </button>
      </div>

      {expanded && (
        <div className="border-t border-[var(--border)] p-3 space-y-4">
          {chunks.map((chunk, index) => (
            <section key={chunk.chunk_id || `${source.id}-${index}`}>
              {chunks.length > 1 && (
                <p className="mb-2 text-[10px] font-medium text-[var(--muted-foreground)]">
                  Excerpt {index + 1}
                </p>
              )}
              <MarkdownExcerpt text={chunk.text || ""} />
            </section>
          ))}
        </div>
      )}
    </article>
  );
}
