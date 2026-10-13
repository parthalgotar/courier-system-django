import React, { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Layers, ChevronDown, Check, X } from "lucide-react";

export const ORDER_GROUP_BY_OPTIONS = [
  { id: "vendor", label: "Vendor" },
  { id: "status", label: "Status" },
  { id: "driver", label: "Driver" },
  {
    id: "order_date",
    label: "Order Date",
    hasSubmenu: true,
    subOptions: [
      { subId: "month", label: "Month" },
      { subId: "day", label: "Day" },
      { subId: "quarter", label: "Quarter" },
      { subId: "year", label: "Year" },
    ],
  },
  { id: "customer", label: "Customer" },
  { id: "route", label: "Route" },
  { id: "payment_status", label: "Payment Status" },
  {
    id: "pickup_date",
    label: "Pickup Date",
    hasSubmenu: true,
    subOptions: [
      { subId: "month", label: "Month" },
      { subId: "day", label: "Day" },
      { subId: "quarter", label: "Quarter" },
      { subId: "year", label: "Year" },
    ],
  },
  {
    id: "delivery_date",
    label: "Delivery Date",
    hasSubmenu: true,
    subOptions: [
      { subId: "month", label: "Month" },
      { subId: "day", label: "Day" },
      { subId: "quarter", label: "Quarter" },
      { subId: "year", label: "Year" },
    ],
  },
  { id: "destination", label: "Destination City" },
  { id: "commodity", label: "Commodity" },
  { id: "amount", label: "Value Range" },
];

export const INVOICE_GROUP_BY_OPTIONS = [
  { id: "vendor", label: "Vendor" },
  { id: "status", label: "Status" },
  { id: "driver", label: "Driver" },
  { id: "order_date", label: "Order Date" },
  { id: "customer", label: "Customer" },
  { id: "route", label: "Route" },
  { id: "invoice_date", label: "Invoice Date" },
  { id: "payment_status", label: "Payment Status" },
  { id: "journal", label: "Journal" },
  { id: "tags", label: "Tags" },
];

/**
 * Reusable Group By Multi-Select Dropdown Component.
 * Supports multiple selections in order, collapsible sub-options,
 * badge counters, and clean keyboard/mouse interactions.
 */
