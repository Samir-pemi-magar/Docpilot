import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";

function formatTime(value) {
  if (!value) return "";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";

  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function mapMessage(message) {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    timestamp: formatTime(message.created_at),
    sources: message.sources || [],
  };
}

function mapSources(sources) {
  return (sources || []).map((source, index) => ({
    ...source,
    rank: source.rank ?? index + 1,
  }));
}

export function useMockChat(
  organizationId,
  selectedConversationId = null,
  onConversationChange,
  onConversationsChanged,
) {
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingText] = useState("");
  const [sources, setSources] = useState([]);
  const [conversationId, setConversationId] = useState(
    selectedConversationId,
  );
  const [error, setError] = useState("");
  const [traceVisible, setTraceVisible] = useState(false);
  const [activeTrace, setActiveTrace] = useState([]);
  const [sourcesVisible, setSourcesVisible] = useState(true);
  const pendingConversationSelectionRef = useRef(null);

  // Load the selected conversation, or reset the view for a new chat.
  useEffect(() => {
    let cancelled = false;

    // A newly created conversation is selected after its answer arrives.
    // Preserve that live answer instead of clearing its messages and trace.
    if (
      selectedConversationId &&
      pendingConversationSelectionRef.current?.organizationId === organizationId &&
      pendingConversationSelectionRef.current?.conversationId === selectedConversationId
    ) {
      pendingConversationSelectionRef.current = null;

      return () => {
        cancelled = true;
      };
    }

    setMessages([]);
    setSources([]);
    setError("");
    setActiveTrace([]);
    setTraceVisible(false);
    setSourcesVisible(true);
    setConversationId(selectedConversationId);

    if (!organizationId || !selectedConversationId) {
      return () => {
        cancelled = true;
      };
    }

    async function loadConversation() {
      try {
        const conversation = await api.conversation(
          organizationId,
          selectedConversationId,
        );

        if (cancelled) return;

        const loadedMessages = (conversation.messages || []).map(mapMessage);
        setMessages(loadedMessages);

        const lastAssistantMessage = [...loadedMessages]
          .reverse()
          .find((message) => message.role === "assistant");

        setSources(mapSources(lastAssistantMessage?.sources));
      } catch (err) {
        if (cancelled) return;

        setError(err.message || "Unable to load this conversation.");
      }
    }

    loadConversation();

    return () => {
      cancelled = true;
    };
  }, [organizationId, selectedConversationId]);

  const sendMessage = useCallback(
    async (rawText) => {
      const text = rawText.trim();

      if (!text || !organizationId || isStreaming) return;

      const userMessage = {
        id: `pending-user-${Date.now()}`,
        role: "user",
        content: text,
        timestamp: formatTime(new Date().toISOString()),
        sources: [],
      };

      setMessages((previous) => [...previous, userMessage]);
      setActiveTrace([]);
      setError("");
      setIsStreaming(true);

      try {
        const result = await api.chat(
          organizationId,
          text,
          conversationId,
          5,
        );

        const returnedConversationId = result.conversation_id;
        setActiveTrace(Array.isArray(result.trace) ? result.trace : []);

        if (returnedConversationId !== conversationId) {
          pendingConversationSelectionRef.current = {
            organizationId,
            conversationId: returnedConversationId,
          };
        }

        setConversationId(returnedConversationId);

        if (returnedConversationId !== conversationId) {
          onConversationChange?.(returnedConversationId);
        }

        const assistantSources = mapSources(result.sources);

        setMessages((previous) => [
          ...previous.filter((message) => message.id !== userMessage.id),
          {
            ...userMessage,
            id: `user-${returnedConversationId}-${Date.now()}`,
          },
          {
            id: `assistant-${returnedConversationId}-${Date.now()}`,
            role: "assistant",
            content: result.answer,
            timestamp: formatTime(new Date().toISOString()),
            sources: assistantSources,
          },
        ]);
        setSources(assistantSources);

        // Replace temporary IDs with persisted database IDs for export actions.
        try {
          const savedConversation = await api.conversation(
            organizationId,
            returnedConversationId,
          );
          const savedMessages = (savedConversation.messages || []).map(mapMessage);
          if (savedMessages.length > 0) {
            setMessages(savedMessages);
            const lastSavedAssistant = [...savedMessages]
              .reverse()
              .find((message) => message.role === "assistant");
            setSources(mapSources(lastSavedAssistant?.sources));
          }
        } catch {
          // Keep the answer visible if the follow-up refresh fails.
        }

        // Refresh the sidebar so the saved conversation and updated title appear.
        await onConversationsChanged?.();
      } catch (err) {
        setError(err.message || "Unable to get an answer from DocPilot.");
      } finally {
        setIsStreaming(false);
      }
    },
    [
      organizationId,
      conversationId,
      isStreaming,
      onConversationChange,
      onConversationsChanged,
    ],
  );

  const toggleTrace = useCallback(() => {
    setTraceVisible((visible) => !visible);
  }, []);

  const toggleSources = useCallback(() => {
    setSourcesVisible((visible) => !visible);
  }, []);

  return {
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
  };
}
