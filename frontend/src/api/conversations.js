const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export async function getConversations() {
  const retryDelays = [2000, 4000, 6000, 8000];

  for (let attempt = 0; attempt <= retryDelays.length; attempt++) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/conversations`);

      if (response.ok) {
        return response.json();
      }

      if (![502, 503, 504].includes(response.status)) {
        throw new Error(
          `Failed to load conversations (HTTP ${response.status}).`,
        );
      }

      if (attempt === retryDelays.length) {
        throw new Error(
          `ResolveAI server is temporarily unavailable (HTTP ${response.status}).`,
        );
      }
    } catch (err) {
      if (!(err instanceof TypeError)) {
        throw err;
      }

      if (attempt === retryDelays.length) {
        throw new Error("Unable to connect to ResolveAI. Please try again.", {
          cause: err,
        });
      }
    }

    await new Promise((resolve) => setTimeout(resolve, retryDelays[attempt]));
  }
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

export async function confirmAndExecutePendingAction(conversationId, actionId) {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/conversations/${conversationId}/pending-actions/${actionId}/confirm-and-execute`,
    {
      method: "POST",
    },
  );

  if (!response.ok) {
    let message = "Failed to cancel the order.";

    try {
      const data = await response.json();

      if (data?.detail) {
        message = data.detail;
      }
    } catch {
      // Keep the fallback message.
    }

    throw new Error(message);
  }

  return response.json();
}

export async function confirmAndExecuteRefund(conversationId, actionId) {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/conversations/${conversationId}/pending-actions/${actionId}/refund/confirm-and-execute`,
    {
      method: "POST",
    },
  );

  if (!response.ok) {
    let message = "Failed to initiate the refund.";

    try {
      const data = await response.json();

      if (data?.detail) {
        message = data.detail;
      }
    } catch {
      message = "Failed to initiate the refund.";
    }

    throw new Error(message);
  }

  return response.json();
}

export async function rejectPendingAction(conversationId, actionId) {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/conversations/${conversationId}/pending-actions/${actionId}/reject`,
    {
      method: "POST",
    },
  );

  if (!response.ok) {
    let message = "Failed to keep the order.";

    try {
      const data = await response.json();

      if (data?.detail) {
        message = data.detail;
      }
    } catch {
      // Keep the fallback message.
    }

    throw new Error(message);
  }

  return response.json();
}
