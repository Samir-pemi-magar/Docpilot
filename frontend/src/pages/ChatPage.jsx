import Header from "../components/layout/Header";
import ChatView from "../components/chat/ChatView";
import SourcesPanel from "../components/sources/SourcesPanel";
import AgentTraceView from "../components/trace/AgentTraceView";
import { useMockChat } from "../hooks/useMockChat";

export default function ChatPage({
  organizationId,
  conversationId = null,
  onConversationChange,
  onConversationsChanged,
}) {
  const {
    messages,
    isStreaming,
    streamingText,
    sources,
    activeTrace,
    traceVisible,
    sourcesVisible,
    error,
    sendMessage,
    toggleTrace,
    toggleSources,
  } = useMockChat(
    organizationId,
    conversationId,
    onConversationChange,
    onConversationsChanged,
  );

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <Header
        title="Organization chat"
        onToggleTrace={toggleTrace}
        onToggleSources={toggleSources}
        traceVisible={traceVisible}
        sourcesVisible={sourcesVisible}
      />

      <div className="flex flex-1 min-h-0">
        <div className="flex flex-col flex-1 min-w-0 min-h-0">
          <ChatView
            messages={messages}
            isStreaming={isStreaming}
            streamingText={streamingText}
            onSend={sendMessage}
            error={error}
          />
          <AgentTraceView trace={activeTrace} visible={traceVisible} />
        </div>

        <SourcesPanel sources={sources} visible={sourcesVisible} />
      </div>
    </div>
  );
}
