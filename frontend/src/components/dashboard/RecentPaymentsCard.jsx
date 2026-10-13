import React from "react";
import { Link } from "react-router-dom";
import { Card } from "../ui.jsx";

export default function RecentPaymentsCard({ payments = [], currency = "USD" }) {
  const formatMoney = (val) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency }).format(val || 0);

  return (
    <Card className="p-6 border border-paper-line shadow-xs">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-display text-base font-bold text-ink">Recent Payments</h3>
          <p className="text-xs text-ink-faint mt-0.5">Latest 5 settlements across journals</p>
        </div>
        <span className="text-xs font-mono text-ink-faint">{payments.length} records</span>
      </div>

      {payments.length === 0 ? (
        <div className="py-8 text-center text-xs text-ink-faint">
          No payments recorded yet.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead>
              <tr className="border-b border-paper-line text-ink-faint uppercase tracking-wider font-semibold">
                <th className="py-2.5 pr-2">Payment #</th>
                <th className="py-2.5 pr-2">Invoice</th>
                <th className="py-2.5 pr-2">Customer</th>
                <th className="py-2.5 pr-2">Journal</th>
                <th className="py-2.5 pr-2 text-right">Amount</th>
                <th className="py-2.5 text-right">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-paper-line">
              {payments.map((p) => {
                const isCash = (p.journal_type || "").toLowerCase() === "cash";
                return (
                  <tr key={p.id} className="hover:bg-paper/80 transition-colors">
                    <td className="py-2.5 pr-2 font-mono font-medium text-ink">{p.number}</td>
                    <td className="py-2.5 pr-2">
                      <Link
                        to={`/invoices/${p.invoice_id}`}
                        className="font-mono text-freight hover:underline"
                      >
                        {p.invoice_number}
                      </Link>
                    </td>
                    <td className="py-2.5 pr-2 text-ink max-w-[120px] truncate" title={p.customer}>
                      {p.customer || "—"}
                    </td>
                    <td className="py-2.5 pr-2">
                      <span
                        className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium uppercase tracking-wider ${
                          isCash
                            ? "bg-emerald-100 text-emerald-800"
                            : "bg-sky-100 text-sky-800"
                        }`}
                      >
                        {p.journal}
                      </span>
                    </td>
                    <td className="py-2.5 pr-2 text-right font-mono font-semibold text-ink">
                      {formatMoney(p.amount)}
                    </td>
                    <td className="py-2.5 text-right text-ink-faint whitespace-nowrap">
                      {p.date}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
