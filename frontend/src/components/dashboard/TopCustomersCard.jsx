import React from "react";
import { Users } from "lucide-react";
import { Card } from "../ui.jsx";

export default function TopCustomersCard({ customers = [], currency = "USD" }) {
  const formatMoney = (val) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency }).format(val || 0);

  const maxTotal = customers.reduce((max, c) => Math.max(max, c.total || 0), 1);

  return (
    <Card className="p-6 border border-paper-line shadow-xs">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Users size={18} className="text-freight" />
          <h3 className="font-display text-base font-bold text-ink">Top Customers</h3>
        </div>
        <span className="text-xs text-ink-faint">By Invoiced Volume</span>
      </div>

      {customers.length === 0 ? (
        <div className="py-8 text-center text-xs text-ink-faint">
          No customer invoicing history available yet.
        </div>
      ) : (
        <div className="space-y-3.5">
          {customers.map((c, i) => {
            const pct = Math.round(((c.total || 0) / maxTotal) * 100);
            return (
              <div key={c.id || i} className="group">
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-medium text-ink group-hover:text-freight transition-colors">
                    {c.name}
                  </span>
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-ink font-semibold">{formatMoney(c.total)}</span>
                    {c.due > 0 ? (
                      <span className="font-mono text-[11px] text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded">
                        due {formatMoney(c.due)}
                      </span>
                    ) : (
                      <span className="font-mono text-[11px] text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded">
                        settled
                      </span>
                    )}
                  </div>
                </div>
                {/* Visual share bar */}
                <div className="w-full bg-paper-line/50 rounded-full h-1.5 overflow-hidden">
                  <div
                    className="bg-freight h-full rounded-full transition-all duration-500"
                    style={{ width: `${Math.max(pct, 4)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
