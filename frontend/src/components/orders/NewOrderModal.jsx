import React, { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import Modal from "../ui/Modal.jsx";
import { Button, Input, ErrorBanner } from "../ui.jsx";
import { api } from "../../api/client.js";

const todayIso = () => new Date().toISOString().split("T")[0];

const emptyForm = {
  vendor_id: "",
  customer_name: "",
  customer_phone: "",
  customer_email: "",
  delivery_address: "",
  delivery_lat: "",
  delivery_lng: "",
  origin_city: "",
  destination_city: "",
  commodity: "",
  weight_kg: "",
  declared_value: "",
  is_cod: false,
  cod_amount: "",
  sku: "",
  quantity: 1,
  order_date: "",
  driver_id: "",
};

export default function NewOrderModal({
  isOpen,
  onClose,
  onSuccess,
  vendors = [],
  role,
  token,
}) {
  const [form, setForm] = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);
  const [generalError, setGeneralError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [drivers, setDrivers] = useState([]);
  const [driversLoading, setDriversLoading] = useState(false);

  // Reset or initialize form whenever modal opens
  useEffect(() => {
    if (isOpen) {
      setGeneralError("");
      setFieldErrors({});
      const today = todayIso();
      if (role === "vendor" && vendors.length > 0) {
        setForm((prev) => ({
          ...emptyForm,
          vendor_id: prev.vendor_id || vendors[0].id,
          order_date: today,
        }));
      } else if (vendors.length > 0) {
        setForm((prev) => ({
          ...emptyForm,
          vendor_id: prev.vendor_id || vendors[0].id,
          order_date: today,
        }));
      } else {
        setForm({ ...emptyForm, order_date: today });
      }

      // Load drivers
      setDriversLoading(true);
      api.listDrivers(token)
        .then((res) => {
          const list = Array.isArray(res) ? res : res?.results || [];
          setDrivers(list);
        })
        .catch(() => setDrivers([]))
        .finally(() => setDriversLoading(false));
    }
  }, [isOpen, role, vendors, token]);

  async function handleSubmit(e) {
    e.preventDefault();
    setGeneralError("");
    setFieldErrors({});
    setSubmitting(true);

    try {
      const vid = Number(
        form.vendor_id || (vendors.length > 0 ? vendors[0].id : 0)
      );

      await api.createOrder(token, {
        vendor_id: vid,
        customer_name: form.customer_name,
        customer_phone: form.customer_phone,
        customer_email: form.customer_email || undefined,
        delivery_address: form.delivery_address,
        delivery_lat: form.delivery_lat ? Number(form.delivery_lat) : null,
        delivery_lng: form.delivery_lng ? Number(form.delivery_lng) : null,
        origin_city: form.origin_city,
        destination_city: form.destination_city,
        commodity: form.commodity || "General Cargo",
        weight_kg: form.weight_kg ? Number(form.weight_kg) : 0,
        declared_value: form.declared_value ? Number(form.declared_value) : 0,
        is_cod: form.is_cod,
        cod_amount: form.is_cod && form.cod_amount ? Number(form.cod_amount) : 0,
        order_date: form.order_date || todayIso(),
        driver_id: form.driver_id ? Number(form.driver_id) : null,
        items: form.sku
          ? [{ sku: form.sku, quantity: Number(form.quantity) }]
          : [],
      });

      setForm(emptyForm);
      onSuccess?.();
      onClose();
    } catch (err) {
      if (err.detail && typeof err.detail === "object" && !Array.isArray(err.detail)) {
        setFieldErrors(err.detail);
      } else {
        setGeneralError(err.message || "Failed to create order.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  function getFieldError(fieldName) {
    const error = fieldErrors[fieldName];
    if (!error) return null;
    return Array.isArray(error) ? error.join(" ") : String(error);
  }

  const modalFooter = (
    <>
      <Button
        type="button"
        variant="ghost"
        onClick={onClose}
        disabled={submitting}
        className="px-4 py-2"
      >
        Cancel
      </Button>
      <Button
        type="submit"
        form="new-order-modal-form"
        disabled={submitting || (vendors.length === 0 && role !== "vendor")}
        className="px-4 py-2"
      >
        {submitting ? (
          <>
            <RefreshCw size={14} className="animate-spin" /> Creating…
          </>
        ) : (
          "Create Order"
        )}
      </Button>
    </>
  );

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="New order (Milestone 1)"
      footer={modalFooter}
    >
      <ErrorBanner message={generalError} />

      <form
        id="new-order-modal-form"
        onSubmit={handleSubmit}
        className="flex flex-col gap-3"
      >
        {/* Vendor (shipper) */}
        <div>
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="font-medium text-ink-soft">Vendor (shipper)</span>
            {role === "vendor" ? (
              <div className="rounded-md border border-paper-line bg-paper px-3 py-2 text-sm text-ink font-medium">
                {vendors.find((v) => v.id === form.vendor_id)?.name ||
                  vendors[0]?.name ||
                  "My Vendor Profile"}
              </div>
            ) : (
              <select
                required
                value={form.vendor_id}
                onChange={(e) =>
                  setForm({ ...form, vendor_id: e.target.value })
                }
                className="rounded-md border border-paper-line bg-white px-3 py-2 text-sm focus:border-freight outline-none"
              >
                <option value="" disabled>
                  Select vendor…
                </option>
                {vendors.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name}
                  </option>
                ))}
              </select>
            )}
          </label>
          {getFieldError("vendor") && (
            <p className="text-xs text-alert mt-1">{getFieldError("vendor")}</p>
          )}
          {getFieldError("vendor_id") && (
            <p className="text-xs text-alert mt-1">{getFieldError("vendor_id")}</p>
          )}
        </div>

        {/* Order Date + Driver row */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium text-ink-soft">Order Date</span>
              <input
                type="date"
                required
                value={form.order_date}
                onChange={(e) => setForm({ ...form, order_date: e.target.value })}
                className="rounded-md border border-paper-line bg-white px-3 py-2 text-sm focus:border-freight outline-none"
              />
            </label>
            {getFieldError("order_date") && (
              <p className="text-xs text-alert mt-1">{getFieldError("order_date")}</p>
            )}
          </div>

          <div>
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium text-ink-soft">Driver</span>
              <select
                value={form.driver_id}
                onChange={(e) => setForm({ ...form, driver_id: e.target.value })}
                className="rounded-md border border-paper-line bg-white px-3 py-2 text-sm focus:border-freight outline-none"
                disabled={driversLoading}
              >
                <option value="">Select driver…</option>
                {drivers.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.full_name}{d.is_available ? " ✓" : " (busy)"}
                  </option>
                ))}
              </select>
            </label>
            {getFieldError("driver_id") && (
              <p className="text-xs text-alert mt-1">{getFieldError("driver_id")}</p>
            )}
          </div>
        </div>

        {/* Customer (consignee) */}
        <div>
          <Input
            label="Customer (consignee)"
            required
            value={form.customer_name}
            onChange={(e) =>
              setForm({ ...form, customer_name: e.target.value })
            }
          />
          {getFieldError("customer_name") && (
            <p className="text-xs text-alert mt-1">{getFieldError("customer_name")}</p>
          )}
        </div>

        {/* Customer phone */}
        <div>
          <Input
            label="Customer phone"
            required
            value={form.customer_phone}
            onChange={(e) =>
              setForm({ ...form, customer_phone: e.target.value })
            }
          />
          {getFieldError("customer_phone") && (
            <p className="text-xs text-alert mt-1">{getFieldError("customer_phone")}</p>
          )}
        </div>

        {/* Customer email */}
        <div>
          <Input
            label="Customer email"
            type="email"
            value={form.customer_email}
            onChange={(e) =>
              setForm({ ...form, customer_email: e.target.value })
            }
            placeholder="customer@example.com"
          />
          {getFieldError("customer_email") && (
            <p className="text-xs text-alert mt-1">{getFieldError("customer_email")}</p>
          )}
        </div>

        {/* Delivery address */}
        <div>
          <Input
            label="Delivery address"
            required
            value={form.delivery_address}
            onChange={(e) =>
              setForm({ ...form, delivery_address: e.target.value })
            }
          />
          {getFieldError("delivery_address") && (
            <p className="text-xs text-alert mt-1">{getFieldError("delivery_address")}</p>
          )}
        </div>

        {/* Origin city & Destination city */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Input
              label="Origin city"
              value={form.origin_city}
              onChange={(e) =>
                setForm({ ...form, origin_city: e.target.value })
              }
              placeholder="Pune"
            />
            {getFieldError("origin_city") && (
              <p className="text-xs text-alert mt-1">{getFieldError("origin_city")}</p>
            )}
          </div>
          <div>
            <Input
              label="Destination city"
              value={form.destination_city}
              onChange={(e) =>
                setForm({ ...form, destination_city: e.target.value })
              }
              placeholder="Mumbai"
            />
            {getFieldError("destination_city") && (
              <p className="text-xs text-alert mt-1">{getFieldError("destination_city")}</p>
            )}
          </div>
        </div>

        {/* Latitude & Longitude */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Input
              label="Latitude"
              type="number"
              step="any"
              value={form.delivery_lat}
              onChange={(e) =>
                setForm({ ...form, delivery_lat: e.target.value })
              }
              placeholder="19.11"
            />
            {getFieldError("delivery_lat") && (
              <p className="text-xs text-alert mt-1">{getFieldError("delivery_lat")}</p>
            )}
          </div>
          <div>
            <Input
              label="Longitude"
              type="number"
              step="any"
              value={form.delivery_lng}
              onChange={(e) =>
                setForm({ ...form, delivery_lng: e.target.value })
              }
              placeholder="72.86"
            />
            {getFieldError("delivery_lng") && (
              <p className="text-xs text-alert mt-1">{getFieldError("delivery_lng")}</p>
            )}
          </div>
        </div>

        {/* Commodity */}
        <div>
          <Input
            label="Commodity"
            value={form.commodity}
            onChange={(e) => setForm({ ...form, commodity: e.target.value })}
            placeholder="Apparel cartons"
          />
          {getFieldError("commodity") && (
            <p className="text-xs text-alert mt-1">{getFieldError("commodity")}</p>
          )}
        </div>

        {/* Weight & Declared value */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Input
              label="Weight (kg)"
              type="number"
              step="any"
              value={form.weight_kg}
              onChange={(e) =>
                setForm({ ...form, weight_kg: e.target.value })
              }
            />
            {getFieldError("weight_kg") && (
              <p className="text-xs text-alert mt-1">{getFieldError("weight_kg")}</p>
            )}
          </div>
          <div>
            <Input
              label="Declared value (₹)"
              type="number"
              value={form.declared_value}
              onChange={(e) =>
                setForm({ ...form, declared_value: e.target.value })
              }
            />
            {getFieldError("declared_value") && (
              <p className="text-xs text-alert mt-1">{getFieldError("declared_value")}</p>
            )}
          </div>
        </div>

        {/* COD checkbox */}
        <label className="flex items-center gap-2 text-sm text-ink-soft">
          <input
            type="checkbox"
            checked={form.is_cod}
            onChange={(e) =>
              setForm({ ...form, is_cod: e.target.checked })
            }
            className="accent-freight"
          />
          This is a COD shipment
        </label>

        {/* COD amount */}
        {form.is_cod && (
          <div>
            <Input
              label="COD amount (₹)"
              type="number"
              value={form.cod_amount}
              onChange={(e) =>
                setForm({ ...form, cod_amount: e.target.value })
              }
            />
            {getFieldError("cod_amount") && (
              <p className="text-xs text-alert mt-1">{getFieldError("cod_amount")}</p>
            )}
          </div>
        )}

        {/* SKU & Quantity */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Input
              label="SKU"
              value={form.sku}
              onChange={(e) => setForm({ ...form, sku: e.target.value })}
              placeholder="SKU-001"
            />
            {getFieldError("sku") && (
              <p className="text-xs text-alert mt-1">{getFieldError("sku")}</p>
            )}
          </div>
          <div>
            <Input
              label="Quantity"
              type="number"
              min="1"
              value={form.quantity}
              onChange={(e) =>
                setForm({ ...form, quantity: e.target.value })
              }
            />
            {getFieldError("quantity") && (
              <p className="text-xs text-alert mt-1">{getFieldError("quantity")}</p>
            )}
          </div>
        </div>

        {vendors.length === 0 && role !== "vendor" && (
          <p className="text-xs text-ink-faint">
            Add a vendor first on the Vendors page.
          </p>
        )}
      </form>
    </Modal>
  );
}
