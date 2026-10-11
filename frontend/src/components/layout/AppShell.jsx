import Sidebar from "./Sidebar";

export default function AppShell({
  currentPage,
  onNavigate,
  children,
  user,
  conversations,
  conversationsLoading,
  activeConversationId,
  onConversationSelect,
  onNewChat,
  onConversationDelete,
  deletingConversationId,
}) {
  return (
    <div className="flex h-screen overflow-hidden bg-[var(--background)]">
      <Sidebar
        currentPage={currentPage}
        onNavigate={onNavigate}
        user={user}
        conversations={conversations}
        conversationsLoading={conversationsLoading}
        activeConversationId={activeConversationId}
        onConversationSelect={onConversationSelect}
        onNewChat={onNewChat}
        onConversationDelete={onConversationDelete}
        deletingConversationId={deletingConversationId}
      />
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {children}
      </main>
    </div>
  );
}
