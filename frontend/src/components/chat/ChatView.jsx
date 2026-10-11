import { useEffect, useRef } from "react";
import MessageBubble from "./MessageBubble";
import StreamingIndicator from "./StreamingIndicator";
import ChatInput from "./ChatInput";

export default function ChatView({ messages, isStreaming, streamingText, onSend, error }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText]);

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Message list */}
      <div className="flex-1 overflow-y-auto py-4 space-y-1">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isStreaming && <StreamingIndicator text={streamingText} />}
        {error && (
          <div role="alert" className="mx-4 my-3 rounded border border-red-500/30 bg-red-500/5 px-3 py-2 text-xs text-red-400">
            {error}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <ChatInput onSend={onSend} disabled={isStreaming} />
    </div>
  );
}
