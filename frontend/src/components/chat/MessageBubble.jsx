import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Badge from "../ui/Badge";

export default function MessageBubble({ message }) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end px-4 py-2">
        <div className="max-w-[70%] min-w-0">
          <div className="bg-[var(--secondary)] border border-[var(--border)] rounded-[var(--radius)] px-3.5 py-2.5 text-sm text-[var(--foreground)] whitespace-pre-wrap break-words">
            {message.content}
          </div>
          {message.timestamp && (
            <p className="text-[10px] text-[var(--muted-foreground)] mt-1 text-right font-mono">
              {message.timestamp}
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="px-4 py-2">
      <div className="flex items-start gap-3 max-w-[88%]">
        <div className="w-6 h-6 rounded bg-[var(--primary)]/20 border border-[var(--primary)]/30 flex items-center justify-center flex-shrink-0 mt-0.5">
          <span className="text-[10px] font-bold text-[var(--primary)]">DP</span>
        </div>

        <div className="flex-1 min-w-0">
          <div className="text-sm text-[var(--foreground)] leading-relaxed break-words [&_p]:my-2 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0 [&_strong]:font-semibold [&_em]:italic [&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:my-1 [&_h1]:text-lg [&_h1]:font-semibold [&_h1]:my-3 [&_h2]:text-base [&_h2]:font-semibold [&_h2]:my-3 [&_h3]:font-semibold [&_h3]:my-2 [&_a]:text-[var(--primary)] [&_a]:underline [&_blockquote]:border-l-2 [&_blockquote]:border-[var(--border)] [&_blockquote]:pl-3 [&_blockquote]:my-2 [&_code]:font-mono [&_code]:text-xs [&_code]:bg-[var(--secondary)] [&_code]:rounded [&_code]:px-1 [&_pre]:overflow-x-auto [&_pre]:rounded [&_pre]:bg-[var(--secondary)] [&_pre]:p-3 [&_pre]:my-2 [&_table]:w-full [&_table]:text-left [&_table]:border-collapse [&_th]:border [&_th]:border-[var(--border)] [&_th]:p-2 [&_td]:border [&_td]:border-[var(--border)] [&_td]:p-2">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                a: ({ children, ...props }) => (
                  <a {...props} target="_blank" rel="noopener noreferrer">
                    {children}
                  </a>
                ),
              }}
            >
              {message.content ?? ""}
            </ReactMarkdown>
          </div>

          {message.citations?.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {message.citations.map((citation) => (
                <Badge key={citation.ref} variant="mono" className="text-[10px]">
                  [{citation.ref}] {citation.sourceId}
                </Badge>
              ))}
            </div>
          )}

          {message.timestamp && (
            <p className="text-[10px] text-[var(--muted-foreground)] mt-1.5 font-mono">
              {message.timestamp}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
