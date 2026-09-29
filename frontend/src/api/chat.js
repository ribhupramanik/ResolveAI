const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL;

export async function sendMessage(message) {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/chat`,
    {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify({
        message,
      }),
    }
  );

  if (!response.ok) {
    throw new Error(
      `Request failed with status ${response.status}`
    );
  }

  return response.json();
}