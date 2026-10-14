import { useEffect, useState } from "react";
import { getDemoOrders } from "../api/orders";
import CreateOrderForm from "./CreateOrderForm";

function OrdersPanel({ onTestInChat }) {
  const [orders, setOrders] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createdOrderNumber, setCreatedOrderNumber] = useState("");
  const [copyMessage, setCopyMessage] = useState("");
  useEffect(() => {
    let cancelled = false;

    getDemoOrders()
      .then((data) => {
        if (!cancelled) {
          setOrders(data);
          setError("");
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load orders.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const filteredOrders = orders.filter((order) => {
    const query = search.trim().toLowerCase();

    return (
      order.order_number.toLowerCase().includes(query) ||
      order.customer_name.toLowerCase().includes(query)
    );
  });

  function handleRefresh() {
    setLoading(true);
    setReloadKey((current) => current + 1);
  }

  function formatAmount(order) {
    return `${order.currency} ${Number(order.total_amount).toLocaleString(
      "en-IN",
      {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      },
    )}`;
  }

  function handleOrderCreated(order) {
    setCreatedOrderNumber(order.order_number);
    setCopyMessage("");
    setShowCreateForm(false);
    handleRefresh();
  }

  async function handleCopyOrderNumber(orderNumber) {
    try {
      await navigator.clipboard.writeText(orderNumber);

      setCopyMessage("Order number copied to clipboard.");
    } catch {
      setCopyMessage(
        "Unable to copy automatically. Please select and copy the order number.",
      );
    }
  }
  return (
    <section className="flex min-h-0 flex-1 flex-col overflow-y-auto p-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">Order Scenario Manager</h2>

          <p className="mt-1 text-sm text-slate-400">
            Manage customer orders and test AI support scenarios.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleRefresh}
            disabled={loading}
            className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-medium text-slate-200 transition hover:bg-slate-800 disabled:opacity-50"
          >
            {loading ? "Loading..." : "Refresh"}
          </button>

          <button
            type="button"
            onClick={() => {
              setCreatedOrderNumber("");
              setShowCreateForm((current) => !current);
            }}
            className="rounded-lg bg-indigo-600 px-5 py-2 text-sm font-medium text-white transition hover:bg-indigo-500"
          >
            {showCreateForm ? "Close Form" : "+ Create Order"}
          </button>
        </div>
      </div>

      {createdOrderNumber && (
        <div className="mb-5 rounded-xl border border-indigo-500/30 bg-indigo-500/10 p-5">
          <p className="text-sm font-semibold text-indigo-300">
            Order created successfully!
          </p>

          <p className="mt-2 text-sm text-slate-300">
            Your generated order number:
          </p>

          <p className="mt-2 break-all font-mono text-xl font-semibold text-white">
            {createdOrderNumber}
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => handleCopyOrderNumber(createdOrderNumber)}
              className="rounded-lg border border-indigo-500/40 bg-indigo-500/10 px-4 py-2.5 text-sm font-medium text-indigo-300 transition hover:bg-indigo-500/20"
            >
              Copy Order Number
            </button>

            <button
              type="button"
              onClick={() => onTestInChat(createdOrderNumber)}
              className="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-indigo-500"
            >
              Test in Chat →
            </button>
          </div>

          {copyMessage && (
            <p role="status" className="mt-3 text-xs text-slate-300">
              {copyMessage}
            </p>
          )}
        </div>
      )}

      {showCreateForm && (
        <CreateOrderForm
          onCreated={handleOrderCreated}
          onCancel={() => setShowCreateForm(false)}
        />
      )}

      <div className="mb-5">
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search by order number or customer..."
          aria-label="Search orders"
          className="w-full max-w-md rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-slate-100 outline-none placeholder:text-slate-500 focus:border-indigo-500"
        />
      </div>

      {error && (
        <div
          role="alert"
          className="mb-5 rounded-lg border border-red-900 bg-red-950/50 p-4 text-sm text-red-300"
        >
          {error}
        </div>
      )}

      <div className="min-h-[260px] flex-1 overflow-auto rounded-xl border border-slate-800">
        <table className="w-full min-w-[850px] border-collapse text-left text-sm">
          <thead className="sticky top-0 z-10 bg-slate-900 text-slate-400">
            <tr>
              <th className="px-5 py-4 font-medium">Order Number</th>

              <th className="px-5 py-4 font-medium">Customer</th>

              <th className="px-5 py-4 font-medium">Order Status</th>

              <th className="px-5 py-4 font-medium">Payment</th>

              <th className="px-5 py-4 font-medium">Amount</th>

              <th className="px-5 py-4 font-medium">Type</th>
            </tr>
          </thead>

          <tbody className="divide-y divide-slate-800">
            {filteredOrders.map((order) => (
              <tr
                key={order.id}
                className="bg-slate-950 transition hover:bg-slate-900/70"
              >
                <td className="px-5 py-4 font-medium text-indigo-400">
                  {order.order_number}
                </td>

                <td className="px-5 py-4 text-slate-200">
                  {order.customer_name}
                </td>

                <td className="px-5 py-4">
                  <span className="inline-flex rounded-md bg-slate-800 px-3 py-1 text-xs capitalize text-slate-200">
                    {order.status}
                  </span>
                </td>

                <td className="px-5 py-4">
                  <span className="inline-flex rounded-md bg-slate-800 px-3 py-1 text-xs capitalize text-slate-200">
                    {order.payment_status}
                  </span>
                </td>

                <td className="px-5 py-4 font-medium text-slate-200">
                  {formatAmount(order)}
                </td>

                <td className="px-5 py-4">
                  {order.is_demo_managed ? (
                    <span className="rounded-md bg-indigo-500/10 px-3 py-1 text-xs text-indigo-300">
                      Demo
                    </span>
                  ) : (
                    <span className="rounded-md bg-slate-800 px-3 py-1 text-xs text-slate-400">
                      Seeded
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {!loading && !error && filteredOrders.length === 0 && (
          <div className="p-12 text-center text-sm text-slate-400">
            No matching orders found.
          </div>
        )}

        {loading && (
          <div className="p-12 text-center text-sm text-slate-400">
            Loading orders...
          </div>
        )}
      </div>

      <div className="mt-4 text-xs text-slate-500">
        Showing {filteredOrders.length} of {orders.length} orders
      </div>
    </section>
  );
}

export default OrdersPanel;
