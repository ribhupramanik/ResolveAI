function ConversationSidebar({
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  mobileActive = false,
}) {
  return (
    <aside
      className={`${mobileActive ? "flex" : "hidden"} min-h-0 w-full flex-col border-r border-slate-800 bg-slate-900/60 xl:flex xl:w-64 xl:shrink-0`}
    >
      <div className="border-b border-slate-800 p-5">
        <h1 className="text-xl font-bold">ResolveAI</h1>

        <p className="mt-1 text-xs text-slate-500">Support Intelligence</p>
      </div>

      <div className="p-4">
        <button
          type="button"
          onClick={onNewConversation}
          className="w-full rounded-lg border border-slate-700 px-4 py-2 text-left text-sm font-medium transition hover:bg-slate-800"
        >
          + New conversation
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-3">
        <p className="px-2 pb-2 text-xs uppercase tracking-wider text-slate-600">
          Recent
        </p>

        <div className="space-y-1">
          {conversations.length === 0 && (
            <p className="px-2 py-3 text-sm text-slate-600">
              No conversations yet.
            </p>
          )}

          {conversations.map((conversation) => {
            const isActive = conversation.id === activeConversationId;

            return (
              <button
                key={conversation.id}
                type="button"
                onClick={() => onSelectConversation(conversation.id)}
                className={`w-full rounded-lg px-3 py-3 text-left transition ${
                  isActive ? "bg-slate-800" : "hover:bg-slate-800/50"
                }`}
              >
                <p className="truncate text-sm font-medium">
                  {conversation.title}
                </p>

                <p className="mt-1 text-xs text-slate-500">
                  Conversation #{conversation.id}
                </p>
              </button>
            );
          })}
        </div>
      </div>

      <div className="border-t border-slate-800 p-4 text-xs text-slate-600">
        ResolveAI v0.1
      </div>
    </aside>
  );
}

export default ConversationSidebar;
