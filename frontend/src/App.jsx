import { useEffect, useState } from "react";

import {
  confirmAndExecutePendingAction,
  createConversation,
  getConversationMessages,
  getConversations,
  getPendingAction,
  rejectPendingAction,
  sendConversationMessage,
} from "./api/conversations";

import ChatPanel from "./components/ChatPanel";
import ConversationSidebar from "./components/ConversationSidebar";
import IntelligencePanel from "./components/IntelligencePanel";

function App() {
  const [conversations, setConversations] = useState([]);

  const [activeConversationId, setActiveConversationId] = useState(null);

  const [messages, setMessages] = useState([]);

  const [message, setMessage] = useState("");

  const [metadata, setMetadata] = useState(null);

  const [pendingAction, setPendingAction] = useState(null);

  const [loading, setLoading] = useState(false);

  const [actionLoading, setActionLoading] = useState(false);

  const [error, setError] = useState("");

  useEffect(() => {
    loadConversations();
  }, []);

  useEffect(() => {
    if (!activeConversationId) {
      setMessages([]);
      setMetadata(null);
      setPendingAction(null);
      return;
    }

    loadConversationData(activeConversationId);
  }, [activeConversationId]);

  async function loadConversations() {
    try {
      const data = await getConversations();

      setConversations(data);

      if (data.length > 0 && !activeConversationId) {
        setActiveConversationId(data[0].id);
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load conversations.",
      );
    }
  }

  async function loadConversationData(conversationId) {
    try {
      setError("");

      setMessages([]);
      setMetadata(null);
      setPendingAction(null);

      const [messagesData, pendingActionData] = await Promise.all([
        getConversationMessages(conversationId),
        getPendingAction(conversationId),
      ]);

      setMessages(messagesData);

      setPendingAction(pendingActionData);

      const latestAssistantWithMetadata = [...messagesData]
        .reverse()
        .find((item) => item.role === "assistant" && item.ai_metadata);

      setMetadata(latestAssistantWithMetadata?.ai_metadata ?? null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load conversation.",
      );
    }
  }

  async function handleNewConversation() {
    try {
      setError("");

      const conversation = await createConversation();

      setConversations((current) => [conversation, ...current]);

      setActiveConversationId(conversation.id);

      setMessages([]);
      setMetadata(null);
      setPendingAction(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create conversation.",
      );
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();

    const trimmedMessage = message.trim();

    if (!trimmedMessage || loading || actionLoading) {
      return;
    }

    let conversationId = activeConversationId;

    try {
      setLoading(true);
      setError("");

      if (!conversationId) {
        const conversation = await createConversation();

        conversationId = conversation.id;

        setConversations((current) => [conversation, ...current]);

        setActiveConversationId(conversation.id);
      }

      const temporaryUserMessage = {
        id: `temp-${crypto.randomUUID()}`,
        conversation_id: conversationId,
        role: "user",
        content: trimmedMessage,
        created_at: new Date().toISOString(),
      };

      setMessages((current) => [...current, temporaryUserMessage]);

      setMessage("");

      const data = await sendConversationMessage(
        conversationId,
        trimmedMessage,
      );

      setMessages((current) => [
        ...current.filter((item) => item.id !== temporaryUserMessage.id),
        data.user_message,
        data.assistant_message,
      ]);

      setMetadata(data.metadata);

      setPendingAction(data.pending_action);

      await loadConversations();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  async function handlePendingActionDecision(decision) {
    if (!activeConversationId || !pendingAction || actionLoading || loading) {
      return;
    }

    try {
      setActionLoading(true);
      setError("");

      if (decision === "confirm") {
        const action = pendingAction;

        await confirmAndExecutePendingAction(activeConversationId, action.id);

        // The backend persists the result message.
        // Reload the conversation so React displays
        // the authoritative database state.
        await loadConversationData(activeConversationId);

        await loadConversations();

        return;
      }

      if (decision === "reject") {
        const action = pendingAction;

        await rejectPendingAction(activeConversationId, action.id);

        // The backend persists the deterministic
        // rejection message and changes the exact
        // PendingAction to rejected.
        //
        // Reload the authoritative conversation state.
        await loadConversationData(activeConversationId);

        await loadConversations();

        return;
      }

      throw new Error("Unknown pending action decision.");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to process cancellation.",
      );
    } finally {
      setActionLoading(false);
    }
  }

  return (
    <main className="h-screen overflow-hidden bg-slate-950 text-slate-100">
      <div className="flex h-full">
        <ConversationSidebar
          conversations={conversations}
          activeConversationId={activeConversationId}
          onSelectConversation={setActiveConversationId}
          onNewConversation={handleNewConversation}
        />

        <ChatPanel
          messages={messages}
          message={message}
          setMessage={setMessage}
          loading={loading}
          error={error}
          onSubmit={handleSubmit}
          pendingAction={pendingAction}
          actionLoading={actionLoading}
          onPendingActionDecision={handlePendingActionDecision}
        />

        <IntelligencePanel metadata={metadata} />
      </div>
    </main>
  );
}

export default App;
