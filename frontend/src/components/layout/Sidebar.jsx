import { useMemo } from "react";

const NAV_ITEMS = [
  { id: "chat", label: "Chat", icon: "💬", page: "chat" },
  { id: "eval", label: "Eval", icon: "📊", page: "eval" },
  { id: "files", label: "File Manager", icon: "📁", page: "files" },
];

function formatRelativeTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
  if (seconds < 60) return "Just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
  return date.toLocaleDateString([], { month: "short", day: "numeric" });
}

export default function Sidebar({
  currentPage,
  onNavigate,
  user,
  conversations = [],
  conversationsLoading = false,
  activeConversationId,
  onConversationSelect,
  onNewChat,
  onConversationDelete,
  deletingConversationId,
}) {
  const initials = useMemo(() => {
    const name = user?.full_name?.trim() || user?.email || "User";
    return name.split(/[\s@._-]+/).filter(Boolean).slice(0, 2)
      .map((part) => part[0].toUpperCase()).join("");
  }, [user]);

  return (
    <aside className="w-56 flex-shrink-0 flex flex-col border-r border-[var(--border)] bg-[var(--card)] h-full">
      <div className="h-12 flex items-center px-4 border-b border-[var(--border)]">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-[var(--primary)] flex items-center justify-center">
            <span className="text-[10px] font-bold text-[var(--primary-foreground)]">DP</span>
          </div>
          <span className="text-sm font-semibold tracking-tight text-[var(--foreground)]">DocPilot</span>
        </div>
      </div>

      <nav className="px-2 pt-3 pb-2 flex flex-col gap-0.5">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onNavigate(item.page)}
            className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded text-sm transition-colors text-left ${
              currentPage === item.page
                ? "bg-[var(--muted)] text-[var(--foreground)]"
                : "text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)]"
            }`}
          >
            <span className="text-base leading-none">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>

      <div className="mx-3 border-t border-[var(--border)]" />

      <div className="px-3 pt-3 flex-1 overflow-y-auto min-h-0">
        <div className="flex items-center justify-between gap-2 px-1.5 mb-2">
          <p className="text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
            Recent chats
          </p>
          <button
            type="button"
            onClick={onNewChat}
            title="Start a new chat"
            aria-label="Start a new chat"
            className="text-lg leading-none text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            +
          </button>
        </div>


        {conversationsLoading ? (
          <p className="px-2.5 py-3 text-xs text-[var(--muted-foreground)]">Loading conversations…</p>
        ) : conversations.length === 0 ? (
          <p className="px-2.5 py-3 text-xs leading-relaxed text-[var(--muted-foreground)]">
            No saved conversations yet. Start a chat to create one.
          </p>
        ) : (
          <div className="flex flex-col gap-0.5">
            {conversations.map((conversation) => {
              const selected = activeConversationId === conversation.id && currentPage === "chat";
              return (
                <div
                  key={conversation.id}
                  className={`group flex items-start gap-1 rounded ${
                    selected
                      ? "bg-[var(--muted)] text-[var(--foreground)]"
                      : "text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)]"
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => {
                      onConversationSelect(conversation.id);
                      onNavigate("chat");
                    }}
                    title={conversation.title}
                    className="flex-1 min-w-0 text-left px-2.5 py-2"
                  >
                    <p className="text-xs font-medium truncate leading-tight">
                      {conversation.title || "New conversation"}
                    </p>
                    <p className="text-[10px] text-[var(--muted-foreground)] mt-0.5">
                      {formatRelativeTime(conversation.updated_at)}
                      {Number(conversation.message_count) > 0 ? ` · ${conversation.message_count} messages` : ""}
                    </p>
                  </button>
                  <button
                    type="button"
                    onClick={() => onConversationDelete?.(conversation)}
                    disabled={deletingConversationId === conversation.id}
                    aria-label={`Delete conversation ${conversation.title || ""}`}
                    title="Delete conversation"
                    className="mt-1 mr-1 rounded px-1.5 py-1 text-xs text-[var(--muted-foreground)] hover:bg-red-500/10 hover:text-red-400 disabled:opacity-50"
                  >
                    {deletingConversationId === conversation.id ? "…" : "×"}
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="p-3 border-t border-[var(--border)]">
        <div className="flex items-center gap-2 px-1 min-w-0">
          <div className="w-6 h-6 flex-shrink-0 rounded-full bg-[var(--secondary)] border border-[var(--border)] flex items-center justify-center text-[10px] text-[var(--muted-foreground)]">
            {initials}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-[var(--foreground)] truncate">
              {user?.full_name || user?.email || "Signed-in user"}
            </p>
            <p className="text-[10px] text-[var(--muted-foreground)] truncate">{user?.email || ""}</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
