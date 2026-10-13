import React from "react";
import { Link } from "react-router-dom";
import StatusBadge from "./ui/StatusBadge.jsx";

/**
 * 2-column grid layout (1 column on mobile):
 * Left column (top to bottom):
 *   Order number, Vendor, Vendor address, Customer, Delivery address, Commodity
 * Right column (top to bottom):
 *   Tracking number (monospace font), Vendor phone, (empty), Route, (empty), Payment
 */
const LINKED_ORDER_FIELDS = [
  // Row 1
  {
    label: "Order number",
    getter: (order) => {
      const num = order?.order_number;
      if (!num) return "-";
      const id = order?.id;
      return id ? (
        <Link
          to={`/orders/${id}`}
          className="font-mono text-freight hover:underline inline-block"
        >
          {num}
        </Link>
      ) : (
        <span className="font-mono">{num}</span>
      );
    },
  },
  {
    label: "Tracking number",
    className: "font-mono",
    getter: (order) => order?.tracking_number || "-",
  },
  // Row 2
  {
    label: "Vendor",
    getter: (order, invoice) => order?.vendor?.name || invoice?.vendor?.name || "-",
  },
  {
    label: "Vendor phone",
    getter: (order, invoice) =>
      order?.vendor?.phone ||
      order?.vendor?.contact_phone ||
      invoice?.vendor?.phone ||
      invoice?.vendor?.contact_phone ||
      "-",
  },
  // Row 3
  {
    label: "Vendor address",
    getter: (order, invoice) => order?.vendor?.address || invoice?.vendor?.address || "-",
  },
  {
    empty: true,
  },
  // Row 4
  {
    label: "Customer",
    getter: (order, invoice) => order?.customer_name || invoice?.customer_name || "-",
  },
  {
    label: "Route",
    getter: (order) => {
      const origin = order?.origin_city?.trim?.() || "";
      const dest = order?.destination_city?.trim?.() || "";
      if (origin && dest) return `${origin} → ${dest}`;
      if (origin || dest) return origin || dest;
      return "-";
    },
  },
  // Row 5
  {
    label: "Delivery address",
    getter: (order) => order?.delivery_address || "-",
  },
  {
    empty: true,
  },
  // Row 6
  {
    label: "Commodity",
    getter: (order) => {
      const qty = order?.quantity || order?.commodity;
      const wt =
        order?.weight_kg !== undefined && order?.weight_kg !== null
          ? Number(order.weight_kg)
          : order?.weight !== undefined && order?.weight !== null
          ? Number(order.weight)
          : null;

      if (qty && wt !== null) {
        return `${qty} (${wt} kg)`;
      }
      if (qty) return `${qty}`;
      if (wt !== null) return `${wt} kg`;
      return "-";
    },
  },
  {
    label: "Payment",
    getter: (order) => {
      const pt = (order?.payment_type || "").toLowerCase().trim();
      if (pt === "cash_on_delivery" || pt === "cod" || order?.is_cod) {
        return "Cash on delivery";
      }
      if (pt === "prepaid" || (!order?.is_cod && (order?.payment_type || order?.id))) {
        return "Prepaid";
      }
      return order?.is_cod ? "Cash on delivery" : "Prepaid";
    },
  },
];

export default function LinkedOrderSection({ invoice }) {
  if (!invoice) return null;
  const order = invoice.order;
  if (!order) return null;

  return (
    <div className="mt-6 pt-4 border-t border-paper-line">
      {/* Section Header: left = Title, right = Status Badge */}
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-xs font-semibold text-ink">Linked Order Information</h3>
        <StatusBadge status={invoice.status} />
      </div>

      {/* 2-column grid (1 column on mobile) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4 text-xs">
        {LINKED_ORDER_FIELDS.map((field, idx) => {
          if (field.empty) {
            return <div key={`empty-${idx}`} className="hidden md:block" aria-hidden="true" />;
          }

          const rawVal = field.getter ? field.getter(order, invoice) : "-";
          const displayVal = React.isValidElement(rawVal) ? rawVal : (rawVal || "-");

          return (
            <div key={field.label || idx}>
              <p className="text-xs text-ink-faint mb-1">{field.label}</p>
              <div className={`text-sm text-ink ${field.className || ""}`}>
                {displayVal}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
