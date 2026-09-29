import MessageBubble from "./MessageBubble";


function ChatPanel({
  messages,
  message,
  setMessage,
  loading,
  error,
  onSubmit,
}) {
  return (
    <section className="flex min-w-0 flex-1 flex-col bg-slate-950">

      <header className="border-b border-slate-800 px-6 py-4">
        <h2 className="font-semibold">
          Customer Conversation
        </h2>

        <p className="text-sm text-slate-500">
          ResolveAI support assistant
        </p>
      </header>


      <div className="flex-1 space-y-5 overflow-y-auto p-6">

        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center text-center">
            <div>
              <h3 className="text-xl font-semibold">
                Start a conversation
              </h3>

              <p className="mt-2 text-sm text-slate-500">
                Ask ResolveAI a customer-support question.
              </p>
            </div>
          </div>
        )}


        {messages.map((item) => (
          <MessageBubble
            key={item.id}
            role={item.role}
            content={item.content}
          />
        ))}


        {loading && (
          <MessageBubble
            role="assistant"
            content="Thinking..."
          />
        )}


        {error && (
          <div className="rounded-lg border border-red-900 bg-red-950/30 p-3 text-sm text-red-300">
            {error}
          </div>
        )}

      </div>


      <form
        onSubmit={onSubmit}
        className="border-t border-slate-800 p-4"
      >
        <div className="flex items-end gap-3 rounded-xl border border-slate-700 bg-slate-900 p-3">

          <textarea
            value={message}
            onChange={(event) =>
              setMessage(
                event.target.value
              )
            }
            placeholder="Ask ResolveAI..."
            rows={2}
            className="max-h-40 min-h-12 flex-1 resize-none bg-transparent text-sm outline-none placeholder:text-slate-600"
          />

          <button
            type="submit"
            disabled={
              loading ||
              !message.trim()
            }
            className="rounded-lg bg-white px-5 py-2 text-sm font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Send
          </button>

        </div>
      </form>

    </section>
  );
}

export default ChatPanel;