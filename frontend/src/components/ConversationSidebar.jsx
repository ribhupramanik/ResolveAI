function ConversationSidebar() {
  return (
    <aside className="hidden w-64 shrink-0 border-r border-slate-800 bg-slate-900/60 lg:flex lg:flex-col">
      <div className="border-b border-slate-800 p-5">
        <h1 className="text-xl font-bold">ResolveAI</h1>

        <p className="mt-1 text-xs text-slate-500">Support Intelligence</p>
      </div>

      <div className="p-4">
        <button
          type="button"
          className="w-full rounded-lg border border-slate-700 px-4 py-2 text-left text-sm font-medium hover:bg-slate-800"
        >
          + New conversation
        </button>
      </div>

      <div className="flex-1 px-3">
        <p className="px-2 pb-2 text-xs uppercase tracking-wider text-slate-600">
          Recent
        </p>

        <div className="rounded-lg bg-slate-800/70 px-3 py-3">
          <p className="truncate text-sm">Current conversation</p>

          <p className="mt-1 text-xs text-slate-500">Active now</p>
        </div>
      </div>

      <div className="border-t border-slate-800 p-4 text-xs text-slate-600">
        ResolveAI v0.1
      </div>
    </aside>
  );
}

export default ConversationSidebar;
