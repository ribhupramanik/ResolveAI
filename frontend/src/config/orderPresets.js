export const ORDER_PRESETS = [
  {
    id: "custom",
    label: "Custom Order",
    description: "Configure your own order scenario.",
  },
  {
    id: "cancellation_eligible",
    label: "Cancellation Eligible",
    description:
      "Create a processing order that can be tested against the cancellation workflow.",
  },
  {
    id: "cancellation_ineligible",
    label: "Cancellation Ineligible",
    description:
      "Create a shipped order to test why cancellation is no longer available.",
  },
  {
    id: "refund_eligible",
    label: "Refund Eligible",
    description:
      "Create a paid processing order to test refund eligibility and confirmation.",
  },
  {
    id: "refund_ineligible",
    label: "Refund Ineligible",
    description:
      "Create a shipped order to test refund eligibility restrictions.",
  },
  {
    id: "tracking_available",
    label: "Tracking Available",
    description:
      "Create a shipped order with carrier, tracking number, and delivery estimate.",
  },
  {
    id: "tracking_unavailable",
    label: "Tracking Unavailable",
    description:
      "Create a shipped order without tracking information to test AI response accuracy.",
  },
];

function getFutureDate(days) {
  const today = new Date();

  const future = new Date(
    today.getFullYear(),
    today.getMonth(),
    today.getDate() + days,
  );

  const year = future.getFullYear();
  const month = String(future.getMonth() + 1).padStart(2, "0");
  const day = String(future.getDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

export function getOrderPresetForm(presetId) {
  const base = {
    status: "processing",
    payment_status: "paid",
    total_amount: "",
    currency: "INR",
    shipping_address: "Demo Shipping Address",
    carrier: "",
    tracking_number: "",
    estimated_delivery: "",
  };

  switch (presetId) {
    case "custom":
      return base;

    case "cancellation_eligible":
    case "refund_eligible":
      return {
        ...base,
        total_amount: "2499.00",
      };

    case "cancellation_ineligible":
    case "refund_ineligible":
      return {
        ...base,
        status: "shipped",
        total_amount: "2499.00",
      };

    case "tracking_available":
      return {
        ...base,
        status: "shipped",
        total_amount: "2499.00",
        carrier: "Demo Courier",
        tracking_number: `DEMO-${crypto.randomUUID().slice(0, 8).toUpperCase()}`,
        estimated_delivery: getFutureDate(5),
      };

    case "tracking_unavailable":
      return {
        ...base,
        status: "shipped",
        total_amount: "2499.00",
      };

    default:
      throw new Error("Unknown order scenario preset.");
  }
}
