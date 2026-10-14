const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export async function getDemoOrders() {
  const response = await fetch(`${API_BASE_URL}/api/v1/demo/orders`);

  if (!response.ok) {
    throw new Error("Failed to load orders.");
  }

  const data = await response.json();

  if (!Array.isArray(data)) {
    throw new Error("Invalid orders response.");
  }

  return data;
}

export async function createDemoOrder(payload) {
  const response = await fetch(`${API_BASE_URL}/api/v1/demo/orders`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorMessage = "Failed to create order.";

    try {
      const data = await response.json();

      if (typeof data.detail === "string") {
        errorMessage = data.detail;
      } else if (Array.isArray(data.detail)) {
        errorMessage = data.detail.map((item) => item.msg).join(", ");
      }
    } catch {
      errorMessage = "Failed to create order.";
    }

    throw new Error(errorMessage);
  }

  return response.json();
}
