import SourceCard from "./SourceCard";

export default function SourcesPanel({ sources = [], visible }) {
  if (!visible) return null;

  const grouped = new Map();

  sources.forEach((source, index) => {
    const key =
      source.document_id ||
      source.document_version_id ||
      source.document_name ||
      `source-${index}`;

    if (!grouped.has(key)) {
      grouped.set(key, {
        id: key,
        name: source.document_name || "Retrieved document",
        chunks: [],
      });
    }

    grouped.get(key).chunks.push(source);
  });

  const documents = [...grouped.values()];

  return (
    <aside className="w-72 flex-shrink-0 flex flex-col border-l border-[var(--border)] bg-[var(--card)] overflow-hidden">
      <div className="min-h-12 flex items-center justify-between gap-2 px-4 border-b border-[var(--border)] flex-shrink-0">
        <div>
          <h2 className="text-sm font-semibold text-[var(--foreground)]">
            Sources
          </h2>
          <p className="text-[10px] text-[var(--muted-foreground)]">
            Documents used for this answer
          </p>
        </div>
        <span className="text-xs text-[var(--muted-foreground)]">
          {documents.length}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto">
        {documents.length === 0 ? (
          <p className="px-4 py-5 text-xs leading-relaxed text-[var(--muted-foreground)]">
            Sources will appear here when relevant documents are found.
          </p>
        ) : (
          <div className="p-2 space-y-2">
            {documents.map((document, index) => (
              <SourceCard
                key={document.id}
                source={document}
                rank={index + 1}
              />
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}
