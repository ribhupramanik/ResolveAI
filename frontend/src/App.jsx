import { useState } from "react";

import { sendMessage } from "./api/chat";
import ChatPanel from "./components/ChatPanel";
import ConversationSidebar from "./components/ConversationSidebar";
import IntelligencePanel from "./components/IntelligencePanel";

function App() {
  const [message, setMessage] = useState("");

  const [messages, setMessages] = useState([]);

  const [metadata, setMetadata] = useState(null);

  const [loading, setLoading] = useState(false);

  const [error, setError] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault();

    const trimmedMessage = message.trim();

    if (!trimmedMessage || loading) {
      return;
    }

    const userMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmedMessage,
    };

    setMessages((current) => [...current, userMessage]);

    setMessage("");
    setLoading(true);
    setError("");

    try {
      const data = await sendMessage(trimmedMessage);

      const assistantMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: data.message,
      };

      setMessages((current) => [...current, assistantMessage]);

      setMetadata(data.metadata);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="h-screen overflow-hidden bg-slate-950 text-slate-100">
      <div className="flex h-full">
        <ConversationSidebar />

        <ChatPanel
          messages={messages}
          message={message}
          setMessage={setMessage}
          loading={loading}
          error={error}
          onSubmit={handleSubmit}
        />

        <IntelligencePanel metadata={metadata} />
      </div>
    </main>
  );
}

export default App;
