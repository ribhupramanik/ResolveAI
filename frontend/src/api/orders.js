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
