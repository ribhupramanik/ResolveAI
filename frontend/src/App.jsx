import { useEffect, useState } from "react";

import {
  confirmAndExecutePendingAction,
  confirmAndExecuteRefund,
  createConversation,
  getConversationMessages,
  getConversations,
  getPendingAction,
  rejectPendingAction,
  sendConversationMessage,
} from "./api/conversations";

import OrdersPanel from "./components/OrdersPanel";
import ChatPanel from "./components/ChatPanel";
import ConversationSidebar from "./components/ConversationSidebar";
import IntelligencePanel from "./components/IntelligencePanel";

function App() {
  const [conversations, setConversations] = useState([]);

  const [initialLoading, setInitialLoading] = useState(true);
  const [initialError, setInitialError] = useState("");

  const [activeConversationId, setActiveConversationId] = useState(null);

  const [messages, setMessages] = useState([]);

  const [message, setMessage] = useState("");

  const [metadata, setMetadata] = useState(null);

  const [pendingAction, setPendingAction] = useState(null);

  const [loading, setLoading] = useState(false);

  const [actionLoading, setActionLoading] = useState(false);

  const [activeView, setActiveView] = useState("chat");

  const [chatPane, setChatPane] = useState("chat");

  const [error, setError] = useState("");

  useEffect(() => {
    loadConversations(true);
  }, []);

  useEffect(() => {
    if (activeConversationId !== null) {
      loadConversationData(activeConversationId);
    }
  }, [activeConversationId]);

  async function loadConversations(isInitial = false) {
    if (isInitial) {
      setInitialLoading(true);
      setInitialError("");
    }

    try {
      const data = await getConversations();

      setConversations(data);

      setActiveConversationId((current) => current ?? data[0]?.id ?? null);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to load conversations.";

      if (isInitial) {
        setInitialError(errorMessage);
      } else {
        setError(errorMessage);
      }
    } finally {
      if (isInitial) {
        setInitialLoading(false);
      }
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

        if (action.action_type === "cancel_order") {
          await confirmAndExecutePendingAction(activeConversationId, action.id);
        } else if (action.action_type === "initiate_refund") {
          await confirmAndExecuteRefund(activeConversationId, action.id);
        } else {
          throw new Error("Unsupported pending action type.");
        }

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
        err instanceof Error
          ? err.message
          : "Failed to process the pending action.",
      );
    } finally {
      setActionLoading(false);
    }
  }

  function handleTestOrderInChat(orderNumber) {
    setActiveConversationId(null);

    setMessages([]);
    setMetadata(null);
    setPendingAction(null);
    setError("");

    setMessage(
      `Tell me about order ${orderNumber}. What is its current status, and what shipping or delivery details are available?`,
    );

    setActiveView("chat");
    setChatPane("chat");
  }

  return (
    <main className="flex h-screen flex-col overflow-hidden bg-slate-950 text-slate-100">
      <header className="flex shrink-0 items-center justify-between gap-2 border-b border-slate-800 px-3 py-3 sm:px-6">
        <div className="flex min-w-0 flex-1 items-center gap-2 sm:gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 text-lg font-bold text-white">
            R
          </div>

          <div>
            <h1 className="text-lg font-semibold tracking-tight">ResolveAI</h1>
            <p className="max-w-[145px] text-xs leading-4 text-slate-400 sm:max-w-none">
              Intelligent Customer Support
            </p>
          </div>
        </div>

        <nav
          className="flex items-center justify-end gap-2"
          aria-label="Main navigation"
        >
          <button
            type="button"
            aria-pressed={activeView === "chat"}
            onClick={() => setActiveView("chat")}
            className={`rounded-lg px-5 py-2 text-sm font-medium transition-colors ${
              activeView === "chat"
                ? "bg-indigo-600 text-white"
                : "text-slate-400 hover:bg-slate-800 hover:text-white"
            }`}
          >
            Chat
          </button>

          <button
            type="button"
            aria-pressed={activeView === "orders"}
            onClick={() => setActiveView("orders")}
            className={`rounded-lg px-5 py-2 text-sm font-medium transition-colors ${
              activeView === "orders"
                ? "bg-indigo-600 text-white"
                : "text-slate-400 hover:bg-slate-800 hover:text-white"
            }`}
          >
            Orders
          </button>
        </nav>
      </header>

      {activeView === "chat" && (initialLoading || initialError) ? (
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
          {initialLoading ? (
            <div
              className="flex flex-col items-center gap-4"
              role="status"
              aria-live="polite"
            >
              <div
                className="h-12 w-12 animate-spin rounded-full border-4 border-slate-700 border-t-indigo-500"
                aria-hidden="true"
              />
              <p className="text-sm text-slate-300">
                Connecting to ResolveAI...
              </p>
              <p className="text-xs text-slate-500">
                Loading your conversations
              </p>
            </div>
          ) : (
            <div role="alert" className="flex flex-col items-center gap-4">
              <p className="text-sm text-red-300">{initialError}</p>
              <button
                type="button"
                onClick={() => loadConversations(true)}
                className="rounded-lg bg-indigo-600 px-5 py-2 text-sm font-medium text-white hover:bg-indigo-500"
              >
                Try again
              </button>
            </div>
          )}
        </div>
      ) : activeView === "chat" ? (
        <div className="flex min-h-0 flex-1 flex-col">
          <nav
            className="grid grid-cols-3 gap-2 border-b border-slate-800 p-2 xl:hidden"
            aria-label="Chat panels"
          >
            {[
              ["conversations", "Conversations"],
              ["chat", "Chat"],
              ["intelligence", "AI Insights"],
            ].map(([key, label]) => (
              <button
                key={key}
                type="button"
                aria-pressed={chatPane === key}
                onClick={() => setChatPane(key)}
                className={`rounded-lg px-2 py-2 text-xs font-semibold ${
                  chatPane === key
                    ? "bg-indigo-600 text-white"
                    : "bg-slate-900 text-slate-300"
                }`}
              >
                {label}
              </button>
            ))}
          </nav>

          <div className="flex min-h-0 flex-1">
            <ConversationSidebar
              conversations={conversations}
              activeConversationId={activeConversationId}
              mobileActive={chatPane === "conversations"}
              onSelectConversation={(id) => {
                setActiveConversationId(id);
                setChatPane("chat");
              }}
              onNewConversation={() => {
                setChatPane("chat");
                handleNewConversation();
              }}
            />

            <ChatPanel
              mobileActive={chatPane === "chat"}
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

            <IntelligencePanel
              metadata={metadata}
              mobileActive={chatPane === "intelligence"}
            />
          </div>
        </div>
      ) : (
        <OrdersPanel onTestInChat={handleTestOrderInChat} />
      )}
    </main>
  );
}

export default App;
