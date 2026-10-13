import React from "react";

// Colours follow the existing console palette (see tailwind.config.js).
const STYLES = {
  draft: "bg-paper text-ink-soft border-paper-line",
  issued: "bg-scan-soft text-scan border-scan/30",
  paid: "bg-freight-soft text-freight-dark border-freight/30",
  cancelled: "bg-alert-soft text-alert border-alert/30",
  // e-mail delivery states
  pending: "bg-transit-soft text-transit border-transit/30",
  sent: "bg-freight-soft text-freight-dark border-freight/30",
  failed: "bg-alert-soft text-alert border-alert/30",
  bounced: "bg-alert-soft text-alert border-alert/30",
};

export default function InvoiceStatusBadge({ status }) {
  const label = status ? status.charAt(0).toUpperCase() + status.slice(1) : "—";
  return (
    <span
      className={`badge-pop inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium transition-all duration-200 hover:scale-105 select-none ${
        STYLES[status] || STYLES.draft
      }`}
    >
      {label}
    </span>
  );
}
