function MessageBubble({
  role,
  content,
}) {
  const isUser = role === "user";

  return (
    <div
      className={`flex ${
        isUser
          ? "justify-end"
          : "justify-start"
      }`}
    >
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-white text-slate-950"
            : "border border-slate-800 bg-slate-900 text-slate-100"
        }`}
      >
        <p className="mb-1 text-xs opacity-60">
          {isUser
            ? "Customer"
            : "ResolveAI"}
        </p>

        <p className="whitespace-pre-wrap leading-6">
          {content}
        </p>
      </div>
    </div>
  );
}

export default MessageBubble;