export default function GroupByDropdown({
  options = [],
  activeGroupBys = [],
  onToggleGroupBy,
  onClear,
  buttonLabel = "Group By",
  className = "",
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [expandedSubmenu, setExpandedSubmenu] = useState(null);
  const containerRef = useRef(null);

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const count = activeGroupBys.length;

  return (
    <div className={`relative ${className}`} ref={containerRef}>
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border transition-all duration-150 ${
          count > 0
            ? "bg-[#714B67] text-white border-[#714B67] shadow-sm hover:bg-[#5e3d55]"
            : "bg-white text-ink border-paper-line hover:bg-paper hover:text-ink shadow-xs"
        }`}
        title="Group records"
        aria-expanded={isOpen}
      >
        <Layers size={14} className={count > 0 ? "text-white" : "text-[#714B67]"} />
        <span>{buttonLabel}</span>
        {count > 0 && (
          <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-white/20 text-white font-mono font-bold">
            {count}
          </span>
        )}
        <ChevronDown
          size={13}
          className={`transition-transform duration-150 ${isOpen ? "rotate-180" : ""}`}
        />
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="absolute right-0 mt-2 w-72 bg-white rounded-lg shadow-xl border border-paper-line z-50 py-1.5 text-xs text-ink"
            style={{ minWidth: "260px", transformOrigin: "top right" }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-3.5 py-2 border-b border-paper-line">
              <div className="flex items-center gap-2 font-semibold text-ink text-sm">
                <Layers size={15} className="text-[#714B67]" />
                <span>Group By</span>
                {count > 0 && (
                  <span className="text-[11px] text-ink-faint font-normal font-mono">
                    ({count} selected)
                  </span>
                )}
              </div>
              {count > 0 && (
                <button
                  type="button"
                  onClick={() => {
                    onClear?.();
                  }}
                  className="text-xs text-freight hover:text-freight-dark hover:underline font-medium transition-colors"
                >
                  Clear
                </button>
              )}
            </div>

            <p className="px-3.5 py-1.5 text-[11px] text-ink-faint border-b border-paper-line/50">
              Select multiple options to create nested levels:
            </p>

            {/* Options list */}
            <div className="py-1 max-h-[420px] overflow-y-auto">
              {options.map((item) => {
                // Find if active either directly or with subId (e.g. "order_date" or "order_date:month")
                const activeIndex = activeGroupBys.findIndex(
                  (id) => id === item.id || id.startsWith(`${item.id}:`)
                );
                const isSelected = activeIndex !== -1;
                const hasSub = item.hasSubmenu && Array.isArray(item.subOptions);
                const isExpanded = expandedSubmenu === item.id;

                return (
                  <div key={item.id} className="border-b border-paper-line/30 last:border-0">
                    <div className="flex items-center justify-between hover:bg-paper transition-colors px-2 py-0.5">
                      {/* Checkbox & Option Label */}
                      <button
                        type="button"
                        onClick={() => onToggleGroupBy(item.id)}
                        className={`flex-1 text-left px-2 py-1.5 flex items-center gap-2 rounded transition-colors ${
                          isSelected ? "text-[#714B67] font-semibold bg-[#714B67]/5" : "text-ink"
                        }`}
                      >
                        {/* Checkbox indicator */}
                        <div
                          className={`w-4 h-4 rounded border flex items-center justify-center transition-colors flex-shrink-0 ${
                            isSelected
                              ? "bg-[#714B67] border-[#714B67] text-white"
                              : "border-paper-line bg-white hover:border-freight"
                          }`}
                        >
                          {isSelected && <Check size={11} strokeWidth={3} />}
                        </div>

                        <span className="flex-1">{item.label}</span>

                        {/* Nesting order pill */}
                        {isSelected && (
                          <span className="w-4 h-4 rounded-full bg-[#714B67]/15 text-[#714B67] flex items-center justify-center text-[10px] font-mono font-bold">
                            {activeIndex + 1}
                          </span>
                        )}
                      </button>

                      {/* Submenu toggle arrow */}
                      {hasSub && (
                        <button
                          type="button"
                          onClick={() => setExpandedSubmenu(isExpanded ? null : item.id)}
                          className="p-1.5 text-ink-faint hover:text-ink rounded hover:bg-white"
                          title={`Toggle ${item.label} intervals`}
                        >
                          <ChevronDown
                            size={13}
                            className={`transition-transform duration-200 ${isExpanded ? "rotate-180" : ""}`}
                          />
                        </button>
                      )}
                    </div>

                    {/* Submenu (e.g. Month, Day, Quarter, Year) */}
                    {hasSub && (
                      <AnimatePresence>
                        {isExpanded && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.15 }}
                            className="overflow-hidden bg-paper/50 py-1 pl-8 pr-3 border-t border-paper-line/40 space-y-0.5"
                          >
                            {item.subOptions.map((sub) => {
                              const subFullId = `${item.id}:${sub.subId}`;
                              const subIndex = activeGroupBys.indexOf(subFullId);
                              const isSubSelected = subIndex !== -1;
                              return (
                                <button
                                  key={sub.subId}
                                  type="button"
                                  onClick={() => onToggleGroupBy(subFullId)}
                                  className={`w-full text-left px-2 py-1 text-[11px] rounded flex items-center justify-between hover:bg-white transition-colors ${
                                    isSubSelected
                                      ? "text-[#714B67] font-bold bg-white shadow-xs"
                                      : "text-ink-soft hover:text-ink"
                                  }`}
                                >
                                  <span>{sub.label}</span>
                                  {isSubSelected && (
                                    <span className="flex items-center gap-1">
                                      <span className="text-[10px] font-mono bg-[#714B67] text-white rounded-full w-3.5 h-3.5 flex items-center justify-center">
                                        {subIndex + 1}
                                      </span>
                                      <Check size={11} className="text-[#714B67]" />
                                    </span>
                                  )}
                                </button>
                              );
                            })}
                          </motion.div>
                        )}
                      </AnimatePresence>
                    )}
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
