import MessageBubble from "./MessageBubble";

function ChatPanel({
  messages,
  message,
  setMessage,
  loading,
  error,
  onSubmit,
  pendingAction,
  actionLoading,
  onPendingActionDecision,
}) {
  const hasCancellationPending =
    pendingAction?.action_type === "cancel_order" &&
    pendingAction?.status === "pending";

  return (
    <section className="flex min-w-0 flex-1 flex-col bg-slate-950">
      <header className="border-b border-slate-800 px-6 py-4">
        <h2 className="font-semibold">Customer Conversation</h2>

        <p className="text-sm text-slate-500">ResolveAI support assistant</p>
      </header>

      <div className="flex-1 space-y-5 overflow-y-auto p-6">
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center text-center">
            <div>
              <h3 className="text-xl font-semibold">Start a conversation</h3>

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

        {hasCancellationPending && (
          <div className="ml-11 max-w-xl">
            <div className="rounded-xl border border-slate-700 bg-slate-900 p-4 shadow-lg">
              <div className="flex items-start gap-3">
                <div className="flex-1">
                  <p className="text-sm font-semibold text-slate-100">
                    Confirm cancellation
                  </p>

                  <p className="mt-2 text-sm leading-6 text-slate-400">
                    Do you want to cancel{" "}
                    <span className="font-semibold text-slate-200">
                      {pendingAction.target_identifier}
                    </span>
                    ?
                  </p>

                  <p className="mt-1 text-xs text-slate-500">
                    Confirming will cancel the order immediately if it is
                    still eligible.
                  </p>
                </div>
              </div>

              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  type="button"
                  disabled={actionLoading || loading}
                  onClick={() => onPendingActionDecision("confirm")}
                  className="rounded-lg bg-red-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-400 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {actionLoading ? "Cancelling..." : "Confirm cancellation"}
                </button>

                <button
                  type="button"
                  disabled={actionLoading || loading}
                  onClick={() => onPendingActionDecision("reject")}
                  className="rounded-lg border border-slate-600 bg-slate-950 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Keep order
                </button>
              </div>
            </div>
          </div>
        )}

        {loading && <MessageBubble role="assistant" content="Thinking..." />}

        {error && (
          <div className="rounded-lg border border-red-900 bg-red-950/30 p-3 text-sm text-red-300">
            {error}
          </div>
        )}
      </div>

      <form onSubmit={onSubmit} className="border-t border-slate-800 p-4">
        <div className="flex items-end gap-3 rounded-xl border border-slate-700 bg-slate-900 p-3">
          <textarea
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder={
              actionLoading ? "Processing cancellation..." : "Ask ResolveAI..."
            }
            rows={2}
            disabled={actionLoading}
            className="max-h-40 min-h-12 flex-1 resize-none bg-transparent text-sm outline-none placeholder:text-slate-600 disabled:cursor-not-allowed disabled:opacity-50"
          />

          <button
            type="submit"
            disabled={loading || actionLoading || !message.trim()}
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
