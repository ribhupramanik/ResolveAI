const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export async function getConversations() {
  const response = await fetch(`${API_BASE_URL}/api/v1/conversations`);

  if (!response.ok) {
    throw new Error("Failed to load conversations.");
  }

  return response.json();
}

export async function createConversation() {
  const response = await fetch(`${API_BASE_URL}/api/v1/conversations`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({}),
  });

  if (!response.ok) {
    throw new Error("Failed to create conversation.");
  }

  return response.json();
}

export async function getConversationMessages(conversationId) {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/conversations/${conversationId}/messages`,
  );

  if (!response.ok) {
    throw new Error("Failed to load messages.");
  }

  return response.json();
}

export async function getPendingAction(conversationId) {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/conversations/${conversationId}/pending-action`,
  );

  if (!response.ok) {
    throw new Error("Failed to load pending action.");
  }

  return response.json();
}

export async function sendConversationMessage(conversationId, message) {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/conversations/${conversationId}/messages`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message,
      }),
    },
  );

  if (!response.ok) {
    throw new Error("Failed to send message.");
  }

  return response.json();
}
