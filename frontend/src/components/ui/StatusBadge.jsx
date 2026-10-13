import React from "react";
import { Check } from "lucide-react";

/**
 * Soft color mappings for Invoice Status Badge
 * draft     -> "Draft"     amber/grey (bg #FEF3C7, text #92400E)
 * posted    -> "Posted"    blue       (bg #DBEAFE, text #1E40AF)
 * paid      -> "Paid"      green      (bg #DCFCE7, text #166534) with check icon
 * cancelled -> "Cancelled" red        (bg #FEE2E2, text #991B1B)
 * unknown   -> "-"         neutral grey
 */
const STATUS_CONFIG = {
  draft: {
    label: "Draft",
    bg: "#FEF3C7",
    color: "#92400E",
    dotColor: "#D97706",
  },
  posted: {
    label: "Posted",
    bg: "#DBEAFE",
    color: "#1E40AF",
    dotColor: "#2563EB",
  },
  issued: {
    label: "Posted",
    bg: "#DBEAFE",
    color: "#1E40AF",
    dotColor: "#2563EB",
  },
  paid: {
    label: "Paid",
    bg: "#DCFCE7",
    color: "#166534",
    dotColor: "#166534",
    showCheck: true,
  },
  cancelled: {
    label: "Cancelled",
    bg: "#FEE2E2",
    color: "#991B1B",
    dotColor: "#DC2626",
  },
};

const DEFAULT_CONFIG = {
  label: "-",
  bg: "#F3F4F6",
  color: "#4B5563",
  dotColor: "#9CA3AF",
};

export default function StatusBadge({ status, className = "" }) {
  const normalized = status ? String(status).toLowerCase().trim() : "";
  const config = STATUS_CONFIG[normalized] || DEFAULT_CONFIG;

  return (
    <span
      role="status"
      aria-label={`Invoice status: ${config.label}`}
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium tracking-wide ${className}`}
      style={{ backgroundColor: config.bg, color: config.color }}
    >
      {config.showCheck ? (
        <Check size={12} strokeWidth={2.5} className="shrink-0" aria-hidden="true" />
      ) : (
        <span
          className="w-1.5 h-1.5 rounded-full shrink-0"
          style={{ backgroundColor: config.dotColor }}
          aria-hidden="true"
        />
      )}
      <span>{config.label}</span>
    </span>
  );
}
