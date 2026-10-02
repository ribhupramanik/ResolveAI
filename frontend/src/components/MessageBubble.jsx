import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function MessageBubble({ role, content }) {
  const isUser = role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-white text-slate-950"
            : "border border-slate-800 bg-slate-900 text-slate-100"
        }`}
      >
        <p className="mb-1 text-xs opacity-60">
          {isUser ? "Customer" : "ResolveAI"}
        </p>

        {isUser ? (
          <p className="whitespace-pre-wrap leading-6">{content}</p>
        ) : (
          <div className="leading-6">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                p: ({ children }) => (
                  <p className="mb-3 last:mb-0">{children}</p>
                ),

                strong: ({ children }) => (
                  <strong className="font-semibold text-slate-100">
                    {children}
                  </strong>
                ),

                ul: ({ children }) => (
                  <ul className="my-3 list-disc space-y-1 pl-5">{children}</ul>
                ),

                ol: ({ children }) => (
                  <ol className="my-3 list-decimal space-y-1 pl-5">
                    {children}
                  </ol>
                ),

                li: ({ children }) => <li className="pl-1">{children}</li>,

                code: ({ children }) => (
                  <code className="rounded bg-slate-800 px-1.5 py-0.5 text-sm text-slate-200">
                    {children}
                  </code>
                ),

                a: ({ children, href }) => (
                  <a
                    href={href}
                    target="_blank"
                    rel="noreferrer"
                    className="text-blue-400 underline underline-offset-2 hover:text-blue-300"
                  >
                    {children}
                  </a>
                ),
              }}
            >
              {content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}

export default MessageBubble;
