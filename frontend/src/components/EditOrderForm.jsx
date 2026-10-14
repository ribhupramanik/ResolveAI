import { useRef, useState } from "react";
import { updateDemoOrder } from "../api/orders";

function EditOrderForm({ order, onUpdated, onCancel }) {
  const [form, setForm] = useState({
    status: order.status,
    payment_status: order.payment_status,
    total_amount: String(order.total_amount),
    shipping_address: order.shipping_address,
    carrier: order.carrier ?? "",
    tracking_number: order.tracking_number ?? "",
    estimated_delivery: order.estimated_delivery ?? "",
  });

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const dateInputRef = useRef(null);

  const showShippingFields =
    form.status === "shipped" || form.status === "delivered";

  const showEstimatedDelivery = form.status !== "cancelled";

  function handleChange(event) {
    const { name, value } = event.target;

    setForm((current) => ({
      ...current,
      [name]: value,
    }));
  }

  function openDatePicker() {
    const input = dateInputRef.current;

    if (!input) {
      return;
    }

    try {
      if (typeof input.showPicker === "function") {
        input.showPicker();
      } else {
        input.focus();
      }
    } catch {
      input.focus();
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();

    if (saving) {
      return;
    }

    const payload = {
      status: form.status,
      payment_status: form.payment_status,
      total_amount: form.total_amount,
      shipping_address: form.shipping_address.trim(),
      carrier:
        showShippingFields && form.carrier.trim() ? form.carrier.trim() : null,
      tracking_number:
        showShippingFields && form.tracking_number.trim()
          ? form.tracking_number.trim()
          : null,
      estimated_delivery:
        showEstimatedDelivery && form.estimated_delivery
          ? form.estimated_delivery
          : null,
    };

    try {
      setSaving(true);
      setError("");

      const updatedOrder = await updateDemoOrder(order.id, payload);

      onUpdated(updatedOrder);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update order.");
    } finally {
      setSaving(false);
    }
  }

  const inputClass =
    "w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white outline-none focus:border-indigo-500";

  return (
    <section className="mb-6 rounded-xl border border-slate-800 bg-slate-900/60 p-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold">Edit Test Order</h3>

          <p className="mt-1 break-all font-mono text-sm text-indigo-400">
            {order.order_number}
          </p>
        </div>

        <button
          type="button"
          onClick={onCancel}
          disabled={saving}
          className="rounded-lg px-3 py-2 text-sm text-slate-400 hover:bg-slate-800 hover:text-white disabled:opacity-50"
        >
          Cancel
        </button>
      </div>

      {error && (
        <div
          role="alert"
          className="mb-5 rounded-lg border border-red-900 bg-red-950/50 p-4 text-sm text-red-300"
        >
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="grid gap-5 md:grid-cols-2">
          <div>
            <label
              htmlFor="edit-order-status"
              className="mb-2 block text-sm font-medium text-slate-300"
            >
              Order Status
            </label>

            <select
              id="edit-order-status"
              name="status"
              value={form.status}
              onChange={handleChange}
              disabled={saving}
              className={inputClass}
            >
              <option value="processing">Processing</option>
              <option value="shipped">Shipped</option>
              <option value="delivered">Delivered</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>

          <div>
            <label
              htmlFor="edit-payment-status"
              className="mb-2 block text-sm font-medium text-slate-300"
            >
              Payment Status
            </label>

            <select
              id="edit-payment-status"
              name="payment_status"
              value={form.payment_status}
              onChange={handleChange}
              disabled={saving}
              className={inputClass}
            >
              <option value="paid">Paid</option>
              <option value="pending">Pending</option>
              <option value="unpaid">Unpaid</option>
              <option value="failed">Failed</option>
              <option value="refunded">Refunded</option>
            </select>
          </div>

          <div>
            <label
              htmlFor="edit-total-amount"
              className="mb-2 block text-sm font-medium text-slate-300"
            >
              Total Amount ({order.currency})
            </label>

            <input
              id="edit-total-amount"
              type="number"
              name="total_amount"
              value={form.total_amount}
              onChange={handleChange}
              min="0.01"
              max="99999999.99"
              step="0.01"
              required
              disabled={saving}
              className={inputClass}
            />
          </div>
        </div>

        <div>
          <label
            htmlFor="edit-shipping-address"
            className="mb-2 block text-sm font-medium text-slate-300"
          >
            Shipping Address
          </label>

          <textarea
            id="edit-shipping-address"
            name="shipping_address"
            value={form.shipping_address}
            onChange={handleChange}
            rows={2}
            required
            disabled={saving}
            className={inputClass}
          />
        </div>

        {showShippingFields && (
          <div className="grid gap-5 md:grid-cols-2">
            <div>
              <label
                htmlFor="edit-carrier"
                className="mb-2 block text-sm font-medium text-slate-300"
              >
                Shipping Carrier (Optional)
              </label>

              <input
                id="edit-carrier"
                type="text"
                name="carrier"
                value={form.carrier}
                onChange={handleChange}
                maxLength={100}
                placeholder="Blue Dart"
                disabled={saving}
                className={inputClass}
              />
            </div>

            <div>
              <label
                htmlFor="edit-tracking-number"
                className="mb-2 block text-sm font-medium text-slate-300"
              >
                Tracking Number (Optional)
              </label>

              <input
                id="edit-tracking-number"
                type="text"
                name="tracking_number"
                value={form.tracking_number}
                onChange={handleChange}
                maxLength={100}
                placeholder="BD123456789"
                disabled={saving}
                className={inputClass}
              />
            </div>
          </div>
        )}

        {showEstimatedDelivery && (
          <div>
            <label
              htmlFor="edit-estimated-delivery"
              className="mb-2 block text-sm font-medium text-slate-300"
            >
              Estimated Delivery Date (Optional)
            </label>

            <div className="flex flex-col gap-3 sm:flex-row">
              <input
                ref={dateInputRef}
                id="edit-estimated-delivery"
                type="date"
                name="estimated_delivery"
                value={form.estimated_delivery}
                onChange={handleChange}
                disabled={saving}
                className={`${inputClass} min-w-0 flex-1 cursor-pointer [color-scheme:dark]`}
              />

              <button
                type="button"
                onClick={openDatePicker}
                disabled={saving}
                className="rounded-lg border border-indigo-500/40 bg-indigo-500/10 px-5 py-3 text-sm font-medium text-indigo-300 hover:bg-indigo-500/20 disabled:opacity-50"
              >
                Select Date
              </button>
            </div>
          </div>
        )}

        <div className="flex justify-end gap-3 border-t border-slate-800 pt-5">
          <button
            type="button"
            onClick={onCancel}
            disabled={saving}
            className="rounded-lg border border-slate-700 px-5 py-2.5 text-sm text-slate-300 hover:bg-slate-800 disabled:opacity-50"
          >
            Cancel
          </button>

          <button
            type="submit"
            disabled={saving}
            className="rounded-lg bg-indigo-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </form>
    </section>
  );
}

export default EditOrderForm;
