import { useState } from "react";
import { api } from "../lib/api";
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
  const [downloadError, setDownloadError] = useState("");

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

  async function handleDownloadPdf(messageId) {
    if (!organizationId || !conversationId) {
      setDownloadError("Save or select a conversation before exporting.");
      return;
    }

    setDownloadError("");

    try {
      const blob = await api.downloadChatMessagePdf(
        organizationId,
        conversationId,
        messageId,
      );
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `docpilot-answer-${messageId}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      setDownloadError(err.message || "Unable to download the PDF.");
    }
  }

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
            error={downloadError || error}
            onDownloadPdf={handleDownloadPdf}
          />
          <AgentTraceView trace={activeTrace} visible={traceVisible} />
        </div>

        <SourcesPanel sources={sources} visible={sourcesVisible} />
      </div>
    </div>
  );
}
