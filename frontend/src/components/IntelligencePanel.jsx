function IntelligencePanel({ metadata }) {
  return (
    <aside className="hidden w-80 shrink-0 border-l border-slate-800 bg-slate-900/40 xl:block">
      <div className="border-b border-slate-800 px-5 py-4">
        <h2 className="font-semibold">AI Intelligence</h2>

        <p className="text-sm text-slate-500">Response diagnostics</p>
      </div>

      <div className="space-y-6 p-5">
        {!metadata && (
          <p className="text-sm text-slate-500">
            Intelligence data will appear after ResolveAI generates a response.
          </p>
        )}

        {metadata && (
          <>
            <ToolExecution metadata={metadata} />

            <MetadataItem
              label="Knowledge topic"
              value={metadata.verified_knowledge_topics?.join(", ") || "None"}
            />

            <MetadataItem
              label="Retrieved examples"
              value={metadata.retrieved_count}
            />

            <MetadataItem
              label="Verified knowledge"
              value={metadata.verified_knowledge_count}
            />

            <MetadataItem
              label="System capabilities"
              value={metadata.system_capability_count}
            />

            <MetadataItem
              label="Generation attempts"
              value={metadata.attempts}
            />

            <MetadataItem
              label="Fallback used"
              value={metadata.used_fallback ? "Yes" : "No"}
            />

            <MetadataItem
              label="Provider"
              value={metadata.provider || "Unknown"}
            />

            <MetadataItem label="Model" value={metadata.model || "Unknown"} />

            <div>
              <p className="mb-2 text-xs uppercase tracking-wider text-slate-500">
                Retry triggers
              </p>

              {metadata.retry_trigger_issues?.length > 0 ? (
                <div className="space-y-2">
                  {metadata.retry_trigger_issues.map((issue, index) => (
                    <div
                      key={`${issue.code}-${index}`}
                      className="rounded-lg border border-amber-900/50 bg-amber-950/20 p-3"
                    >
                      <p className="text-xs font-medium text-amber-300">
                        {issue.code}
                      </p>

                      <p className="mt-1 text-xs text-slate-400">
                        {issue.matched_text}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-slate-400">None</p>
              )}
            </div>
          </>
        )}
      </div>
    </aside>
  );
}

function ToolExecution({ metadata }) {
  /*
   * Older saved conversations may not contain the
   * tool observability fields yet.
   */
  if (metadata.tool_used === undefined) {
    return (
      <div>
        <p className="mb-2 text-xs uppercase tracking-wider text-slate-500">
          Tool execution
        </p>

        <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
          <p className="text-sm text-slate-400">Not recorded</p>
        </div>
      </div>
    );
  }

  if (!metadata.tool_used) {
    return (
      <div>
        <p className="mb-2 text-xs uppercase tracking-wider text-slate-500">
          Tool execution
        </p>

        <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
          <p className="text-sm text-slate-300">No tool required</p>

          <p className="mt-1 text-xs text-slate-500">
            ResolveAI answered without executing an operational tool.
          </p>
        </div>
      </div>
    );
  }

  const succeeded = metadata.tool_success === true;

  return (
    <div>
      <p className="mb-2 text-xs uppercase tracking-wider text-slate-500">
        Tool execution
      </p>

      <div
        className={`rounded-lg border p-3 ${
          succeeded
            ? "border-emerald-900/50 bg-emerald-950/20"
            : "border-rose-900/50 bg-rose-950/20"
        }`}
      >
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs text-slate-500">Tool</p>

            <p className="mt-1 text-sm font-medium text-slate-200">
              {metadata.tool_name || "Unknown"}
            </p>
          </div>

          <span
            className={`rounded-full px-2.5 py-1 text-xs font-medium ${
              succeeded
                ? "bg-emerald-500/10 text-emerald-300"
                : "bg-rose-500/10 text-rose-300"
            }`}
          >
            {succeeded ? "Success" : "Failed"}
          </span>
        </div>
      </div>
    </div>
  );
}

function MetadataItem({ label, value }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wider text-slate-500">{label}</p>

      <p className="mt-1 break-words text-sm text-slate-200">{value}</p>
    </div>
  );
}

export default IntelligencePanel;
