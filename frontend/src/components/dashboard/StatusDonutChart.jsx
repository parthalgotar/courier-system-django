import React from "react";
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from "recharts";
import { Card } from "../ui.jsx";

const COLORS = {
  draft: "#94a3b8", // Slate
  posted: "#3b82f6", // Blue
  paid: "#10b981", // Emerald
};

function DonutTooltip({ active, payload, currency = "USD" }) {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    const formatted = new Intl.NumberFormat("en-US", { style: "currency", currency }).format(data.amount || 0);
    return (
      <div className="bg-paper-card border border-paper-line rounded-md px-3 py-2 shadow-lg text-xs">
        <p className="font-semibold capitalize text-ink">{data.name}</p>
        <p className="text-ink-soft">{data.value} Invoices</p>
        <p className="text-freight font-mono mt-0.5">{formatted}</p>
      </div>
    );
  }
  return null;
}

export default function StatusDonutChart({ statusBreakdown, currency = "USD" }) {
  const formatMoney = (val) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency }).format(val || 0);

  const draft = statusBreakdown?.draft || { count: 0, amount: 0 };
  const posted = statusBreakdown?.posted || { count: 0, amount: 0 };
  const paid = statusBreakdown?.paid || { count: 0, amount: 0 };

  const chartData = [
    { name: "Draft", value: draft.count, amount: draft.amount, color: COLORS.draft },
    { name: "Posted", value: posted.count, amount: posted.amount, color: COLORS.posted },
    { name: "Paid", value: paid.count, amount: paid.amount, color: COLORS.paid },
  ].filter((d) => d.value > 0);

  const totalCount = draft.count + posted.count + paid.count;

  return (
    <Card className="p-6 border border-paper-line shadow-xs flex flex-col justify-between">
      <div>
        <h3 className="font-display text-base font-bold text-ink">Invoice Status</h3>
        <p className="text-xs text-ink-faint mt-0.5">Distribution across lifecycle states</p>
      </div>

      <div className="relative my-3 flex items-center justify-center" style={{ height: 160 }}>
        {totalCount === 0 ? (
          <p className="text-xs text-ink-faint">No invoice records</p>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Tooltip content={<DonutTooltip currency={currency} />} />
              <Pie
                data={chartData}
                innerRadius={48}
                outerRadius={70}
                paddingAngle={4}
                dataKey="value"
                animationDuration={800}
              >
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        )}
        {totalCount > 0 && (
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <span className="font-display text-xl font-bold text-ink">{totalCount}</span>
            <span className="text-[10px] uppercase tracking-wider text-ink-faint">Total</span>
          </div>
        )}
      </div>

      {/* Legend & Breakdown stats */}
      <div className="grid grid-cols-3 gap-2 pt-3 border-t border-paper-line text-center">
        <div>
          <div className="flex items-center justify-center gap-1.5 mb-0.5">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: COLORS.draft }} />
            <span className="text-[11px] font-medium text-ink-faint">Draft</span>
          </div>
          <p className="font-mono text-xs font-semibold text-ink">{draft.count}</p>
          <p className="text-[10px] text-ink-faint truncate">{formatMoney(draft.amount)}</p>
        </div>

        <div>
          <div className="flex items-center justify-center gap-1.5 mb-0.5">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: COLORS.posted }} />
            <span className="text-[11px] font-medium text-blue-600">Posted</span>
          </div>
          <p className="font-mono text-xs font-semibold text-ink">{posted.count}</p>
          <p className="text-[10px] text-ink-faint truncate">{formatMoney(posted.amount)}</p>
        </div>

        <div>
          <div className="flex items-center justify-center gap-1.5 mb-0.5">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: COLORS.paid }} />
            <span className="text-[11px] font-medium text-emerald-600">Paid</span>
          </div>
          <p className="font-mono text-xs font-semibold text-ink">{paid.count}</p>
          <p className="text-[10px] text-ink-faint truncate">{formatMoney(paid.amount)}</p>
        </div>
      </div>
    </Card>
  );
}
