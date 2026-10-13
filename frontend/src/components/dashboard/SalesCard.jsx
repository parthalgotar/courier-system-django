import React from "react";
import { Plus, ChevronRight } from "lucide-react";
import { Card } from "../ui.jsx";
import MiniBarChart from "./MiniBarChart.jsx";

export default function SalesCard({
  salesData,
  onNavigateFilter,
  onNewInvoice,
  currency = "USD",
}) {
  const formatMoney = (val) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency }).format(val || 0);

  const toValidate = salesData?.to_validate || { count: 0, amount: 0 };
  const unpaid = salesData?.unpaid || { count: 0, amount: 0 };
  const late = salesData?.late || { count: 0, amount: 0 };
  const monthly = salesData?.monthly || [];

  return (
    <Card className="p-6 border border-paper-line shadow-xs">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 pb-4 border-b border-paper-line">
        <div>
          <div className="flex items-center gap-3">
            <h3 className="font-display text-lg font-bold text-ink">Sales</h3>
            <button
              onClick={onNewInvoice}
              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded bg-freight text-white hover:bg-freight-dark transition-all shadow-xs hover:shadow-glow"
              title="Create new draft invoice"
            >
              <Plus size={13} />
              <span>New</span>
            </button>
          </div>
          <p className="text-xs text-ink-faint mt-1">Invoices, revenue &amp; payment tracking</p>
        </div>

        {/* 3 Clickable status indicator rows */}
        <div className="flex flex-col gap-1.5 min-w-[220px]">
          <div
            onClick={() => onNavigateFilter({ status: "draft" })}
            className="flex items-center justify-between px-3 py-1.5 rounded-md hover:bg-paper cursor-pointer transition-colors group"
          >
            <span className="text-xs text-ink-soft group-hover:text-ink font-medium">
              <span className="font-bold text-ink mr-1.5">{toValidate.count}</span>
              To Validate
            </span>
            <div className="flex items-center gap-1 font-mono text-xs text-ink-soft group-hover:text-freight font-medium">
              <span>{formatMoney(toValidate.amount)}</span>
              <ChevronRight size={13} className="text-ink-faint group-hover:translate-x-0.5 transition-transform" />
            </div>
          </div>

          <div
            onClick={() => onNavigateFilter({ status: "posted", unpaid: "true" })}
            className="flex items-center justify-between px-3 py-1.5 rounded-md hover:bg-paper cursor-pointer transition-colors group"
          >
            <span className="text-xs text-ink-soft group-hover:text-ink font-medium">
              <span className="font-bold text-amber-600 mr-1.5">{unpaid.count}</span>
              Unpaid
            </span>
            <div className="flex items-center gap-1 font-mono text-xs text-ink-soft group-hover:text-amber-600 font-medium">
              <span>{formatMoney(unpaid.amount)}</span>
              <ChevronRight size={13} className="text-ink-faint group-hover:translate-x-0.5 transition-transform" />
            </div>
          </div>

          <div
            onClick={() => onNavigateFilter({ status: "posted", overdue: "true" })}
            className="flex items-center justify-between px-3 py-1.5 rounded-md hover:bg-paper cursor-pointer transition-colors group"
          >
            <span className="text-xs text-ink-soft group-hover:text-ink font-medium">
              <span className="font-bold text-alert mr-1.5">{late.count}</span>
              Late
            </span>
            <div className="flex items-center gap-1 font-mono text-xs text-ink-soft group-hover:text-alert font-medium">
              <span>{formatMoney(late.amount)}</span>
              <ChevronRight size={13} className="text-ink-faint group-hover:translate-x-0.5 transition-transform" />
            </div>
          </div>
        </div>
      </div>

      {/* 12 Months Purple Bar Chart */}
      <div className="mt-5">
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs font-medium uppercase tracking-wider text-ink-faint">
            Invoiced Total (Last 12 Months)
          </p>
          <span className="text-[11px] text-ink-faint">Monthly Totals</span>
        </div>
        <MiniBarChart data={monthly} color="#8b5cf6" currency={currency} height={180} />
      </div>
    </Card>
  );
}
