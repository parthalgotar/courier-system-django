import React, { useEffect, useState } from "react";
import { Filter, RefreshCw, X } from "lucide-react";
import { api } from "../../api/client.js";
import { useAuth } from "../../context/AuthContext.jsx";

export default function DashboardFilters({
  filters,
  onChange,
  onRefresh,
  loading,
}) {
  const { token } = useAuth();
  const [customers, setCustomers] = useState([]);
  const [journals, setJournals] = useState([]);

  useEffect(() => {
    if (!token) return;
    api.listCustomers(token).then((res) => {
      setCustomers(Array.isArray(res) ? res : res?.results || []);
    }).catch(() => {});

    api.listJournals(token).then((res) => {
      setJournals(Array.isArray(res) ? res : res?.results || []);
    }).catch(() => {});
  }, [token]);

  const handleFieldChange = (key, value) => {
    onChange({ ...filters, [key]: value || undefined });
  };

  const handleClear = () => {
    onChange({});
  };

  const hasActiveFilters = Object.values(filters).some((v) => v !== undefined && v !== "");

  return (
    <div className="bg-paper-card border border-paper-line rounded-lg p-3.5 mb-6 shadow-xs flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap items-center gap-2.5">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-ink-soft mr-1">
          <Filter size={14} className="text-freight" />
          <span>Filters</span>
        </div>

        {/* Date From */}
        <div className="flex items-center gap-1 bg-white border border-paper-line rounded-md px-2 py-1 text-xs">
          <span className="text-ink-faint">From:</span>
          <input
            type="date"
            value={filters.date_from || ""}
            onChange={(e) => handleFieldChange("date_from", e.target.value)}
            className="text-ink outline-none bg-transparent"
          />
        </div>

        {/* Date To */}
        <div className="flex items-center gap-1 bg-white border border-paper-line rounded-md px-2 py-1 text-xs">
          <span className="text-ink-faint">To:</span>
          <input
            type="date"
            value={filters.date_to || ""}
            onChange={(e) => handleFieldChange("date_to", e.target.value)}
            className="text-ink outline-none bg-transparent"
          />
        </div>

        {/* Customer Select */}
        <div className="flex items-center bg-white border border-paper-line rounded-md px-2 py-1 text-xs">
          <select
            value={filters.customer || ""}
            onChange={(e) => handleFieldChange("customer", e.target.value)}
            className="text-ink outline-none bg-transparent cursor-pointer"
          >
            <option value="">All Customers</option>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>

        {/* Journal Select */}
        <div className="flex items-center bg-white border border-paper-line rounded-md px-2 py-1 text-xs">
          <select
            value={filters.journal || ""}
            onChange={(e) => handleFieldChange("journal", e.target.value)}
            className="text-ink outline-none bg-transparent cursor-pointer"
          >
            <option value="">All Journals</option>
            {journals.map((j) => (
              <option key={j.id} value={j.id}>
                {j.name} ({j.type})
              </option>
            ))}
          </select>
        </div>

        {hasActiveFilters && (
          <button
            onClick={handleClear}
            className="inline-flex items-center gap-1 text-xs text-ink-faint hover:text-alert px-2 py-1 rounded hover:bg-paper transition-colors"
            title="Clear all filters"
          >
            <X size={12} />
            <span>Clear</span>
          </button>
        )}
      </div>

      <button
        onClick={onRefresh}
        disabled={loading}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border border-paper-line bg-white hover:bg-paper text-ink transition-all disabled:opacity-50 shadow-xs"
        title="Refresh summary numbers"
      >
        <RefreshCw size={13} className={loading ? "spin text-freight" : "text-ink-soft"} />
        <span>Refresh</span>
      </button>
    </div>
  );
}
