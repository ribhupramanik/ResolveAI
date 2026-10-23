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
  mobileActive = true,
}) {
  const isCancellationPending =
    pendingAction?.action_type === "cancel_order" &&
    pendingAction?.status === "pending";

  const isRefundPending =
    pendingAction?.action_type === "initiate_refund" &&
    pendingAction?.status === "pending";

  const hasPendingAction = isCancellationPending || isRefundPending;

  const actionTitle = isRefundPending
    ? "Confirm refund request"
    : "Confirm cancellation";

  const actionDescription = isRefundPending
    ? "Confirming will initiate an internal refund request if the order is still eligible. This does not mean the money has been refunded."
    : "Confirming will cancel the order immediately if it is still eligible.";

  const confirmButtonLabel = actionLoading
    ? isRefundPending
      ? "Initiating refund..."
      : "Cancelling..."
    : isRefundPending
      ? "Confirm refund"
      : "Confirm cancellation";

  const rejectButtonLabel = isRefundPending ? "Reject refund" : "Keep order";

  const inputPlaceholder = actionLoading
    ? isRefundPending
      ? "Processing refund request..."
      : "Processing cancellation..."
    : "Ask ResolveAI...";

  return (
    <section
      className={`${mobileActive ? "flex" : "hidden"} min-h-0 min-w-0 flex-1 flex-col bg-slate-950 xl:flex`}
    >
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

        {hasPendingAction && (
          <div className="ml-11 max-w-xl">
            <div className="rounded-xl border border-slate-700 bg-slate-900 p-4 shadow-lg">
              <div className="flex items-start gap-3">
                <div className="flex-1">
                  <p className="text-sm font-semibold text-slate-100">
                    {actionTitle}
                  </p>

                  <p className="mt-2 text-sm leading-6 text-slate-400">
                    {isRefundPending
                      ? "Do you want to initiate a refund for "
                      : "Do you want to cancel "}
                    <span className="font-semibold text-slate-200">
                      {pendingAction.target_identifier}
                    </span>
                    ?
                  </p>

                  <p className="mt-2 text-xs leading-5 text-slate-500">
                    {actionDescription}
                  </p>
                </div>
              </div>

              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  type="button"
                  disabled={actionLoading || loading}
                  onClick={() => onPendingActionDecision("confirm")}
                  className={
                    isRefundPending
                      ? "rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
                      : "rounded-lg bg-red-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-400 disabled:cursor-not-allowed disabled:opacity-50"
                  }
                >
                  {confirmButtonLabel}
                </button>

                <button
                  type="button"
                  disabled={actionLoading || loading}
                  onClick={() => onPendingActionDecision("reject")}
                  className="rounded-lg border border-slate-600 bg-slate-950 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {rejectButtonLabel}
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
            placeholder={inputPlaceholder}
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
