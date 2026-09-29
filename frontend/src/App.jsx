import { useState } from "react";

import { sendMessage } from "./api/chat";

function App() {
  const [message, setMessage] = useState("");

  const [response, setResponse] = useState(null);

  const [loading, setLoading] = useState(false);

  const [error, setError] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault();

    const trimmedMessage = message.trim();

    if (!trimmedMessage) {
      return;
    }

    setLoading(true);
    setError("");
    setResponse(null);

    try {
      const data = await sendMessage(trimmedMessage);

      setResponse(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-3xl px-6 py-12">
        <header className="mb-10">
          <h1 className="text-3xl font-bold">ResolveAI</h1>

          <p className="mt-2 text-slate-400">
            AI Customer Support Intelligence
          </p>
        </header>

        <form
          onSubmit={handleSubmit}
          className="rounded-xl border border-slate-800 bg-slate-900 p-5"
        >
          <label htmlFor="message" className="mb-2 block text-sm font-medium">
            Customer message
          </label>

          <textarea
            id="message"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Where is my order right now?"
            rows={4}
            className="w-full resize-none rounded-lg border border-slate-700 bg-slate-950 p-3 outline-none focus:border-slate-500"
          />

          <button
            type="submit"
            disabled={loading}
            className="mt-4 rounded-lg bg-white px-5 py-2 font-medium text-slate-950 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? "Thinking..." : "Send"}
          </button>
        </form>

        {error && (
          <div className="mt-6 rounded-xl border border-red-900 bg-red-950/30 p-4">
            {error}
          </div>
        )}

        {response && (
          <section className="mt-6 space-y-4">
            <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
              <p className="mb-2 text-sm text-slate-400">ResolveAI</p>

              <p className="leading-7">{response.message}</p>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
              <h2 className="mb-4 font-semibold">AI Metadata</h2>

              <div className="space-y-2 text-sm text-slate-300">
                <p>
                  <span className="text-slate-500">Knowledge topic:</span>{" "}
                  {response.metadata.verified_knowledge_topics.join(", ") ||
                    "None"}
                </p>

                <p>
                  <span className="text-slate-500">Retrieved examples:</span>{" "}
                  {response.metadata.retrieved_count}
                </p>

                <p>
                  <span className="text-slate-500">Attempts:</span>{" "}
                  {response.metadata.attempts}
                </p>

                <p>
                  <span className="text-slate-500">Fallback used:</span>{" "}
                  {response.metadata.used_fallback ? "Yes" : "No"}
                </p>

                <p>
                  <span className="text-slate-500">Model:</span>{" "}
                  {response.metadata.model}
                </p>
              </div>
            </div>
          </section>
        )}
      </div>
    </main>
  );
}

export default App;
