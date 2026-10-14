function DetailField({ label, value }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
        {label}
      </dt>

      <dd className="mt-2 break-words text-sm font-medium text-slate-200">
        {value ?? "Not provided"}
      </dd>
    </div>
  );
}

function OrderDetails({ order, onClose }) {
  function formatAmount() {
    const amount = Number(order.total_amount);

    return `${order.currency} ${amount.toLocaleString("en-IN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  }

  function formatDate(value) {
    if (!value) {
      return "Not provided";
    }

    return new Date(`${value}T00:00:00`).toLocaleDateString("en-IN", {
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  }

  function formatTimestamp(value) {
    if (!value) {
      return "Not available";
    }

    return new Date(value).toLocaleString("en-IN", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  }

  return (
    <section
      aria-label={`Details for ${order.order_number}`}
      className="mb-6 shrink-0 rounded-xl border border-indigo-500/30 bg-slate-900/70 p-6"
    >
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h3 className="text-lg font-semibold text-white">Order Details</h3>

          <p className="mt-2 break-all font-mono text-sm text-indigo-400">
            {order.order_number}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <span className="rounded-md bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-300">
            {order.is_demo_managed ? "Demo Order" : "Seeded Order"}
          </span>

          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 transition hover:bg-slate-800 hover:text-white"
          >
            Close
          </button>
        </div>
      </div>

      <div className="space-y-8">
        <div>
          <h4 className="mb-4 text-sm font-semibold text-indigo-300">
            Order Information
          </h4>

          <dl className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            <DetailField label="Order ID" value={order.id} />

            <DetailField label="Order Number" value={order.order_number} />

            <DetailField
              label="Order Status"
              value={<span className="capitalize">{order.status}</span>}
            />

            <DetailField
              label="Payment Status"
              value={<span className="capitalize">{order.payment_status}</span>}
            />

            <DetailField label="Total Amount" value={formatAmount()} />

            <DetailField label="Currency" value={order.currency} />
          </dl>
        </div>

        <div className="border-t border-slate-800 pt-6">
          <h4 className="mb-4 text-sm font-semibold text-indigo-300">
            Customer Information
          </h4>

          <dl className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            <DetailField label="Customer ID" value={order.customer_id} />

            <DetailField label="Customer Name" value={order.customer_name} />
          </dl>
        </div>

        <div className="border-t border-slate-800 pt-6">
          <h4 className="mb-4 text-sm font-semibold text-indigo-300">
            Shipping Information
          </h4>

          <dl className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            <DetailField
              label="Shipping Address"
              value={order.shipping_address}
            />

            <DetailField label="Shipping Carrier" value={order.carrier} />

            <DetailField
              label="Tracking Number"
              value={order.tracking_number}
            />

            <DetailField
              label="Estimated Delivery Date"
              value={formatDate(order.estimated_delivery)}
            />
          </dl>
        </div>

        <div className="border-t border-slate-800 pt-6">
          <h4 className="mb-4 text-sm font-semibold text-indigo-300">
            Record Information
          </h4>

          <dl className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            <DetailField
              label="Order Type"
              value={order.is_demo_managed ? "Demo Managed" : "Seeded"}
            />

            <DetailField
              label="Created At"
              value={formatTimestamp(order.created_at)}
            />

            <DetailField
              label="Last Updated"
              value={formatTimestamp(order.updated_at)}
            />
          </dl>
        </div>
      </div>
    </section>
  );
}

export default OrderDetails;
