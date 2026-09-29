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
            <MetadataItem
              label="Knowledge topic"
              value={metadata.verified_knowledge_topics.join(", ") || "None"}
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

function MetadataItem({ label, value }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wider text-slate-500">{label}</p>

      <p className="mt-1 break-words text-sm text-slate-200">{value}</p>
    </div>
  );
}

export default IntelligencePanel;
