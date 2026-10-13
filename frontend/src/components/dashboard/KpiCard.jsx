import React from "react";
import { ArrowUpRight } from "lucide-react";
import { Card } from "../ui.jsx";

export default function KpiCard({ title, amount, subtitle, icon: Icon, color = "#6366f1", onClick, active }) {
  return (
    <Card
      hover
      onClick={onClick}
      className={`p-5 cursor-pointer relative overflow-hidden transition-all duration-200 border ${
        active ? "border-freight shadow-md ring-1 ring-freight/30" : "border-paper-line hover:border-freight/40"
      }`}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-ink-faint">{title}</p>
          <p className="font-display text-2xl font-bold text-ink mt-1 tracking-tight">{amount}</p>
          {subtitle && <p className="text-xs text-ink-soft mt-1">{subtitle}</p>}
        </div>
        <div
          className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
          style={{ backgroundColor: `${color}15`, color: color }}
        >
          {Icon ? <Icon size={20} /> : <ArrowUpRight size={18} />}
        </div>
      </div>
      <div className="mt-3 flex items-center text-[11px] text-ink-faint hover:text-freight transition-colors">
        <span>View detailed list</span>
        <ArrowUpRight size={12} className="ml-0.5" />
      </div>
    </Card>
  );
}
