import React from "react";
import { ResponsiveContainer, AreaChart, Area, XAxis, Tooltip } from "recharts";

function CustomTooltip({ active, payload, label, currency = "USD" }) {
  if (active && payload && payload.length) {
    const val = payload[0].value;
    const formatted = new Intl.NumberFormat("en-US", { style: "currency", currency }).format(val);
    return (
      <div className="bg-paper-card border border-paper-line rounded-md px-3 py-2 shadow-lg text-xs">
        <p className="font-semibold text-ink">{label}</p>
        <p className="text-freight font-mono mt-0.5">{formatted}</p>
      </div>
    );
  }
  return null;
}

export default function MiniAreaChart({
  data = [],
  color = "#10b981",
  gradientId = "areaGradient",
  currency = "USD",
  height = 140,
}) {
  const formattedData = data.map((item) => {
    let shortMonth = item.month;
    if (item.month && item.month.includes("-")) {
      const [, m] = item.month.split("-");
      const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      shortMonth = monthNames[parseInt(m, 10) - 1] || item.month;
    }
    return {
      ...item,
      shortMonth,
    };
  });

  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={formattedData} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={color} stopOpacity={0.4} />
              <stop offset="95%" stopColor={color} stopOpacity={0.0} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="shortMonth"
            stroke="#94a3b8"
            fontSize={11}
            tickLine={false}
            axisLine={{ stroke: "#e2e8f0" }}
          />
          <Tooltip content={<CustomTooltip currency={currency} />} />
          <Area
            type="monotone"
            dataKey="amount"
            stroke={color}
            strokeWidth={2}
            fillOpacity={1}
            fill={`url(#${gradientId})`}
            animationDuration={800}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
