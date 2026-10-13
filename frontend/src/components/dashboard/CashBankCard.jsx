import React from "react";
import { ArrowUpRight, DollarSign, Landmark } from "lucide-react";
import { Card } from "../ui.jsx";
import MiniAreaChart from "./MiniAreaChart.jsx";

export default function CashBankCard({
  type = "cash", // "cash" or "bank"
  title,
  balance = 0,
  monthly = [],
  currency = "USD",
  onViewTransactions,
}) {
  const isCash = type.toLowerCase() === "cash";
  const displayTitle = title || (isCash ? "Cash" : "Bank");
  const chartColor = isCash ? "#10b981" : "#0284c7";
  const Icon = isCash ? DollarSign : Landmark;

  const formattedBalance = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
  }).format(balance || 0);

  return (
    <Card className="p-6 border border-paper-line shadow-xs">
      <div className="flex items-start justify-between pb-4 border-b border-paper-line">
        <div className="flex items-center gap-2.5">
          <div
            className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
            style={{ backgroundColor: `${chartColor}15`, color: chartColor }}
          >
            <Icon size={18} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-display text-base font-bold text-ink">{displayTitle}</h3>
              <button
                onClick={onViewTransactions}
                className="inline-flex items-center gap-1 text-[11px] font-medium text-freight hover:text-freight-dark px-2 py-0.5 rounded bg-freight/10 hover:bg-freight/20 transition-colors"
                title={`View ${displayTitle} transactions`}
              >
                <span>Transactions</span>
                <ArrowUpRight size={11} />
              </button>
            </div>
            <p className="text-xs text-ink-faint mt-0.5">Payments Journal</p>
          </div>
        </div>

        <div className="text-right">
          <p className="text-xs uppercase tracking-wider text-ink-faint">Balance</p>
          <p className="font-display text-xl font-bold text-ink mt-0.5 tracking-tight font-mono">
            {formattedBalance}
          </p>
        </div>
      </div>

      <div className="mt-4">
        <p className="text-[11px] font-medium uppercase tracking-wider text-ink-faint mb-2">
          Collections (Last 12 Months)
        </p>
        <MiniAreaChart
          data={monthly}
          color={chartColor}
          gradientId={`gradient-${type}`}
          currency={currency}
          height={140}
        />
      </div>
    </Card>
  );
}
