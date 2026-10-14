import { useRef, useState } from "react";
import { createDemoOrder } from "../api/orders";

const initialForm = {
  status: "processing",
  payment_status: "paid",
  total_amount: "",
  currency: "INR",
  shipping_address: "Demo Shipping Address",
  carrier: "",
  tracking_number: "",
  estimated_delivery: "",
};

function CreateOrderForm({ onCreated, onCancel }) {
  const [form, setForm] = useState(initialForm);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const showShippingFields =
    form.status === "shipped" || form.status === "delivered";

  const showEstimatedDelivery = form.status !== "cancelled";

  const estimatedDeliveryRef = useRef(null);

  function handleChange(event) {
    const { name, value } = event.target;

    setForm((current) => ({
      ...current,
      [name]: value,
    }));
  }

  function openEstimatedDeliveryPicker() {
    const input = estimatedDeliveryRef.current;

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

    if (submitting) {
      return;
    }

    try {
      setSubmitting(true);
      setError("");

      const payload = {
        status: form.status,
        payment_status: form.payment_status,
        total_amount: form.total_amount,
        currency: form.currency,
        shipping_address: form.shipping_address.trim(),
      };

      if (showShippingFields) {
        const carrier = form.carrier.trim();
        const trackingNumber = form.tracking_number.trim();

        if (carrier) {
          payload.carrier = carrier;
        }

        if (trackingNumber) {
          payload.tracking_number = trackingNumber;
        }
      }

      if (showEstimatedDelivery && form.estimated_delivery) {
        payload.estimated_delivery = form.estimated_delivery;
      }

      const createdOrder = await createDemoOrder(payload);

      onCreated(createdOrder);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create order.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="mb-6 rounded-xl border border-slate-800 bg-slate-900/60 p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-white">
            Create Test Order
          </h3>

          <p className="mt-1 text-sm text-slate-400">
            Customer and order number will be generated automatically.
          </p>
        </div>

        <button
          type="button"
          onClick={onCancel}
          disabled={submitting}
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
              htmlFor="order-status"
              className="mb-2 block text-sm font-medium text-slate-300"
            >
              Order Status
            </label>

            <select
              id="order-status"
              name="status"
              value={form.status}
              onChange={handleChange}
              disabled={submitting}
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white focus:border-indigo-500 focus:outline-none"
            >
              <option value="processing">Processing</option>
              <option value="shipped">Shipped</option>
              <option value="delivered">Delivered</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>

          <div>
            <label
              htmlFor="payment-status"
              className="mb-2 block text-sm font-medium text-slate-300"
            >
              Payment Status
            </label>

            <select
              id="payment-status"
              name="payment_status"
              value={form.payment_status}
              onChange={handleChange}
              disabled={submitting}
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white focus:border-indigo-500 focus:outline-none"
            >
              <option value="paid">Paid</option>
              <option value="pending">Pending</option>
              <option value="unpaid">Unpaid</option>
              <option value="failed">Failed</option>
            </select>
          </div>

          <div>
            <label
              htmlFor="order-amount"
              className="mb-2 block text-sm font-medium text-slate-300"
            >
              Total Amount
            </label>

            <input
              id="order-amount"
              type="number"
              name="total_amount"
              value={form.total_amount}
              onChange={handleChange}
              min="0.01"
              max="99999999.99"
              step="0.01"
              placeholder="2499.00"
              required
              disabled={submitting}
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white placeholder:text-slate-500 focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <div>
            <label
              htmlFor="order-currency"
              className="mb-2 block text-sm font-medium text-slate-300"
            >
              Currency
            </label>

            <select
              id="order-currency"
              name="currency"
              value={form.currency}
              onChange={handleChange}
              disabled={submitting}
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white focus:border-indigo-500 focus:outline-none"
            >
              <option value="INR">INR</option>
              <option value="USD">USD</option>
              <option value="EUR">EUR</option>
              <option value="GBP">GBP</option>
            </select>
          </div>
        </div>

        <div>
          <label
            htmlFor="shipping-address"
            className="mb-2 block text-sm font-medium text-slate-300"
          >
            Shipping Address
          </label>

          <textarea
            id="shipping-address"
            name="shipping_address"
            value={form.shipping_address}
            onChange={handleChange}
            rows={2}
            required
            disabled={submitting}
            className="w-full resize-none rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white focus:border-indigo-500 focus:outline-none"
          />
        </div>

        {showShippingFields && (
          <div className="grid gap-5 md:grid-cols-2">
            <div>
              <label
                htmlFor="shipping-carrier"
                className="mb-2 block text-sm font-medium text-slate-300"
              >
                Shipping Carrier
                <span className="ml-2 text-xs font-normal text-slate-500">
                  Optional
                </span>
              </label>

              <input
                id="shipping-carrier"
                type="text"
                name="carrier"
                value={form.carrier}
                onChange={handleChange}
                placeholder="e.g. Blue Dart, Delhivery, DTDC"
                maxLength={100}
                disabled={submitting}
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-indigo-500"
              />
            </div>

            <div>
              <label
                htmlFor="tracking-number"
                className="mb-2 block text-sm font-medium text-slate-300"
              >
                Tracking Number
                <span className="ml-2 text-xs font-normal text-slate-500">
                  Optional
                </span>
              </label>

              <input
                id="tracking-number"
                type="text"
                name="tracking_number"
                value={form.tracking_number}
                onChange={handleChange}
                placeholder="e.g. BD123456789"
                maxLength={100}
                disabled={submitting}
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-indigo-500"
              />
            </div>
          </div>
        )}

        {showEstimatedDelivery && (
          <div>
            <label
              htmlFor="estimated-delivery"
              className="mb-2 block text-sm font-medium text-slate-300"
            >
              Estimated Delivery Date
              <span className="ml-2 text-xs font-normal text-slate-500">
                Optional
              </span>
            </label>

            <div className="flex flex-col gap-3 sm:flex-row">
              <input
                ref={estimatedDeliveryRef}
                id="estimated-delivery"
                type="date"
                name="estimated_delivery"
                value={form.estimated_delivery}
                onChange={handleChange}
                onClick={openEstimatedDeliveryPicker}
                disabled={submitting}
                className="min-w-0 flex-1 cursor-pointer rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white outline-none focus:border-indigo-500 [color-scheme:dark]"
              />

              <button
                type="button"
                onClick={openEstimatedDeliveryPicker}
                disabled={submitting}
                className="rounded-lg border border-indigo-500/40 bg-indigo-500/10 px-5 py-3 text-sm font-medium text-indigo-300 transition hover:bg-indigo-500/20 disabled:opacity-50"
              >
                Select Date
              </button>
            </div>

            <p className="mt-2 text-xs text-slate-500">
              Select an estimated delivery date from the calendar, or leave it
              blank to test scenarios without a delivery estimate.
            </p>
          </div>
        )}

        {showShippingFields && (
          <p className="text-xs leading-5 text-slate-400">
            Carrier and tracking information are optional. Leave them blank to
            test how ResolveAI handles missing shipment details.
          </p>
        )}

        <div className="flex justify-end gap-3 border-t border-slate-800 pt-5">
          <button
            type="button"
            onClick={onCancel}
            disabled={submitting}
            className="rounded-lg border border-slate-700 px-5 py-2.5 text-sm text-slate-300 hover:bg-slate-800 disabled:opacity-50"
          >
            Cancel
          </button>

          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-indigo-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? "Creating Order..." : "Create Order"}
          </button>
        </div>
      </form>
    </section>
  );
}

export default CreateOrderForm;
